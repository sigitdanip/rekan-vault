"""
Qdrant Cloud client + collection management (P4 — retrieval index).

`QdrantStore` is the thin async wrapper around ``AsyncQdrantClient`` for
the pilot retrieval collection. It is responsible for:

* Ensuring the collection exists with the locked vector shape
  (named "dense" vector, 1024-dim, Cosine — ``RV-DEC-P4-0002``) and
  payload indexes for the filter fields surfaced in P4-T3.
* Upserting chunk vectors with their display payload.
* Filtered deletes (used by reindex/reconciliation).
* A rebuild skeleton (drop + recreate) so callers can replay every
  chunk from Postgres after a wipe.

Lifecycle is owned by the caller: instantiate once, ``await close()``
on shutdown. ADR ``RV-DEC-P4-0001`` (Qdrant Cloud) is the source of
truth for *where*; ``RV-DEC-0009`` (Qdrant is a disposable index) is
the source of truth for *how* the rebuild path is shaped.

Ponytail: one class, no factory, no interface. The point-vector shape
is locked at the ADR level — anything that needs a second vector name
(e.g. sparse) will get a sibling class rather than generalizing this
one.
"""

from __future__ import annotations

from typing import Any, Iterable

from qdrant_client import AsyncQdrantClient
from qdrant_client.http import models

from apps.api.config import Settings

# Filter fields per P4-T3. Keyword fields are equality / `IN` filters;
# `created_at` is a datetime range filter. Module constant so tests can
# assert on the exact set without scraping a method body.
PAYLOAD_INDEXES: tuple[tuple[str, models.PayloadSchemaType], ...] = (
    ("workspace_id", models.PayloadSchemaType.KEYWORD),
    ("document_id", models.PayloadSchemaType.KEYWORD),
    ("version_id", models.PayloadSchemaType.KEYWORD),
    ("source_type", models.PayloadSchemaType.KEYWORD),
    ("status", models.PayloadSchemaType.KEYWORD),
    ("created_at", models.PayloadSchemaType.DATETIME),
    ("corpus_id", models.PayloadSchemaType.KEYWORD),
)

# Display payload keys copied verbatim from each chunk dict on upsert.
# Anything not in this set is silently dropped — the index never needs
# vector-side metadata beyond the filter + display fields.
PAYLOAD_KEYS: tuple[str, ...] = (
    "workspace_id",
    "document_id",
    "version_id",
    "block_type",
    "doc_title",
    "source_type",
    "status",
    "created_at",
    "corpus_id",
    "chunk_text",
)

DenseVectorName = "dense"


class QdrantStore:
    """Async client + collection manager for the pilot retrieval index."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._collection = settings.RV_QDRANT_COLLECTION
        # ``AsyncQdrantClient`` accepts both seconds (int/float) and a
        # ``datetime.timedelta``; the int from settings is seconds.
        self._client = AsyncQdrantClient(
            url=settings.RV_QDRANT_URL,
            api_key=settings.RV_QDRANT_API_KEY,
            timeout=settings.RV_QDRANT_TIMEOUT_SECONDS,
        )

    @property
    def collection_name(self) -> str:
        return self._collection

    @property
    def client(self) -> AsyncQdrantClient:
        """Escape hatch for callers that need methods this class doesn't
        wrap yet (search, scroll, etc.). Keep the surface narrow."""
        return self._client

    async def ensure_collection(self) -> None:
        """Create the collection + payload indexes if they don't exist.
        Idempotent — safe to call on every worker boot."""
        if not await self._client.collection_exists(self._collection):
            vectors_config: dict[str, models.VectorParams] = {
                DenseVectorName: models.VectorParams(
                    size=self._settings.RV_EMBEDDING_DIMENSIONS,
                    distance=models.Distance.COSINE,
                ),
            }
            await self._client.create_collection(
                collection_name=self._collection,
                vectors_config=vectors_config,
            )

        # Indexes are cheap to re-issue — Qdrant returns "already
        # exists" for matching requests. Re-applying also covers the
        # case where the collection existed but indexes were dropped.
        for field_name, schema in PAYLOAD_INDEXES:
            await self._client.create_payload_index(
                collection_name=self._collection,
                field_name=field_name,
                field_schema=schema,
            )

    async def upsert_chunks(self, chunks: Iterable[dict[str, Any]]) -> None:
        """Upsert a batch of chunk vectors.

        Each chunk dict must contain:

        * ``chunk_id`` — the chunk locator string
          (``{doc_external_id}#v{n}#chunk_{seq}`` per ``RV-DEC-P4-0004``).
        * ``embedding`` — a sequence of floats, length
          ``settings.RV_EMBEDDING_DIMENSIONS``.

        All keys in :data:`PAYLOAD_KEYS` are copied from the chunk if
        present; missing keys are silently dropped. An empty batch is a
        no-op.
        """
        points: list[models.PointStruct] = []
        for chunk in chunks:
            chunk_id = chunk["chunk_id"]
            embedding = chunk["embedding"]
            payload = {key: chunk[key] for key in PAYLOAD_KEYS if key in chunk}
            points.append(
                models.PointStruct(
                    id=chunk_id,
                    vector={DenseVectorName: embedding},
                    payload=payload,
                )
            )
        if not points:
            return
        await self._client.upsert(collection_name=self._collection, points=points)

    async def delete_by_filter(self, filter_: models.Filter) -> None:
        """Delete every point matching ``filter_``."""
        await self._client.delete(
            collection_name=self._collection,
            points_selector=filter_,
        )

    async def rebuild_from_postgres(self) -> None:
        """Skeleton for the full rebuild path (P4-T7).

        Current behavior: drop the collection and recreate it empty
        with the locked vector shape + payload indexes, so the caller
        (CLI or worker) can then re-embed and re-upsert every chunk
        from Postgres. The actual re-embed loop will be added once the
        chunker and embedding service are wired in; this method is the
        "wipe + recreate" half of that flow.

        Ponytail: skeleton on purpose. Fleshing this out before the
        chunker exists is speculation — the wipe side is what we need
        now, the re-embed side will follow the chunker.
        """
        if await self._client.collection_exists(self._collection):
            await self._client.delete_collection(self._collection)
        await self.ensure_collection()

    async def close(self) -> None:
        """Close the underlying HTTP/gRPC client. Safe to call once."""
        await self._client.close()


__all__ = [
    "DenseVectorName",
    "PAYLOAD_INDEXES",
    "PAYLOAD_KEYS",
    "QdrantStore",
    "models",
]
