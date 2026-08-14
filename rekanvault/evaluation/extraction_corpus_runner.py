"""P5 full-corpus typed-memory extraction evaluation runner.

Sweeps every active document in a workspace: bulk-loads content blocks, chunks
in-process (structure-first), runs :class:`MemoryExtractor` over each chunk,
optionally persists memories and per-chunk failures, then reports aggregate
extraction statistics (memory count, type distribution, failure rate, and —
when writing — evidence-binding resolution).

The bulk-load path avoids the N+1 ``Chunker.chunk_version`` round-trips
(~4 queries per version), which cost ~175s over 186 versions on Supabase.

Usage::

    python -m rekanvault.evaluation.extraction_corpus_runner            # dry-run
    python -m rekanvault.evaluation.extraction_corpus_runner --write    # persist + verify bindings
    python -m rekanvault.evaluation.extraction_corpus_runner --json     # machine-readable
"""

from __future__ import annotations

import argparse
import asyncio
import time
import uuid
from collections import Counter
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.config import settings
from rekanvault.evidence.chunker import (
    _materialize,
    _maybe_split_oversized,
    _plan_chunks,
    _renumber,
)
from rekanvault.memory.extraction import MemoryExtractor
from rekanvault.memory.models import BaseTypedMemory
from rekanvault.storage.database import get_db_session, init_db
from rekanvault.storage.memory_repo import MemoryRepository
from rekanvault.storage.models import ContentBlock, Document, DocumentVersion


@dataclass(frozen=True)
class _ChunkJob:
    document_id: uuid.UUID
    document_version_id: uuid.UUID
    chunk_id: str
    text: str


@dataclass
class CorpusExtractionReport:
    workspace_id: str
    active_documents: int
    total_chunks: int
    chunks_ok: int
    chunks_failed: int
    total_memories: int
    type_distribution: dict[str, int]
    failure_codes: dict[str, int]
    elapsed_s: float
    bindings: dict[str, int] = field(default_factory=dict)

    @property
    def failure_rate(self) -> float:
        return self.chunks_failed / self.total_chunks if self.total_chunks else 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "workspace_id": self.workspace_id,
            "active_documents": self.active_documents,
            "total_chunks": self.total_chunks,
            "chunks_ok": self.chunks_ok,
            "chunks_failed": self.chunks_failed,
            "failure_rate": round(self.failure_rate, 4),
            "total_memories": self.total_memories,
            "memories_per_chunk": round(self.total_memories / self.total_chunks, 2) if self.total_chunks else 0.0,
            "type_distribution": dict(sorted(self.type_distribution.items())),
            "failure_codes": dict(self.failure_codes),
            "elapsed_s": round(self.elapsed_s, 1),
            "bindings": self.bindings,
        }


