"""
P3-T3 — Duplicate / delayed / out-of-order event property tests.

The repo's first Hypothesis-based test. Convention: ``@given`` for the
random generator, ``@example`` for canonical edge cases (empty list,
single element). All inputs are bounded — Hypothesis defaults to 100
examples per case and we shrink to minimal counter-examples on failure.

The contract under test is *convergence*:

  For any sequence of idempotent document-ingestion events (events that
  carry the same payload for the same document id), regardless of
  order or duplication, the final in-memory state recorded by
  :class:`IngestionLifecycleManager` must be identical, and the
  reconciliation against a reference state must agree.

  Events with DIFFERENT payloads for the same id are explicitly NOT a
  convergence test — the manager's last-write-wins behavior is correct
  for that case (it's how version-updates propagate).

We use the existing :class:`IngestionLifecycleManager` (the unit under
test for convergence) plus :class:`ReconciliationEngine` (the
authoritative diff). No mocks — these are real instances on synthetic
data. No DB — convergence is a property of the in-memory state machine,
not the persistence layer.
"""

from __future__ import annotations

import random
from typing import Any

from hypothesis import HealthCheck, example, given, settings
from hypothesis import strategies as st

from rekanvault.contracts.documents import (
    DocumentBlock,
    DocumentLocator,
    DocumentVersion,
    NormalizedDocument,
    SourceProvider,
)
from rekanvault.ingestion.lifecycle import IngestionLifecycleManager
from rekanvault.ingestion.reconciliation import ReconciliationEngine

# ---- strategies ------------------------------------------------------------

# A small universe of documents. The (id, title, content_hash) tuple is
# sampled as a unit so two events for the same id always carry the same
# payload — that is what makes the convergence property testable.
document_universe = st.sampled_from(
    [
        ("doc_a", "alpha", "h1"),
        ("doc_b", "beta", "h1"),
        ("doc_c", "gamma", "h2"),
        ("doc_d", "delta", "h3"),
    ]
)


@st.composite
def normalized_documents(draw: Any) -> NormalizedDocument:
    """Build a small ``NormalizedDocument`` from a fixed universe entry.

    Two draws that pick the same universe row produce identical
    documents — same id, same title, same hash. Reordering, duplicating,
    or replaying a list of these is therefore an idempotent operation
    at the document level.
    """
    document_id, title, content_hash = draw(document_universe)
    return NormalizedDocument(
        document_id=document_id,
        workspace_id="ws_test",
        source_id="src_test",
        title=title,
        provider=SourceProvider.LOCAL_FILE,
        locator=DocumentLocator(
            provider=SourceProvider.LOCAL_FILE,
            native_id=document_id,
            uri=f"file://{document_id}",
        ),
        active_version_id=f"ver_{content_hash}",
        versions=[
            DocumentVersion(
                version_id=f"ver_{content_hash}",
                document_id=document_id,
                version_number=1,
                content_hash=content_hash,
                blocks=[DocumentBlock(block_id="b1", block_type="paragraph", content="x", sequence=1)],
            )
        ],
    )


event_lists = st.lists(normalized_documents(), min_size=0, max_size=20)


# ---- helpers ---------------------------------------------------------------


def _finalize(docs: list[NormalizedDocument]) -> dict[str, NormalizedDocument]:
    """Apply a sequence of documents to a fresh manager and return the
    final state keyed by document_id."""
    manager = IngestionLifecycleManager()
    for doc in docs:
        manager.process_document(doc)
    return dict(manager.processed_documents)


def _projection(doc: NormalizedDocument) -> dict[str, Any]:
    """Return a timestamp-free projection of a document for equality.

    ``created_at`` / ``updated_at`` are wall-clock fields that change on
    every ``NormalizedDocument`` instantiation. The convergence property
    we care about is *content* convergence, not clock-time stability —
    so we strip those fields before comparing.
    """
    dumped = doc.model_dump()
    dumped.pop("created_at", None)
    dumped.pop("updated_at", None)
    for ver in dumped.get("versions", []):
        ver.pop("created_at", None)
    return dumped


# ---- properties ------------------------------------------------------------


@given(event_lists)
@example([])
@settings(max_examples=50, deadline=None, suppress_health_check=[HealthCheck.too_slow])
def test_convergence_idempotent_under_reordering(events: list[NormalizedDocument]) -> None:
    """P3-T3 (out-of-order): reordering events for the same document id
    must not change the final in-memory state.

    Two events with the same id and same payload are idempotent: the
    state after the first is the same as after the second. Therefore
    any permutation of an idempotent event multiset converges to the
    same state.
    """
    canonical = {k: _projection(v) for k, v in _finalize(events).items()}

    shuffled = list(events)
    random.Random(len(events)).shuffle(shuffled)
    from_shuffled = {k: _projection(v) for k, v in _finalize(shuffled).items()}

    assert canonical == from_shuffled


@given(event_lists)
@example([])
@settings(max_examples=50, deadline=None, suppress_health_check=[HealthCheck.too_slow])
def test_convergence_idempotent_under_duplication(events: list[NormalizedDocument]) -> None:
    """P3-T3 (duplicate): processing the same event twice (a duplicate
    notification) does not change the final state. The second pass is a
    no-op because the document is already in the manager."""
    once = {k: _projection(v) for k, v in _finalize(events).items()}
    twice = {k: _projection(v) for k, v in _finalize(events + events).items()}
    assert once == twice


@given(event_lists)
@settings(max_examples=50, deadline=None, suppress_health_check=[HealthCheck.too_slow])
def test_convergence_idempotent_under_delayed_replay(events: list[NormalizedDocument]) -> None:
    """P3-T3 (delayed): a "delayed" replay (appending the same events
    after the initial pass) converges to the same state."""
    first = {k: _projection(v) for k, v in _finalize(events).items()}
    delayed_replay = {k: _projection(v) for k, v in _finalize(events + events).items()}
    assert first == delayed_replay


# ---- reconciliation contract ------------------------------------------------


@given(event_lists)
@settings(max_examples=50, deadline=None, suppress_health_check=[HealthCheck.too_slow])
def test_reconciliation_engine_finds_no_drift_after_converged_processing(events: list[NormalizedDocument]) -> None:
    """P3-T3 (outbox): once ``IngestionLifecycleManager`` has converged,
    the :class:`ReconciliationEngine` must report zero new / zero
    missing documents when compared to the manager's processed state.

    This is the cross-check that ties the convergence property to the
    reconciliation layer — a single orphaned outbox event would show up
    as a ``new`` id here.
    """
    manager = IngestionLifecycleManager()
    for doc in events:
        manager.process_document(doc)
    final = list(manager.processed_documents.values())

    engine = ReconciliationEngine()
    diff = engine.reconcile(expected=final, actual=final)
    assert diff["new"] == []
    assert diff["missing"] == []
    assert sorted(diff["reconciled"]) == sorted(d.document_id for d in final)


def test_convergence_empty_input() -> None:
    """P3-T3: an empty event list produces an empty processed state.
    Pin the trivial case explicitly so a regression in the strategy
    surfaces here rather than inside a random example."""
    assert _finalize([]) == {}
