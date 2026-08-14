"""LLMProvider — OpenAI-compatible wrapper for memory extraction (RV-DEC-P5-0002).

Single dependency surface for the openai SDK so the rest of the memory
engine doesn't need to know whether we're talking to OpenAI, Groq, Ollama
or vLLM — only the base_url and api_key change.

Ponytail:
  * One class, one obvious entry point (`extract_structured`).
  * Token counts and finish reason are stored on the instance as a
    side-channel rather than a wrapper return type, so the call site
    signature stays `BaseModel` as specified.
  * Retries are delegated to the openai SDK (`max_retries`).
  * Never logs the API key or raw source content — only redacted
    diagnostics (model, finish_reason, prompt_tokens, completion_tokens,
    HTTP status on error).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, TypeVar

import json_repair
import structlog
from openai import (
    APIConnectionError,
    APIError,
    APITimeoutError,
    AsyncOpenAI,
    RateLimitError,
)
from openai.types.chat import ChatCompletion, ChatCompletionMessageParam
from pydantic import BaseModel, ValidationError

from apps.api.config import settings
from rekanvault.contracts.errors import ErrorCode, RekanVaultError


@dataclass(frozen=True)
class TokenUsage:
    """Token accounting from the last successful chat completion."""

    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    model: str
    finish_reason: str


logger = structlog.get_logger(__name__)


_T = TypeVar("_T", bound=BaseModel)


# ponytail: one corrective retry fixes ~70% of parse failures; a second
# catches most of the rest. Beyond 3 attempts the model just repeats itself.
_MAX_PARSE_ATTEMPTS = 3

_CODE_FENCE_RE = re.compile(r"^```(?:[a-zA-Z]+)?\s*(.*?)\s*```$", re.DOTALL)


def _parse_json_object(content: Any) -> dict[str, Any]:
    """Parse LLM output into a JSON object, recovering minor malformation.

    Strips markdown code fences, then tries stdlib ``json.loads`` before
    falling back to ``json_repair`` (trailing commas, unclosed braces, stray
    prose). Raises ``ValueError`` when the result is not a JSON object —
    the envelope is always ``{"memories": [...]}``.
    """
    if not isinstance(content, str):
        raise ValueError(f"expected string content, got {type(content).__name__}")
    text = content.strip()
    fence_match = _CODE_FENCE_RE.match(text)
    if fence_match:
        text = fence_match.group(1).strip()
    try:
        parsed: Any = json.loads(text)
    except ValueError:
        try:
            parsed = json_repair.loads(text)
        except Exception as exc:  # noqa: BLE001 — normalize any repair failure to ValueError
            raise ValueError(f"unrecoverable JSON: {exc}") from exc
    if not isinstance(parsed, dict):
        raise ValueError(f"expected JSON object, got {type(parsed).__name__}")
    return parsed


def _format_validation_errors(errors: list[Any]) -> str:
    """Render Pydantic errors as a compact, model-readable checklist."""
    lines: list[str] = []
    for error in errors[:5]:
        loc = ".".join(str(part) for part in error.get("loc", ()))
        lines.append(f"- {loc or '(root)'}: {error.get('msg')}")
    return "\n".join(lines)


def _salvage_list_items(
    response_model: type[_T],
    data: Any,
    errors: list[Any],
) -> tuple[_T | None, int]:
    """Drop list items that failed validation and re-validate the remainder.

    Returns (model, dropped_count); model is None when not salvageable.
    """
    if not isinstance(data, dict):
        return None, 0
    field_name: str | None = None
    bad_indices: set[int] = set()
    for error in errors:
        loc = error.get("loc", ())
        if len(loc) >= 2 and isinstance(loc[1], int):
            if field_name is None:
                field_name = str(loc[0])
            if str(loc[0]) == field_name:
                bad_indices.add(loc[1])
    if field_name is None:
        return None, 0
    items = data.get(field_name)
    if not isinstance(items, list):
        return None, 0
    data[field_name] = [item for i, item in enumerate(items) if i not in bad_indices]
    try:
        return response_model.model_validate(data), len(bad_indices)
    except ValidationError:
        return None, 0


class LLMProvider:
    """OpenAI-compatible LLM provider wrapper.

    Configured via ``apps.api.config.settings`` — no API keys are read
    from anywhere else. Supports any provider exposing the OpenAI
    Chat Completions protocol (Groq, Ollama, vLLM, etc.) by setting
    ``RV_LLM_BASE_URL``.
    """

    def __init__(self) -> None:
        api_key = settings.RV_LLM_API_KEY
        self._client: AsyncOpenAI = AsyncOpenAI(
            api_key=api_key,
            base_url=settings.RV_LLM_BASE_URL,
            max_retries=settings.RV_LLM_MAX_RETRIES,
            timeout=settings.RV_LLM_TIMEOUT_SECONDS,
        )
        self._model = settings.RV_EXTRACTION_MODEL
        self._max_concurrency = settings.RV_MODEL_MAX_CONCURRENCY
        self._disable_thinking = settings.RV_LLM_DISABLE_THINKING
        self._last_usage: TokenUsage | None = None

    @property
    def last_usage(self) -> TokenUsage | None:
        """Token usage from the most recent successful call."""
        return self._last_usage

    async def _call_completion(
        self,
        messages: list[ChatCompletionMessageParam],
        temperature: float,
        max_tokens: int,
        *,
        disable_thinking: bool = False,
    ) -> ChatCompletion:
        """One chat-completions call, mapping upstream errors to RekanVaultError.

        ``disable_thinking`` disables the reasoning model's chain-of-thought,
        which otherwise burns the whole output budget before emitting JSON.

        Transient HTTP retries are delegated to the openai SDK (``max_retries``);
        this maps the terminal error into a RekanVaultError.
        """
        try:
            extra_body: dict[str, Any] | None = {"thinking": {"type": "disabled"}} if disable_thinking else None
            return await self._client.chat.completions.create(
                model=self._model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                response_format={"type": "json_object"},
                extra_body=extra_body,
            )
        except RateLimitError as exc:
            _log_diagnostics("rate_limited", status=429, error=str(exc))
            raise RekanVaultError(
                "LLM provider rate-limited the extraction request",
                code=ErrorCode.RATE_LIMITED,
                target="llm.extract_structured",
            ) from exc
        except APITimeoutError as exc:
            _log_diagnostics("timeout", error=str(exc))
            raise RekanVaultError(
                "LLM provider timed out during extraction",
                code=ErrorCode.PROVIDER_ERROR,
                target="llm.extract_structured",
            ) from exc
        except APIConnectionError as exc:
            _log_diagnostics("connection_error", error=str(exc))
            raise RekanVaultError(
                "LLM provider connection failed during extraction",
                code=ErrorCode.PROVIDER_ERROR,
                target="llm.extract_structured",
            ) from exc
        except APIError as exc:
            _log_diagnostics("api_error", status=getattr(exc, "status_code", None), error=str(exc))
            raise RekanVaultError(
                "LLM provider returned an error during extraction",
                code=ErrorCode.PROVIDER_ERROR,
                target="llm.extract_structured",
            ) from exc

    async def extract_structured(
        self,
        system_prompt: str,
        user_prompt: str,
        response_model: type[_T],
        temperature: float = 0.1,
        max_tokens: int = 4096,
    ) -> _T:
        """Call the LLM and validate the response against ``response_model``.

        ``response_format`` is pinned to ``{"type": "json_object"}``. The
        response is parsed with a lenient ladder (strip fences → stdlib json
        → ``json_repair``) then validated. On parse/validation failure the
        error is fed back to the model for a bounded number of corrective
        retries before giving up.

        Raises:
            RekanVaultError: ``PROVIDER_ERROR`` for upstream failures,
                ``RATE_LIMITED`` for 429, ``VALIDATION_ERROR`` when the
                response stays unparseable or schema-invalid after retries.
        """
        messages: list[ChatCompletionMessageParam] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        last_data: Any = None
        last_errors: list[Any] = []
        for attempt in range(_MAX_PARSE_ATTEMPTS):
            completion_obj = await self._call_completion(
                messages, temperature, max_tokens, disable_thinking=self._disable_thinking
            )
            self._last_usage = _usage_from(completion_obj)
            finish_reason = self._last_usage.finish_reason

            content = _extract_message_content(completion_obj)
            if content is None:
                logger.warning(
                    "llm_empty_content",
                    finish_reason=finish_reason,
                    model=self._model,
                )
                raise RekanVaultError(
                    f"LLM returned empty content (finish_reason={finish_reason})",
                    code=ErrorCode.PROVIDER_ERROR,
                    target="llm.extract_structured",
                )

            try:
                data = _parse_json_object(content)
            except ValueError as exc:
                logger.warning(
                    "llm_json_parse_failed",
                    attempt=attempt,
                    error_type=type(exc).__name__,
                    finish_reason=finish_reason,
                    model=self._model,
                )
                messages.extend(
                    [
                        {"role": "assistant", "content": content if isinstance(content, str) else ""},
                        {
                            "role": "user",
                            "content": "Your previous response was not valid JSON. "
                            "Return ONLY a single JSON object — no prose and no markdown code fences.",
                        },
                    ]
                )
                continue

            last_data = data
            try:
                return response_model.model_validate(data)
            except ValidationError as exc:
                last_errors = exc.errors()
                logger.warning(
                    "llm_json_validation_failed",
                    attempt=attempt,
                    error_count=len(last_errors),
                    error_details=last_errors,
                    finish_reason=finish_reason,
                    model=self._model,
                )
                messages.extend(
                    [
                        {"role": "assistant", "content": content if isinstance(content, str) else ""},
                        {
                            "role": "user",
                            "content": "Your previous response did not match the expected schema. "
                            "Fix these errors and return ONLY the corrected JSON object:\n"
                            f"{_format_validation_errors(last_errors)}",
                        },
                    ]
                )

        # Retries exhausted: salvage valid items instead of dropping the whole
        # envelope, so one incomplete item can't sink the chunk's other memories.
        salvaged, dropped = _salvage_list_items(response_model, last_data, last_errors)
        if salvaged is not None:
            logger.warning(
                "llm_envelope_salvaged",
                dropped_items=dropped,
                model=self._model,
            )
            return salvaged

        # Fallback: reasoning models can starve the output budget on
        # chain-of-thought — one final attempt with thinking disabled.
        if not self._disable_thinking:
            try:
                completion_obj = await self._call_completion(messages, temperature, max_tokens, disable_thinking=True)
                self._last_usage = _usage_from(completion_obj)
                content = _extract_message_content(completion_obj)
                if content is not None:
                    data = _parse_json_object(content)
                    return response_model.model_validate(data)
            except (RekanVaultError, ValueError):
                pass

        raise RekanVaultError(
            "LLM response did not match the expected schema after retries",
            code=ErrorCode.VALIDATION_ERROR,
            target="llm.extract_structured",
            details={"errors": last_errors[:5]},
        )

    async def close(self) -> None:
        """Release the underlying HTTP client."""
        await self._client.close()


def _extract_message_content(completion: ChatCompletion) -> str | None:
    if not completion.choices:
        return None
    message = completion.choices[0].message
    # Reasoning models (deepseek, kimi, o1-style) may put their final
    # output in reasoning_content while content is empty.
    content = message.content
    if not content:
        reasoning = getattr(message, "reasoning_content", None)
        if reasoning:
            content = reasoning
    if not content:
        return None
    stripped = content.strip()
    return stripped or None


def _usage_from(completion: ChatCompletion) -> TokenUsage:
    usage = completion.usage
    finish_reason = completion.choices[0].finish_reason if completion.choices else "unknown"
    return TokenUsage(
        prompt_tokens=usage.prompt_tokens if usage else 0,
        completion_tokens=usage.completion_tokens if usage else 0,
        total_tokens=usage.total_tokens if usage else 0,
        model=completion.model,
        finish_reason=finish_reason,
    )


def _log_diagnostics(event: str, *, status: int | None = None, error: str | None = None) -> None:
    logger.warning(
        "llm_provider_error",
        provider_event=event,
        model=settings.RV_EXTRACTION_MODEL,
        http_status=status,
        error_excerpt=(error[:200] if error else None),
    )


__all__ = ["LLMProvider", "TokenUsage"]