class ExtractionCorpusRunner:
    """Full-corpus extraction sweep + aggregate reporting (P5)."""

    def __init__(self, *, workspace_id: uuid.UUID, concurrency: int = 8) -> None:
        self.workspace_id = workspace_id
        self.concurrency = concurrency

    async def run(self, *, write: bool = False) -> CorpusExtractionReport:
        started = time.monotonic()
        init_db()

        async for session in get_db_session():
            jobs, active_docs = await self._load_and_chunk(session)
            break

        ok, failed = await self._extract(jobs)

        report = CorpusExtractionReport(
            workspace_id=str(self.workspace_id),
            active_documents=active_docs,
            total_chunks=len(jobs),
            chunks_ok=len(ok),
            chunks_failed=len(failed),
            total_memories=sum(len(memories) for _, memories in ok),
            type_distribution=dict(
                Counter(m.memory_type.value for _, memories in ok for m in memories)
            ),
            failure_codes=dict(Counter(code for _, code, _ in failed)),
            elapsed_s=time.monotonic() - started,
        )

        if write:
            async for session in get_db_session():
                await self._persist(session, ok, failed)
                report.bindings = await self._binding_resolution(session)
                break

        return report

    async def _load_and_chunk(self, session: AsyncSession) -> tuple[list[_ChunkJob], int]:
        docs = list(
            (
                await session.execute(
                    select(Document).where(
                        Document.workspace_id == self.workspace_id,
                        Document.status == "active",
                    )
                )
            ).scalars().all()
        )
        docs_by_id = {d.id: d for d in docs}

        versions = list(
            (
                await session.execute(
                    select(DocumentVersion)
                    .where(DocumentVersion.workspace_id == self.workspace_id)
                    .order_by(DocumentVersion.document_id, DocumentVersion.version_number.desc())
                )
            ).scalars().all()
        )
        latest: dict[uuid.UUID, DocumentVersion] = {}
        for version in versions:
            latest.setdefault(version.document_id, version)

        active_latest = [(doc.id, latest[doc.id]) for doc in docs if doc.id in latest]
        version_ids = [version.id for _, version in active_latest]
        if not version_ids:
            return [], 0

        blocks = list(
            (
                await session.execute(
                    select(ContentBlock)
                    .where(ContentBlock.document_version_id.in_(version_ids))
                    .order_by(ContentBlock.document_version_id, ContentBlock.block_index)
                )
            ).scalars().all()
        )
        blocks_by_version: dict[uuid.UUID, list[ContentBlock]] = {}
        for block in blocks:
            blocks_by_version.setdefault(block.document_version_id, []).append(block)

        jobs: list[_ChunkJob] = []
        for doc_id, version in active_latest:
            document = docs_by_id[doc_id]
            version_blocks = blocks_by_version.get(version.id, [])
            if not version_blocks:
                continue
            split = _maybe_split_oversized(version_blocks)
            planned = _plan_chunks(split)
            chunks = _renumber(
                [
                    _materialize(p, document.external_id, version.version_number, version.id, self.workspace_id)
                    for p in planned
                ]
            )
            jobs.extend(
                _ChunkJob(doc_id, version.id, chunk.chunk_id, chunk.content_text) for chunk in chunks
            )

        return jobs, len(docs)

    async def _extract(
        self, jobs: list[_ChunkJob]
    ) -> tuple[list[tuple[_ChunkJob, list[BaseTypedMemory]]], list[tuple[_ChunkJob, str, str]]]:
        extractor = MemoryExtractor()
        semaphore = asyncio.Semaphore(self.concurrency)
        ok: list[tuple[_ChunkJob, list[BaseTypedMemory]]] = []
        failed: list[tuple[_ChunkJob, str, str]] = []

        async def run_one(job: _ChunkJob) -> None:
            async with semaphore:
                try:
                    memories = await extractor.extract(
                        chunk_text=job.text,
                        chunk_id=job.chunk_id,
                        document_id=job.document_id,
                        workspace_id=self.workspace_id,
                    )
                    ok.append((job, memories))
                except Exception as exc:
                    failed.append((job, str(getattr(exc, "code", type(exc).__name__)), str(exc)[:512]))

        try:
            await asyncio.gather(*(run_one(job) for job in jobs))
        finally:
            await extractor.close()

        return ok, failed

    async def _persist(
        self,
        session: AsyncSession,
        ok: list[tuple[_ChunkJob, list[BaseTypedMemory]]],
        failed: list[tuple[_ChunkJob, str, str]],
    ) -> None:
        repo = MemoryRepository(session)
        for job, memories in ok:
            for memory in memories:
                await repo.create_memory(
                    self.workspace_id,
                    memory,
                    document_id=job.document_id,
                    version_id=job.document_version_id,
                )
        for job, code, message in failed:
            await repo.record_extraction_failure(
                workspace_id=self.workspace_id,
                document_id=job.document_id,
                document_version_id=job.document_version_id,
                chunk_id=job.chunk_id,
                error_code=code,
                error_message=message,
            )

    async def _binding_resolution(self, session: AsyncSession) -> dict[str, int]:
        checks = {
            "bindings_total": "select count(*) from memory_evidence_bindings",
            "bindings_no_doc": "select count(*) from memory_evidence_bindings where document_id is null",
            "bindings_no_ver": "select count(*) from memory_evidence_bindings where version_id is null",
            "dangling_doc": (
                "select count(*) from memory_evidence_bindings b"
                " where not exists (select 1 from documents d where d.id = b.document_id)"
            ),
            "dangling_ver": (
                "select count(*) from memory_evidence_bindings b"
                " where not exists (select 1 from document_versions v where v.id = b.version_id)"
            ),
            "memories_no_binding": (
                "select count(*) from typed_memories m"
                " where m.workspace_id = :ws"
                " and not exists (select 1 from memory_evidence_bindings b where b.memory_id = m.id)"
            ),
        }
        result: dict[str, int] = {}
        for name, query in checks.items():
            result[name] = int((await session.execute(text(query), {"ws": self.workspace_id})).scalar_one())
        return result


def _format_report(report: CorpusExtractionReport) -> str:
    memories_per_chunk = report.total_memories / report.total_chunks if report.total_chunks else 0.0
    lines = [
        f"Workspace:            {report.workspace_id}",
        f"Active documents:     {report.active_documents}",
        f"Chunks:               {report.total_chunks} (ok={report.chunks_ok}, failed={report.chunks_failed})",
        f"Failure rate:         {report.failure_rate*100:.2f}%",
        f"Total memories:       {report.total_memories}",
        f"Memories / chunk:     {memories_per_chunk:.2f}",
        f"Elapsed:              {report.elapsed_s:.1f}s",
    ]
    if report.type_distribution:
        lines.append("Type distribution:")
        for memory_type, count in sorted(report.type_distribution.items()):
            lines.append(f"  {memory_type:<14} {count}")
    if report.failure_codes:
        lines.append("Failure codes:")
        for code, count in sorted(report.failure_codes.items()):
            lines.append(f"  {code:<24} {count}")
    if report.bindings:
        lines.append("Evidence binding resolution:")
        for name, count in report.bindings.items():
            lines.append(f"  {name:<24} {count}")
    return "\n".join(lines)


def _run_cli() -> None:
    parser = argparse.ArgumentParser(description="RekanVault full-corpus extraction evaluation (P5)")
    parser.add_argument("--workspace-id", default=settings.RV_PILOT_WORKSPACE_ID, help="Workspace UUID to sweep")
    parser.add_argument("--concurrency", type=int, default=8, help="Max concurrent LLM calls (default: 8)")
    parser.add_argument("--write", action="store_true", help="Persist memories + failures and verify bindings")
    parser.add_argument("--json", action="store_true", help="Emit the report as JSON")
    args = parser.parse_args()

    runner = ExtractionCorpusRunner(
        workspace_id=uuid.UUID(args.workspace_id),
        concurrency=args.concurrency,
    )
    report = asyncio.run(runner.run(write=args.write))

    if args.json:
        import json

        print(json.dumps(report.to_dict(), indent=2))
    else:
        print(_format_report(report))


if __name__ == "__main__":
    _run_cli()
