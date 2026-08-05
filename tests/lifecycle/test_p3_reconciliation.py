"""
P3-T7 — Missed Notion webhook repaired by poll / reconciliation.

Notion has no real changes feed; the safety net is a 5-minute poll
(``fetch_changes``) backed by a daily full reconciliation. The AC
requires that a dropped or unreceived webhook event is detected and
repaired by one of these mechanisms.

This module pins the two-step recovery contract:

  1. **Safety poll** (``fetch_changes``): if the cursor lags the
     provider's actual state, the poll surfaces the missed event
     through ``changes_count > 0``. The poll is the AC's "5-minute"
     path.

  2. **Full reconciliation** (``reconcile`` + ``ReconciliationEngine``):
     if the poll fails or the lag is large, the daily full scan
     converges state to 100% agreement with the provider inventory.
     The ``ReconciliationEngine`` produces the diff the worker uses
     to deactivate missing docs and detect new ones.

We use the existing ``NotionConnector`` (mocked via respx) and the
``ReconciliationEngine`` — no new code paths, just pinning the
contract.
"""

from __future__ import annotations

from typing import Any

import httpx
import pytest
import respx

from rekanvault.contracts.documents import (
    DocumentBlock,
    DocumentLocator,
    DocumentVersion,
    NormalizedDocument,
    SourceProvider,
)
from rekanvault.ingestion.reconciliation import ReconciliationEngine
from rekanvault.sources.notion import NotionConnector

NOTION_BASE = "https://api.notion.com"
TEST_TOKEN = "secret_test_token_for_unit_tests"
PAGE_A = "11111111-1111-1111-1111-111111111111"
PAGE_B = "22222222-2222-2222-2222-222222222222"
PAGE_C = "33333333-3333-3333-3333-333333333333"


def _page_dict(page_id: str, last_edited: str, *, in_trash: bool = False) -> dict[str, Any]:
    return {
        "object": "page",
        "id": page_id,
        "last_edited_time": last_edited,
        "in_trash": in_trash,
    }


def _empty_children() -> dict[str, Any]:
    return {"object": "list", "results": [], "has_more": False, "next_cursor": None}


def _build_doc(page_id: str, title: str = "Doc") -> NormalizedDocument:
    real_id = page_id.replace("-", "")
    return NormalizedDocument(
        document_id=real_id,
        workspace_id="ws_test",
        source_id="src_notion_1",
        title=title,
        provider=SourceProvider.NOTION,
        locator=DocumentLocator(
            provider=SourceProvider.NOTION,
            native_id=real_id,
            uri=f"https://notion.so/{real_id}",
        ),
        active_version_id="ver_1",
        versions=[
            DocumentVersion(
                version_id="ver_1",
                document_id=real_id,
                version_number=1,
                content_hash="h1",
                blocks=[DocumentBlock(block_id="b1", block_type="paragraph", content="x", sequence=1)],
            )
        ],
    )


# ---- 1) safety poll surfaces the missed event -----------------------------


@pytest.mark.asyncio
async def test_safety_poll_catches_missed_event() -> None:
    """P3-T7 (safety poll): a webhook for ``PAGE_B`` was missed (the
    cursor is older than ``PAGE_B``'s ``last_edited_time``). The next
    safety poll — implemented as ``fetch_changes(old_cursor)`` — must
    surface ``PAGE_B`` in ``changes_count`` and advance the cursor
    forward."""
    async with respx.mock(assert_all_called=True, base_url=NOTION_BASE) as router:
        router.post("/v1/search").mock(
            return_value=httpx.Response(
                200,
                json={
                    "object": "list",
                    "results": [
                        _page_dict(PAGE_C, "2024-06-10T12:00:00.000Z"),
                        _page_dict(PAGE_B, "2024-06-05T12:00:00.000Z"),  # missed event
                        _page_dict(PAGE_A, "2024-05-01T12:00:00.000Z"),
                    ],
                    "has_more": False,
                    "next_cursor": None,
                },
            )
        )

        async with httpx.AsyncClient() as client:
            connector = NotionConnector(
                source_id="src_notion_1",
                config={"root_page_id": PAGE_A},
                client=client,
                token=TEST_TOKEN,
            )
            result = await connector.fetch_changes(cursor="2024-06-04T00:00:00.000Z")

    # The poll counts only pages whose last_edited_time is >= the
    # cursor. PAGE_A is older than the cursor and is skipped — that's
    # the point of the watermark. The poll saw 2 changed pages
    # (PAGE_C and the missed PAGE_B).
    assert result["changes_count"] == 2
    assert result["has_more"] is False
    # Cursor advanced to "now" — the next poll will see only newer events.
    assert "new_cursor" in result


