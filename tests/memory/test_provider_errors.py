"""Unit tests for Phase 5 LLMProvider error handling (P5-T9)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx2 as httpx
import pytest
from openai import APIConnectionError, APIError, APITimeoutError, RateLimitError
from pydantic import BaseModel, ConfigDict, Field

from rekanvault.contracts.errors import ErrorCode, RekanVaultError
from rekanvault.memory.llm import LLMProvider, TokenUsage


class _DummyModel(BaseModel):
    """Minimal response_model for exercising LLMProvider.extract_structured."""

    model_config = ConfigDict(extra="ignore")
    memories: list[dict[str, object]] = Field(default_factory=list)


def _make_mock_completion(content: str | None = "not valid json") -> MagicMock:
    """Build a MagicMock standing in for an OpenAI ChatCompletion response."""
    mock_msg = MagicMock()
    mock_msg.content = content
    mock_choice = MagicMock()
    mock_choice.finish_reason = "stop"
    mock_choice.message = mock_msg
    mock_usage = MagicMock()
    mock_usage.prompt_tokens = 100
    mock_usage.completion_tokens = 50
    mock_usage.total_tokens = 150
    mock_completion = MagicMock()
    mock_completion.choices = [mock_choice]
    mock_completion.usage = mock_usage
    mock_completion.model = "llama-3.3-70b"
    return mock_completion


@pytest.mark.asyncio
async def test_rate_limit_error_raises_rekanvault_error() -> None:
    """P5-T9: RateLimitError → RekanVaultError with code=RATE_LIMITED."""
    fake_response = httpx.Response(429, request=httpx.Request("POST", "https://api.groq.com/openai/v1"))
    with patch("rekanvault.memory.llm.AsyncOpenAI") as mock_client, patch("rekanvault.memory.llm.logger"):
        mock_instance = MagicMock()
        mock_client.return_value = mock_instance
        mock_instance.chat.completions.create = AsyncMock(
            side_effect=RateLimitError("rate limited", response=fake_response, body=None)
        )
        provider = LLMProvider()

        with pytest.raises(RekanVaultError) as exc_info:
            await provider.extract_structured("sys", "user", _DummyModel)

        assert exc_info.value.code == ErrorCode.RATE_LIMITED


@pytest.mark.asyncio
async def test_timeout_error_raises_rekanvault_error() -> None:
    """P5-T9: APITimeoutError → RekanVaultError with code=PROVIDER_ERROR."""
    fake_request = httpx.Request("POST", "https://api.groq.com/openai/v1")
    with patch("rekanvault.memory.llm.AsyncOpenAI") as mock_client, patch("rekanvault.memory.llm.logger"):
        mock_instance = MagicMock()
        mock_client.return_value = mock_instance
        mock_instance.chat.completions.create = AsyncMock(side_effect=APITimeoutError(request=fake_request))
        provider = LLMProvider()

        with pytest.raises(RekanVaultError) as exc_info:
            await provider.extract_structured("sys", "user", _DummyModel)

        assert exc_info.value.code == ErrorCode.PROVIDER_ERROR


@pytest.mark.asyncio
async def test_connection_error_raises_rekanvault_error() -> None:
    """P5-T9: APIConnectionError → RekanVaultError with code=PROVIDER_ERROR."""
    fake_request = httpx.Request("POST", "https://api.groq.com/openai/v1")
    with patch("rekanvault.memory.llm.AsyncOpenAI") as mock_client, patch("rekanvault.memory.llm.logger"):
        mock_instance = MagicMock()
        mock_client.return_value = mock_instance
        mock_instance.chat.completions.create = AsyncMock(side_effect=APIConnectionError(request=fake_request))
        provider = LLMProvider()

        with pytest.raises(RekanVaultError) as exc_info:
            await provider.extract_structured("sys", "user", _DummyModel)

        assert exc_info.value.code == ErrorCode.PROVIDER_ERROR


@pytest.mark.asyncio
async def test_generic_api_error_raises_rekanvault_error() -> None:
    """P5-T9: APIError → RekanVaultError with code=PROVIDER_ERROR."""
    fake_request = httpx.Request("POST", "https://api.groq.com/openai/v1")
    with patch("rekanvault.memory.llm.AsyncOpenAI") as mock_client, patch("rekanvault.memory.llm.logger"):
        mock_instance = MagicMock()
        mock_client.return_value = mock_instance
        mock_instance.chat.completions.create = AsyncMock(
            side_effect=APIError("provider error", request=fake_request, body=None)
        )
        provider = LLMProvider()

        with pytest.raises(RekanVaultError) as exc_info:
            await provider.extract_structured("sys", "user", _DummyModel)

        assert exc_info.value.code == ErrorCode.PROVIDER_ERROR


@pytest.mark.asyncio
async def test_empty_content_raises_rekanvault_error() -> None:
    """P5-T9: choices[0].message.content=None (and no reasoning_content)
    → RekanVaultError. Falls through to pydantic validation which fails
    on empty content, yielding VALIDATION_ERROR."""
    with patch("rekanvault.memory.llm.AsyncOpenAI") as mock_client:
        mock_instance = MagicMock()
        mock_client.return_value = mock_instance
        mock_instance.chat.completions.create = AsyncMock(return_value=_make_mock_completion(content=None))
        provider = LLMProvider()

        with pytest.raises(RekanVaultError) as exc_info:
            await provider.extract_structured("sys", "user", _DummyModel)

        assert exc_info.value.code == ErrorCode.VALIDATION_ERROR


@pytest.mark.asyncio
async def test_malformed_json_raises_validation_error() -> None:
    """P5-T9: non-JSON content → RekanVaultError with code=VALIDATION_ERROR."""
    with patch("rekanvault.memory.llm.AsyncOpenAI") as mock_client:
        mock_instance = MagicMock()
        mock_client.return_value = mock_instance
        mock_instance.chat.completions.create = AsyncMock(return_value=_make_mock_completion(content="not valid json"))
        provider = LLMProvider()

        with pytest.raises(RekanVaultError) as exc_info:
            await provider.extract_structured("sys", "user", _DummyModel)

        assert exc_info.value.code == ErrorCode.VALIDATION_ERROR


@pytest.mark.asyncio
async def test_successful_call_stores_token_usage() -> None:
    """P5-T9: successful call sets provider.last_usage to a populated TokenUsage."""
    with patch("rekanvault.memory.llm.AsyncOpenAI") as mock_client:
        mock_instance = MagicMock()
        mock_client.return_value = mock_instance
        mock_instance.chat.completions.create = AsyncMock(
            return_value=_make_mock_completion(content='{"memories": []}')
        )
        provider = LLMProvider()

        result = await provider.extract_structured("sys", "user", _DummyModel)

        assert result.memories == []
        usage = provider.last_usage
        assert isinstance(usage, TokenUsage)
        assert usage.prompt_tokens == 100
        assert usage.completion_tokens == 50
        assert usage.total_tokens == 150
        assert usage.model == "llama-3.3-70b"


@pytest.mark.asyncio
async def test_retry_recovers_from_malformed_then_valid_json() -> None:
    """P5-T9: malformed attempt 0 is retried with feedback; attempt 1 parses."""
    bad = _make_mock_completion(content="not valid json")
    good = _make_mock_completion(content='{"memories": []}')
    with patch("rekanvault.memory.llm.AsyncOpenAI") as mock_client:
        mock_instance = MagicMock()
        mock_client.return_value = mock_instance
        mock_instance.chat.completions.create = AsyncMock(side_effect=[bad, good])
        provider = LLMProvider()

        result = await provider.extract_structured("sys", "user", _DummyModel)

        assert result.memories == []
        assert mock_instance.chat.completions.create.await_count == 2


@pytest.mark.asyncio
async def test_fenced_and_trailing_comma_json_is_repaired() -> None:
    """P5-T9: markdown-fenced + trailing-comma JSON is repaired and parsed."""
    content = '```json\n{"memories": [{"memory_type": "Fact",}]}\n```'
    with patch("rekanvault.memory.llm.AsyncOpenAI") as mock_client:
        mock_instance = MagicMock()
        mock_client.return_value = mock_instance
        mock_instance.chat.completions.create = AsyncMock(return_value=_make_mock_completion(content=content))
        provider = LLMProvider()

        result = await provider.extract_structured("sys", "user", _DummyModel)

        assert result.memories == [{"memory_type": "Fact"}]


def test_salvage_drops_invalid_items_and_keeps_valid() -> None:
    """A list item that fails validation is dropped; the rest are kept."""
    from rekanvault.memory.llm import _salvage_list_items

    class _Item(BaseModel):
        title: str
        summary: str

    class _Envelope(BaseModel):
        memories: list[_Item]

    data = {
        "memories": [
            {"title": "a", "summary": "b"},
            {"title": "c"},  # missing summary
            {"title": "d", "summary": "e"},
        ]
    }
    errors = [{"loc": ("memories", 1, "summary"), "msg": "Field required", "type": "missing"}]

    model, dropped = _salvage_list_items(_Envelope, data, errors)

    assert model is not None
    assert [m.title for m in model.memories] == ["a", "d"]
    assert dropped == 1


def test_salvage_returns_none_when_not_salvageable() -> None:
    """Non-dict data or errors with no item index → not salvageable."""
    from rekanvault.memory.llm import _salvage_list_items

    class _Item(BaseModel):
        title: str
        summary: str

    class _Envelope(BaseModel):
        memories: list[_Item]

    assert _salvage_list_items(_Envelope, "not a dict", []) == (None, 0)
    assert _salvage_list_items(_Envelope, {"memories": []}, [{"loc": ("memories",), "msg": "x", "type": "x"}]) == (
        None,
        0,
    )
