"""
P4 chunking engine (RV-DEC-P4-0004 — structure-first chunking).

Reads ``ContentBlock`` rows for a ``DocumentVersion`` and produces a stable,
deterministic list of ``Chunk`` records. The chunk_id is
``{external_id}#v{version_number}#chunk_{seq:03d}`` — pure function of
inputs, so re-processing the same version yields byte-identical chunks
(P4-T1).

Algorithm (structure-first):

1. A single block whose token count exceeds ``MAX_BLOCK_TOKENS`` is split
   internally with a sliding token window of ``OVERLAP_TOKENS`` overlap.
2. Otherwise, consecutive same-type blocks are merged into a single chunk
   until the next block would push the chunk past the budget. Merging is
   allowed only across identical ``block_type`` so structural boundaries
   stay intact.
3. Each chunk records the inclusive block-index range it spans and the
   ordered list of block_types that contributed to it.

PostgreSQL note: ``content_blocks.content_tsvector`` is a GENERATED ALWAYS
column (migration 0002) — chunker is read-only against the database; no
explicit ``UPDATE`` is needed.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

import tiktoken
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from rekanvault.storage.document_repo import DocumentRepository
from rekanvault.storage.models import ContentBlock

# --- chunking policy constants (RV-DEC-P4-0004) ---------------------------

MAX_BLOCK_TOKENS: int = 450  # ADR: ~450 tokens per chunk
OVERLAP_TOKENS: int = 80  # ADR: 80-token overlap within an oversized block
WINDOW_TOKENS: int = MAX_BLOCK_TOKENS  # split-window size = full budget

# tiktoken is stable across runs; cache the encoding on the class.
_ENCODING = tiktoken.get_encoding("cl100k_base")


class Chunk(BaseModel):
    """One evidence-ready chunk. Deterministic; safe to re-derive."""

    chunk_id: str
    document_version_id: uuid.UUID
    workspace_id: uuid.UUID
    start_block_index: int
    end_block_index: int
    content_text: str
    token_count: int
    metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = {"frozen": True}


class Chunker:
    """Structure-first chunker. Stateless; safe to reuse across calls."""

    def __init__(self, repo: DocumentRepository) -> None:
        self._repo = repo

    async def chunk_version(
        self,
        session: AsyncSession,
        document_version_id: uuid.UUID,
    ) -> list[Chunk]:
        """Return deterministic chunks for the given ``DocumentVersion``.

        Steps:
            1. Load version metadata (for ``external_id`` and ``version_number``).
            2. Load ordered ``ContentBlock`` rows.
            3. Plan chunks: split oversized blocks, then merge same-type neighbors.
            4. Assign sequential ``chunk_NNN`` ids and emit.
        """
        version = await self._repo.get_version(session, document_version_id)
        if version is None:
            return []

        document = version.document
        blocks = await self._repo.get_content_blocks(session, document_version_id)
        if not blocks:
            return []

        external_id = document.external_id
        version_number = version.version_number
        workspace_id = version.workspace_id

        planned = _plan_chunks(blocks)
        chunks = [
            _materialize(p, external_id, version_number, version.id, workspace_id) for p in planned
        ]
        return _renumber(chunks)


def _plan_chunks(blocks: list[ContentBlock]) -> list[_PlannedChunk]:
    """Pure planner — no I/O, deterministic. Splits oversized blocks,
    then greedily merges same-type neighbors up to the token budget."""
    planned: list[_PlannedChunk] = []
    for block in blocks:
        tokens = len(_ENCODING.encode(block.content_text))
        if tokens > MAX_BLOCK_TOKENS:
            planned.extend(_split_block(block, tokens))
        else:
            _merge_or_emit(planned, block, tokens)
    return planned


def _merge_or_emit(planned: list[_PlannedChunk], block: ContentBlock, tokens: int) -> None:
    """Append ``block`` to the last chunk if it's the same type and the
    new total stays under budget; otherwise start a new chunk."""
    last = planned[-1] if planned else None
    if (
        last is not None
        and last.block_type == block.block_type
        and last.token_count + tokens <= MAX_BLOCK_TOKENS
    ):
        last.text_parts.append(block.content_text)
        last.token_count += tokens
        last.end_block_index = block.block_index
        last.block_types.append(block.block_type)
        return
    planned.append(
        _PlannedChunk(
            block_type=block.block_type,
            text_parts=[block.content_text],
            start_block_index=block.block_index,
            end_block_index=block.block_index,
            token_count=tokens,
            block_types=[block.block_type],
        )
    )


def _split_block(block: ContentBlock, tokens: int) -> list[_PlannedChunk]:
    """Token-window split of one oversized block with overlap. Each
    window becomes its own chunk; block_type is preserved on all splits.
    ``tokens`` is the precomputed token count from the caller so we don't
    re-encode a second time."""
    if tokens <= MAX_BLOCK_TOKENS:
        # Defensive: caller should not route a small block here.
        return [
            _PlannedChunk(
                block_type=block.block_type,
                text_parts=[block.content_text],
                start_block_index=block.block_index,
                end_block_index=block.block_index,
                token_count=tokens,
                block_types=[block.block_type],
            )
        ]

    token_ids = _ENCODING.encode(block.content_text)
    if not token_ids:
        return []

    step = max(1, WINDOW_TOKENS - OVERLAP_TOKENS)
    splits: list[_PlannedChunk] = []
    start = 0
    while start < len(token_ids):
        end = min(start + WINDOW_TOKENS, len(token_ids))
        piece = _ENCODING.decode(token_ids[start:end])
        splits.append(
            _PlannedChunk(
                block_type=block.block_type,
                text_parts=[piece],
                start_block_index=block.block_index,
                end_block_index=block.block_index,
                token_count=end - start,
                block_types=[block.block_type],
            )
        )
        if end == len(token_ids):
            break
        start += step
    return splits


def _materialize(
    planned: _PlannedChunk,
    external_id: str,
    version_number: int,
    document_version_id: uuid.UUID,
    workspace_id: uuid.UUID,
) -> Chunk:
    """Assemble a ``Chunk`` from a planned entry + locator metadata.
    ``chunk_id`` is finalized in ``_renumber`` once the total count is
    known (so the zero-padding width is correct)."""
    return Chunk(
        chunk_id=_format_chunk_id(external_id, version_number, seq=0, width=3),
        document_version_id=document_version_id,
        workspace_id=workspace_id,
        start_block_index=planned.start_block_index,
        end_block_index=planned.end_block_index,
        content_text="\n".join(planned.text_parts),
        token_count=planned.token_count,
        metadata={"block_types": planned.block_types},
    )


def _renumber(chunks: list[Chunk]) -> list[Chunk]:
    """Assign final ``chunk_id`` (with correct zero-pad width). Width is
    the minimum number of digits needed to represent the chunk count
    (always at least 3)."""
    if not chunks:
        return chunks
    width = max(3, len(str(len(chunks))))
    out: list[Chunk] = []
    for idx, chunk in enumerate(chunks, start=1):
        # Reuse the placeholder head "{external_id}#v{version_number}".
        head = chunk.chunk_id.rsplit("#chunk_", 1)[0]
        new_id = f"{head}#chunk_{idx:0{width}d}"
        out.append(chunk.model_copy(update={"chunk_id": new_id}))
    return out


def _format_chunk_id(external_id: str, version_number: int, *, seq: int, width: int) -> str:
    return f"{external_id}#v{version_number}#chunk_{seq:0{width}d}"


# ---- internal planner record ----------------------------------------------


@dataclass
class _PlannedChunk:
    """Mutable scratch record used by the planner. Not part of the
    public API; converted to ``Chunk`` before return."""

    block_type: str
    text_parts: list[str] = field(default_factory=list)
    start_block_index: int = 0
    end_block_index: int = 0
    token_count: int = 0
    block_types: list[str] = field(default_factory=list)


__all__ = ["Chunk", "Chunker", "MAX_BLOCK_TOKENS", "OVERLAP_TOKENS"]