# ---- 2) full reconciliation converges state --------------------------------


@pytest.mark.asyncio
async def test_full_reconciliation_converges_to_provider_inventory() -> None:
    """P3-T7 (full reconciliation): the daily full scan produces a
    provider inventory; the ``ReconciliationEngine`` diffs it against
    the in-memory state and reports exactly the docs that are new
    (in provider, not in memory) or missing (in memory, not in
    provider).

    We build the provider inventory directly rather than going through
    ``NotionConnector.scan()`` because the connector only walks tree
    edges from a single root page — for the reconciliation contract
    the *shape* of the inventory is what matters, not how the
    connector produced it.
    """
    # In-memory state — missing PAGE_B (the one we missed).
    known = [_build_doc(PAGE_A), _build_doc(PAGE_C)]
    # Provider inventory — PAGE_B is back, PAGE_A and PAGE_C unchanged.
    provider_inventory = [
        _build_doc(PAGE_A, "Doc A"),
        _build_doc(PAGE_B, "Doc B"),
        _build_doc(PAGE_C, "Doc C"),
    ]

    engine = ReconciliationEngine()
    diff = engine.reconcile(expected=provider_inventory, actual=known)

    # PAGE_B is missing from memory — the worker will ingest it.
    assert sorted(diff["missing"]) == [PAGE_B.replace("-", "")]
    # No new orphans in memory that the provider doesn't know about.
    assert diff["new"] == []
    # PAGE_A and PAGE_C are reconciled.
    assert sorted(diff["reconciled"]) == sorted([PAGE_A.replace("-", ""), PAGE_C.replace("-", "")])


# ---- 3) reconciliation after a delete --------------------------------------


@pytest.mark.asyncio
async def test_reconciliation_detects_drift_on_delete() -> None:
    """P3-T7 (delete drift): a page was deleted on the Notion side but
    the local index still has it. The next reconciliation must surface
    it as a ``new`` (orphan-in-memory) id so the worker can deactivate
    the row.

    Semantics: the engine's ``new`` field is "in actual (memory) but
    not in expected (provider)" — these are the orphans the worker
    needs to deactivate. ``missing`` is the inverse: docs the
    provider has that the memory does not.
    """
    known = [_build_doc(PAGE_A)]
    provider_inventory: list[NormalizedDocument] = []  # page was deleted

    engine = ReconciliationEngine()
    diff = engine.reconcile(expected=provider_inventory, actual=known)

    # PAGE_A is an orphan in memory (provider doesn't know it).
    assert sorted(diff["new"]) == [PAGE_A.replace("-", "")]
    assert diff["missing"] == []
    assert diff["reconciled"] == []


# ---- 4) safety poll cursor advances ----------------------------------------


@pytest.mark.asyncio
async def test_safety_poll_advances_cursor_even_with_zero_changes() -> None:
    """P3-T7 (cursor advance): the safety poll must always return a
    ``new_cursor`` even when no changes are found. A regressed poll
    that returns the same cursor would re-process the same events on
    every poll and never converge."""
    async with respx.mock(assert_all_called=True, base_url=NOTION_BASE) as router:
        router.post("/v1/search").mock(
            return_value=httpx.Response(
                200,
                json={"object": "list", "results": [], "has_more": False, "next_cursor": None},
            )
        )

        async with httpx.AsyncClient() as client:
            connector = NotionConnector(
                source_id="src_notion_1",
                config={"root_page_id": PAGE_A},
                client=client,
                token=TEST_TOKEN,
            )
            result = await connector.fetch_changes(cursor="2024-06-01T00:00:00.000Z")

    assert result["changes_count"] == 0
    assert result["new_cursor"] != "2024-06-01T00:00:00.000Z"  # cursor advanced
