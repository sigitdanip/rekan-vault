"""
Indexing pipeline (P4-T5/T6).

Orchestrates the chunk → embed → upsert → deactivate flow that turns a
``DocumentVersion`` into searchable Qdrant vectors. The pipeline owns
NO I/O of its own — every collaborator is injected, so the same class
runs in production (real DB, real Qdrant, real embedder) and in unit
tests (AsyncMock everything).

Ponytail:
  * Single class, one obvious way to call it.
  * No retries / dead-letter inside the pipeline — the worker job
    queue is the retry boundary. Raise, let the handler mark it failed.
  * No batching against Qdrant; the embed call already returns a
    single batch and ``upsert_chunks`` takes an iterable. Add a real
    batch size knob only if a single doc blows past the embed batch.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from qdrant_client.http import models
from sqlalchemy.ext.asyncio import AsyncSession

from rekanvault.evidence.chunker import Chunker
from rekanvault.evidence.embedding import EmbeddingService
from rekanvault.storage.document_repo import DocumentRepository
from rekanvault.storage.qdrant import QdrantStore

# Chunk-text display budget kept inline so the pipeline stays
# self-contained. Qdrant payload is fine with more, but the retrieval
# display layer truncates to 1k anyway — match the downstream ceiling.
CHUNK_TEXT_PAYLOAD_MAX_CHARS = 1000

# Local alias to keep the type narrow without importing the dataclass.
DocumentId = uuid.UUID
DocumentVersionId = uuid.UUID


class IndexingPipeline:
    """Chunk a version, embed the chunks, upsert to Qdrant; or deactivate."""

    def __init__(
        self,
        session: AsyncSession,
        chunker: Chunker,
        embed: EmbeddingService,
        qdrant: QdrantStore,
        doc_repo: DocumentRepository,
    ) -> None:
        self._session = session
        self._chunker = chunker
        self._embed = embed
        self._qdrant = qdrant
        self._doc_repo = doc_repo

    async def index_version(self, document_version_id: DocumentVersionId) -> int:
        """Chunk + embed + upsert one version. Returns chunks indexed."""
        version = await self._doc_repo.get_version(self._session, document_version_id)
        if version is None:
            return 0
        document = version.document

        chunks = await self._chunker.chunk_version(self._session, document_version_id)
        if not chunks:
            return 0

        texts = [c.content_text for c in chunks]
        vectors = self._embed.embed(texts)

        now_iso = datetime.now(UTC).isoformat()
        source_type = "unknown"
        try:
            if document.source is not None:
                source_type = document.source.provider
        except Exception:
            source_type = "unknown"
        points: list[dict[str, object]] = []
        for chunk, vector in zip(chunks, vectors, strict=True):
            points.append(
                {
                    "chunk_id": chunk.chunk_id,
                    "embedding": vector,
                    "payload": {
                        "workspace_id": str(chunk.workspace_id),
                        "document_id": str(document.id),
                        "version_id": str(document_version_id),
                        "chunk_text": chunk.content_text[:CHUNK_TEXT_PAYLOAD_MAX_CHARS],
                        "block_start": chunk.start_block_index,
                        "block_end": chunk.end_block_index,
                        "source_type": source_type,
                        "status": "active",
                        "created_at": now_iso,
                        "corpus_id": str(document.corpus_id) if document.corpus_id else None,
                    },
                }
            )

        await self._qdrant.upsert_chunks(points)
        return len(points)

    async def deactivate_version(self, document_version_id: DocumentVersionId) -> int:
        """Delete every Qdrant point tagged with this version_id.

        Returns 0 — Qdrant's delete-by-filter doesn't surface a count
        unless we ask for payload/vectors back, which we don't need.
        ponytail: return count only when a caller actually needs it.
        """
        version = await self._doc_repo.get_version(self._session, document_version_id)
        if version is None:
            return 0
        document = version.document

        await self._qdrant.delete_by_filter(
            models.Filter(
                must=[
                    models.FieldCondition(key="document_id", match=models.MatchValue(value=str(document.id))),
                    models.FieldCondition(key="version_id", match=models.MatchValue(value=str(document_version_id))),
                ]
            )
        )
        return 0

    async def handle_document_change(
        self,
        document_id: DocumentId,
        new_version_id: DocumentVersionId,
    ) -> None:
        """Index the new version, then deactivate every older one for the doc."""
        await self.index_version(new_version_id)
        old_versions = await self._doc_repo.list_versions_for_document(self._session, document_id)
        for old in old_versions:
            if old.id == new_version_id:
                continue
            await self.deactivate_version(old.id)


__all__ = ["CHUNK_TEXT_PAYLOAD_MAX_CHARS", "IndexingPipeline"]
