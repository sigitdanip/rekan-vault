"""MemoryExtractor — turns one chunk into N typed memories (P5-T4).

Ponytail:
  * Stateless service: caller passes ``provider`` so the worker can
    share one LLMProvider instance across chunks (connection pooling).
  * Validation is intentionally belt-and-braces: the LLM response
    parses against a permissive envelope, then each item is re-validated
    against the strict (``extra="forbid"``) typed model — the second
    pass is the one that catches hallucinated fields per P5-T2.
  * On any per-item validation failure, the bad item is dropped and a
    warning is logged. The whole batch never fails because of one bad
    item; only an upstream LLM error aborts the call.
"""

from __future__ import annotations

import uuid
from typing import Any

import structlog
from pydantic import BaseModel, ConfigDict, Field

from rekanvault.contracts.errors import RekanVaultError
from rekanvault.memory.llm import LLMProvider
from rekanvault.memory.models import (
    TYPED_MEMORY_MODELS,
    BaseTypedMemory,
    ImpactLevel,
    MemoryType,
    determine_review_status,
)
from rekanvault.memory.prompts import PROMPTS, render_user_prompt

logger = structlog.get_logger(__name__)

_MEMORY_TYPE_BY_LOWER: dict[str, MemoryType] = {t.value.lower(): t for t in MemoryType}


def _coerce_memory_type(raw: str) -> MemoryType | None:
    """Resolve a memory_type string, tolerating case/whitespace drift.

    Returns None only for genuinely unknown types — no fuzzy matching, so a
    near-miss is never silently retyped (precision over recall).
    """
    normalized = raw.strip()
    try:
        return MemoryType(normalized)
    except ValueError:
        return _MEMORY_TYPE_BY_LOWER.get(normalized.lower())


# Permissive envelope — strict typing happens item-by-item below.
# Uses extra="allow" so type-specific fields (steps, statement, rationale,
# etc.) survive the envelope parse and reach _materialise for strict
# per-type validation against the 18 TYPED_MEMORY_MODELS.
class _ExtractedMemoryItem(BaseModel):
    model_config = ConfigDict(extra="allow")

    memory_type: str
    title: str
    summary: str
    impact: str = "MEDIUM"
    confidence: float = Field(default=0.7, ge=0.0, le=1.0)


class _ExtractionEnvelope(BaseModel):
    model_config = ConfigDict(extra="ignore")

    memories: list[_ExtractedMemoryItem] = Field(default_factory=list)


class MemoryExtractor:
    """Extract typed memories from a single document chunk."""

    def __init__(self, provider: LLMProvider | None = None) -> None:
        self._provider = provider or LLMProvider()

    async def extract(
        self,
        chunk_text: str,
        chunk_id: str,
        document_id: uuid.UUID,
        workspace_id: uuid.UUID,
    ) -> list[BaseTypedMemory]:
        """Run one extraction pass and return valid typed memories."""
        if not chunk_text or not chunk_text.strip():
            return []

        # The LLM is told to return an array; we model it as an envelope
        # so the JSON schema hint we send downstream matches exactly.
        bundle = PROMPTS[MemoryType.FACT]  # any key works — all 18 share v1
        system_prompt = bundle["system"]
        user_prompt = render_user_prompt(MemoryType.FACT, chunk_text)

        try:
            envelope = await self._provider.extract_structured(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                response_model=_ExtractionEnvelope,
            )
        except RekanVaultError as exc:
            # The provider logs the parse/validation failure without chunk_id
            # (it's out of scope there); re-log here so the envelope failure
            # rate is attributable per-chunk instead of a raw counter.
            logger.warning(
                "memory_extraction_envelope_failed",
                chunk_id=chunk_id,
                document_id=str(document_id),
                workspace_id=str(workspace_id),
                error_code=exc.code,
                error_details=exc.details.get("errors"),
            )
            raise

        results: list[BaseTypedMemory] = []
        for item in envelope.memories:
            memory = self._materialise(
                item=item,
                chunk_id=chunk_id,
                document_id=document_id,
                workspace_id=workspace_id,
                prompt_version=bundle["version"],
            )
            if memory is not None:
                results.append(memory)
        return results

    async def close(self) -> None:
        await self._provider.close()

    def _materialise(
        self,
        *,
        item: _ExtractedMemoryItem,
        chunk_id: str,
        document_id: uuid.UUID,
        workspace_id: uuid.UUID,
        prompt_version: str,
    ) -> BaseTypedMemory | None:
        memory_type = _coerce_memory_type(item.memory_type)
        if memory_type is None:
            logger.warning(
                "memory_extraction_unknown_type",
                memory_type=item.memory_type,
                chunk_id=chunk_id,
            )
            return None

        model_cls = TYPED_MEMORY_MODELS.get(memory_type)
        if model_cls is None:
            logger.warning(
                "memory_extraction_unmapped_type",
                memory_type=memory_type.value,
                chunk_id=chunk_id,
            )
            return None

        try:
            impact = ImpactLevel(item.impact)
        except ValueError:
            impact = ImpactLevel.MEDIUM

        # Collect type-specific fields from LLM output (extra="allow" preserves
        # them in model_extra). Sanitize: strip unknown keys and log warnings
        # rather than rejecting — LLMs reliably produce the right structure but
        # may include minor formatting variances.
        extra = getattr(item, "model_extra", {}) or {}
        type_fields: dict[str, Any] = {}
        for key, value in extra.items():
            if key in {"memory_type", "title", "summary", "impact", "confidence"}:
                continue
            type_fields[key] = value

        payload: dict[str, Any] = {
            "memory_type": memory_type,
            "title": item.title,
            "summary": item.summary,
            "impact": impact,
            "confidence": item.confidence,
            "workspace_id": workspace_id,
            "evidence_chunk_ids": [chunk_id],
            "prompt_version": prompt_version,
            **type_fields,
        }

        # Validate: coerce types where possible, drop unknown fields.
        # extra="forbid" catches pure hallucinations while allowing valid
        # memories with minor formatting drift.
        allowed_keys = set(model_cls.model_fields.keys())
        cleaned: dict[str, Any] = {}
        dropped: list[str] = []
        for key, value in payload.items():
            if key in allowed_keys:
                cleaned[key] = value
            else:
                dropped.append(key)

        if dropped:
            logger.info(
                "memory_extraction_dropped_unknown_fields",
                memory_type=memory_type.value,
                chunk_id=chunk_id,
                dropped_keys=dropped,
            )

        try:
            typed_memory = model_cls.model_validate(cleaned)
        except Exception as exc:
            logger.warning(
                "memory_extraction_validation_failed",
                memory_type=memory_type.value,
                chunk_id=chunk_id,
                error_type=type(exc).__name__,
            )
            return None

        typed_memory.review_status = determine_review_status(
            memory_type=typed_memory.memory_type,
            impact=typed_memory.impact,
            confidence=typed_memory.confidence,
        )
        return typed_memory


__all__ = ["MemoryExtractor"]
