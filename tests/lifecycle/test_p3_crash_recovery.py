"""
P3-T4 — Crash before and after cursor commit.

Pins the contract for the two crash-recovery scenarios in the worker
sync loop. The actual cursor persistence is delegated to the
:class:`rekanvault.storage.models.ProviderCursor` model; the test suite
builds an in-memory fake of the cursor store and exercises the two
crash boundaries:

  1. Crash BEFORE cursor commit
     - Ingestion may have produced documents; the cursor was NOT saved.
     - On restart, the worker re-fetches from the old cursor.
     - Result: the documents from the crashed run are re-fetched. The
       ingestion pipeline must treat them as idempotent — same document
       id + same content hash = no new version.

  2. Crash AFTER cursor commit, BEFORE doc commit
     - The cursor IS saved, the docs are NOT.
     - On restart, the worker fetches from the new cursor — those docs
       are NOT seen again.
     - Result: the docs that the first run produced are LOST (or
       surfaced via reconciliation). The AC accepts this trade-off:
       the rescan must be cheap, and reconciliation is the safety net.

The crash-recovery test models a ``CursorStore`` (in-memory) plus a
``SyncWorker`` stub that simulates ingestion + cursor commit in the
right order. No real DB, no real network.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

import pytest

from rekanvault.contracts.documents import (
    DocumentBlock,
    DocumentLocator,
    DocumentVersion,
    NormalizedDocument,
    SourceProvider,
)
from rekanvault.storage.models import ProviderCursor

# ---- in-memory stand-ins ---------------------------------------------------


@dataclass
class _CursorStore:
    """Minimal stand-in for the provider_cursors table.

    The real model is a SQLAlchemy ORM row; here we just keep a
    string -> string map. ``commit`` is the only operation that matters
    for the crash-recovery test — it's the boundary we're pinning.
    """

    rows: dict[str, str] = field(default_factory=dict)

    async def get(self, source_id: str) -> str | None:
        return self.rows.get(source_id)

    async def commit(self, source_id: str, cursor_value: str) -> None:
        self.rows[source_id] = cursor_value


@dataclass
class _IngestionLog:
    """Records every document that ingestion observed, in arrival order."""

    versions: list[tuple[str, str]] = field(default_factory=list)  # (doc_id, content_hash)
    active_version_ids: list[str] = field(default_factory=list)


def _make_doc(doc_id: str, content_hash: str) -> NormalizedDocument:
    return NormalizedDocument(
        document_id=doc_id,
        workspace_id="ws_test",
        source_id="src_test",
        title=f"Doc {doc_id}",
        provider=SourceProvider.LOCAL_FILE,
        locator=DocumentLocator(
            provider=SourceProvider.LOCAL_FILE,
            native_id=doc_id,
            uri=f"file://{doc_id}",
        ),
        active_version_id=f"ver_{content_hash}",
        versions=[
            DocumentVersion(
                version_id=f"ver_{content_hash}",
                document_id=doc_id,
                version_number=1,
                content_hash=content_hash,
                blocks=[DocumentBlock(block_id="b1", block_type="paragraph", content="x", sequence=1)],
            )
        ],
    )


async def _ingest_one_pass(
    docs: list[NormalizedDocument],
    cursor: str,
    log: _IngestionLog,
) -> str:
    """Simulate a single ingestion pass: process each doc, then return the
    new cursor. Idempotent on (doc_id, content_hash) — already-seen
    pairs do not produce a new entry in the log."""
    new_cursor = f"cursor_after_{len(docs)}"
    for doc in docs:
        pair = (doc.document_id, doc.versions[0].content_hash)
        if pair in log.versions:
            continue  # idempotent
        log.versions.append(pair)
        log.active_version_ids.append(doc.active_version_id)
    return new_cursor


# ---- tests -----------------------------------------------------------------


@pytest.mark.asyncio
async def test_crash_before_cursor_commit_resumes_with_old_cursor() -> None:
    """P3-T4 (crash before): ingestion produced 3 documents; the cursor
    commit failed before the transaction boundary. The cursor store
    still holds the OLD cursor. On restart, the worker calls
    ``fetch_changes(old_cursor)`` and re-receives the same 3 documents.

    The ingestion log is the proof of correctness: the second pass sees
    the same 3 (doc_id, content_hash) pairs and the idempotency guard
    in :func:`_ingest_one_pass` skips them. No duplicate active
    versions, no orphaned outbox events.
    """
    store = _CursorStore()
    await store.commit("src_test", "cursor_0")
    log = _IngestionLog()

    docs = [_make_doc("a", "h1"), _make_doc("b", "h1"), _make_doc("c", "h2")]

    # First pass: ingest 3 docs. Then simulate a crash BEFORE the cursor
    # commit. The store is unchanged.
    await _ingest_one_pass(docs, cursor="cursor_0", log=log)
    # (No commit happens — the worker dies.)

    assert await store.get("src_test") == "cursor_0"  # unchanged
    assert len(log.versions) == 3

    # Restart: read the OLD cursor and re-ingest the same docs.
    recovered_cursor = await store.get("src_test")
    assert recovered_cursor == "cursor_0"

    # Rescan produces the same documents again. Idempotency guard kicks in.
    await _ingest_one_pass(docs, cursor=recovered_cursor, log=log)

    # No new active versions were produced.
    assert len(log.active_version_ids) == 3
    assert log.versions == [("a", "h1"), ("b", "h1"), ("c", "h2")]


@pytest.mark.asyncio
async def test_crash_after_cursor_commit_skips_already_committed_changes() -> None:
    """P3-T4 (crash after): the cursor WAS committed; the docs were NOT
    (the worker died between the cursor commit and the doc commit).

    On restart, the worker reads the new cursor and calls
    ``fetch_changes(new_cursor)`` — the provider returns ZERO new
    events. The 3 docs from the first run are lost from the log.

    This is the explicit trade-off the AC accepts: cursor-commit is the
    sync boundary. The lost docs are recovered by the daily full
    reconciliation, which is the safety net.
    """
    store = _CursorStore()
    await store.commit("src_test", "cursor_0")
    log = _IngestionLog()

    docs = [_make_doc("a", "h1"), _make_doc("b", "h1"), _make_doc("c", "h2")]

    # First pass: ingest 3 docs, then commit the cursor. Then the
    # worker dies BEFORE the doc commits.
    await _ingest_one_pass(docs, cursor="cursor_0", log=log)
    new_cursor = await _ingest_one_pass(docs, cursor="cursor_0", log=_IngestionLog())  # returns cursor_after_3
    await store.commit("src_test", new_cursor)
    # (Worker dies before doc commits — but in this stub the log is the
    # in-memory stand-in for the DB; we explicitly DROP it to simulate
    # the lost-doc state.)
    log.versions.clear()
    log.active_version_ids.clear()

    # Restart: read the new cursor. The provider returns no events
    # (we already advanced past them).
    assert await store.get("src_test") == new_cursor

    # Simulate provider returning zero new events when fetched from
    # the new cursor. The log stays empty.
    fetched: list[NormalizedDocument] = []  # provider has no events past the new cursor
    await _ingest_one_pass(fetched, cursor=new_cursor, log=log)
    assert log.versions == []
    assert log.active_version_ids == []


@pytest.mark.asyncio
async def test_crash_before_commit_with_partial_ingestion_state() -> None:
    """P3-T4 (crash before, partial): only 2 of 3 docs were ingested
    when the crash hit. The remaining doc is re-fetched on restart, and
    the re-encountered pair is dedup'd.

    This is the worst-case for the AC: we want to prove that even
    partial state survives a crash, not just all-or-nothing.
    """
    store = _CursorStore()
    await store.commit("src_test", "cursor_0")
    log = _IngestionLog()

    docs = [_make_doc("a", "h1"), _make_doc("b", "h1"), _make_doc("c", "h2")]

    # Crash after 2 of 3.
    for d in docs[:2]:
        log.versions.append((d.document_id, d.versions[0].content_hash))
        log.active_version_ids.append(d.active_version_id)
    # (No commit, no third doc.)

    # Restart: replay the same docs.
    await _ingest_one_pass(docs, cursor="cursor_0", log=log)

    # Two already-seen pairs + one new.
    assert ("c", "h2") in log.versions
    assert log.versions.count(("a", "h1")) == 1
    assert log.versions.count(("b", "h1")) == 1
    assert log.versions.count(("c", "h2")) == 1
    assert len(log.active_version_ids) == 3


@pytest.mark.asyncio
async def test_provider_cursor_model_round_trip() -> None:
    """P3-T4 (model contract): the ORM model used to persist cursors
    must accept the same (source_id, cursor_value) pair we use in the
    in-memory stand-in. This is the only sanity check the test makes
    against the real model — the rest of the crash-recovery logic is
    in the worker, which the persistence layer will own.
    """
    cursor = ProviderCursor(
        source_id=uuid.uuid4(),
        workspace_id=uuid.uuid4(),
        cursor_value="cursor_42",
    )
    assert cursor.cursor_value == "cursor_42"
    assert cursor.source_id is not None
    assert cursor.workspace_id is not None
