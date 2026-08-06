"""
Document persistence repository (P3 — ingestion persistence layer).

Maps ``NormalizedDocument`` (connector output contract) to durable
``Document`` / ``DocumentVersion`` / ``ContentBlock`` storage tables.
Upsert keyed on the ``(workspace_id, source_id, external_id)`` unique
constraint: new docs get a single row + version, changed docs get a new
version + new content blocks, unchanged docs are skipped.

Ponytail: one class, one job, no abstract Factory. Callers own the
transaction (``commit``/``rollback``); the repo only stages and flushes.
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from rekanvault.contracts.documents import DocumentBlock as Block
from rekanvault.contracts.documents import NormalizedDocument
from rekanvault.storage.models import (
    ContentBlock,
    Document,
    DocumentVersion,
)


def _flatten_blocks(normalized: NormalizedDocument) -> list[Block]:
    """Return the blocks of the active version (or the first version if
    ``active_version_id`` doesn't match — the contract allows it)."""
    for version in normalized.versions:
        if version.version_id == normalized.active_version_id:
            return list(version.blocks)
    if normalized.versions:
        return list(normalized.versions[0].blocks)
    return []


def _fingerprint_for(normalized: NormalizedDocument) -> str:
    """Stable identity hash (title + locator + block shape) — used to skip
    writes when nothing material changed."""
    block_sig = "|".join(f"{b.block_id}:{b.block_type}:{len(b.content)}" for b in _flatten_blocks(normalized))
    payload = f"{normalized.active_version_id}|{normalized.title}|{normalized.locator.native_id}|{block_sig}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _content_hash_for(blocks: list[Block]) -> str:
    """Hash of the joined content — the "did the text change" signal."""
    joined = "\n".join(b.content for b in blocks)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


def _byte_size_of(blocks: list[Block]) -> int:
    """Sum of block content byte length."""
    return sum(len(b.content.encode("utf-8")) for b in blocks)


class DocumentRepository:
    """Persists ``NormalizedDocument`` to durable storage. Every method
    takes an explicit ``workspace_id`` — RLS-ready."""

    async def get_by_external_id(
        self,
        session: AsyncSession,
        workspace_id: uuid.UUID,
        source_id: uuid.UUID,
        external_id: str,
    ) -> Document | None:
        stmt = select(Document).where(
            Document.workspace_id == workspace_id,
            Document.source_id == source_id,
            Document.external_id == external_id,
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def upsert_document(
        self,
        session: AsyncSession,
        workspace_id: uuid.UUID,
        source_id: uuid.UUID,
        normalized: NormalizedDocument,
    ) -> Document:
        """Insert or update a document + its content blocks.

        No row → create Document + DocumentVersion + ContentBlocks.
        Row + unchanged fingerprint → return existing (skip write).
        Row + changed fingerprint → bump version, write new version + blocks.
        """
        existing = await self.get_by_external_id(
            session=session,
            workspace_id=workspace_id,
            source_id=source_id,
            external_id=normalized.locator.native_id,
        )

        blocks = _flatten_blocks(normalized)
        fingerprint = _fingerprint_for(normalized)
        content_hash = _content_hash_for(blocks)
        byte_size = _byte_size_of(blocks)
        mime_type = normalized.locator.mime_type or "application/octet-stream"
        storage_path = (normalized.metadata or {}).get("storage_path")

        if existing is None:
            return await self._insert_new(
                session=session,
                workspace_id=workspace_id,
                source_id=source_id,
                normalized=normalized,
                mime_type=mime_type,
                fingerprint=fingerprint,
                content_hash=content_hash,
                byte_size=byte_size,
                blocks=blocks,
                storage_path=storage_path,
            )

        latest = await self._latest_version(session, existing.id)
        if latest is not None and latest.fingerprint == fingerprint:
            return existing

        return await self._insert_new_version(
            session=session,
            document=existing,
            latest_version=latest,
            workspace_id=workspace_id,
            normalized=normalized,
            mime_type=mime_type,
            fingerprint=fingerprint,
            content_hash=content_hash,
            byte_size=byte_size,
            blocks=blocks,
            storage_path=storage_path,
        )

    async def _insert_new(
        self,
        session: AsyncSession,
        workspace_id: uuid.UUID,
        source_id: uuid.UUID,
        normalized: NormalizedDocument,
        mime_type: str,
        fingerprint: str,
        content_hash: str,
        byte_size: int,
        blocks: list[Block],
        storage_path: str | None,
    ) -> Document:
        document = Document(
            id=uuid.uuid4(),
            workspace_id=workspace_id,
            source_id=source_id,
            external_id=normalized.locator.native_id,
            title=normalized.title,
            mime_type=mime_type,
        )
        session.add(document)
        await session.flush()

        version = DocumentVersion(
            id=uuid.uuid4(),
            document_id=document.id,
            workspace_id=workspace_id,
            version_number=1,
            fingerprint=fingerprint,
            content_hash=content_hash,
            byte_size=byte_size,
            storage_path=storage_path,
        )
        session.add(version)
        await session.flush()

        for idx, block in enumerate(blocks):
            session.add(
                ContentBlock(
                    id=uuid.uuid4(),
                    document_version_id=version.id,
                    workspace_id=workspace_id,
                    block_index=idx,
                    block_type=block.block_type,
                    content_text=block.content,
                    metadata_=dict(block.metadata or {}),
                )
            )

        # Enqueue an indexing job for the worker. Direct enqueue is the
        # ponytail move: a transactional outbox adds a second table +
        # second consumer for the single-process pilot. Swap to
        # ``create_outbox_event`` when cross-service delivery matters.
        from rekanvault.storage.jobs import JobQueueManager

        await JobQueueManager(session).enqueue_job(
            workspace_id=workspace_id,
            job_type="index_document_version",
            payload={
                "document_version_id": str(version.id),
                "document_id": str(document.id),
            },
        )

        return document

    async def _insert_new_version(
        self,
        session: AsyncSession,
        document: Document,
        latest_version: DocumentVersion | None,
        workspace_id: uuid.UUID,
        normalized: NormalizedDocument,
        mime_type: str,
        fingerprint: str,
        content_hash: str,
        byte_size: int,
        blocks: list[Block],
        storage_path: str | None,
    ) -> Document:
        next_number = (latest_version.version_number + 1) if latest_version is not None else 1

        document.title = normalized.title
        document.mime_type = mime_type

        version = DocumentVersion(
            id=uuid.uuid4(),
            document_id=document.id,
            workspace_id=workspace_id,
            version_number=next_number,
            fingerprint=fingerprint,
            content_hash=content_hash,
            byte_size=byte_size,
            storage_path=storage_path,
        )
        session.add(version)
        await session.flush()

        for idx, block in enumerate(blocks):
            session.add(
                ContentBlock(
                    id=uuid.uuid4(),
                    document_version_id=version.id,
                    workspace_id=workspace_id,
                    block_index=idx,
                    block_type=block.block_type,
                    content_text=block.content,
                    metadata_=dict(block.metadata or {}),
                )
            )

        # ponytail: same trade-off as _insert_new — direct enqueue now,
        # outbox when cross-service delivery is needed.
        from rekanvault.storage.jobs import JobQueueManager

        await JobQueueManager(session).enqueue_job(
            workspace_id=workspace_id,
            job_type="index_document_version",
            payload={
                "document_version_id": str(version.id),
                "document_id": str(document.id),
            },
        )

        return document

    async def _latest_version(
        self,
        session: AsyncSession,
        document_id: uuid.UUID,
    ) -> DocumentVersion | None:
        stmt = (
            select(DocumentVersion)
            .where(DocumentVersion.document_id == document_id)
            .order_by(DocumentVersion.version_number.desc())
            .limit(1)
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_versions_for_document(
        self,
        session: AsyncSession,
        document_id: uuid.UUID,
    ) -> list[DocumentVersion]:
        """All versions of a document, newest first.

        Used by the indexing pipeline to deactivate older versions when
        a new one is written. Ordered so callers can short-circuit
        ``versions[0]`` as the latest.
        """
        stmt = (
            select(DocumentVersion)
            .where(DocumentVersion.document_id == document_id)
            .order_by(DocumentVersion.version_number.desc())
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def get_latest_version(
        self,
        session: AsyncSession,
        document_id: uuid.UUID,
    ) -> DocumentVersion | None:
        """Public alias for the latest version of a document.

        Same query as the internal ``_latest_version``; exposed because
        the worker deactivation handler needs to find the current head
        without a version_id in the payload.
        """
        return await self._latest_version(session, document_id)

    async def deactivate_document(
        self,
        session: AsyncSession,
        document_id: uuid.UUID,
    ) -> None:
        """Mark a document as removed from its upstream source (P4-T4)."""
        stmt = select(Document).where(Document.id == document_id)
        result = await session.execute(stmt)
        doc = result.scalar_one_or_none()
        if doc is not None:
            doc.status = "deactivated"
            doc.deactivated_at = datetime.now(timezone.utc)

    async def get_version(
        self,
        session: AsyncSession,
        document_version_id: uuid.UUID,
    ) -> DocumentVersion | None:
        """Return a ``DocumentVersion`` with its ``document`` relationship
        eagerly loaded, so callers (e.g. the chunker) can read
        ``external_id`` and ``version_number`` without a second round-trip."""
        stmt = (
            select(DocumentVersion)
            .where(DocumentVersion.id == document_version_id)
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_content_blocks(
        self,
        session: AsyncSession,
        document_version_id: uuid.UUID,
    ) -> list[ContentBlock]:
        """Return all content blocks for a version, ordered by block_index.

        Used by the chunking pipeline to read raw blocks for processing."""
        stmt = (
            select(ContentBlock)
            .where(ContentBlock.document_version_id == document_version_id)
            .order_by(ContentBlock.block_index)
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def list_by_source(
        self,
        session: AsyncSession,
        workspace_id: uuid.UUID,
        source_id: uuid.UUID,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Document]:
        stmt = (
            select(Document)
            .where(Document.workspace_id == workspace_id, Document.source_id == source_id)
            .order_by(Document.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())


__all__ = ["DocumentRepository"]
