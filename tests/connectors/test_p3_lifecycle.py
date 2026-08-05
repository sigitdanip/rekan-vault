"""
P3-T2 — Notion lifecycle classification (archive, restore, delete).

The Notion connector (RV-DEC-P3-0002) does not emit ``Drive``-shaped
lifecycle events (delete / trashed / moved / renamed) — it only filters
trashed pages at scan time and reports a count from ``/v1/search``.

This module pins the observable Notion lifecycle behavior:

  * Archive: ``in_trash=true`` page is excluded from ``scan()`` output.
  * Restore: ``in_trash=false`` page is included again on the next scan.
  * Delete: a page that disappears from ``/v1/search`` results is not
    returned by ``scan()`` (reconciliation is what deactivates the row).
  * Revoke (404 on a previously-known page): the connector raises
    :class:`RekanVaultError` with code ``NOT_FOUND`` and target
    ``notion_api`` — the worker is responsible for marking the source
    in an error state.

These tests are independent of the worker persistence layer; they pin
the connector-side contract only.
"""

from __future__ import annotations

from typing import Any

import httpx
import pytest
import respx

from rekanvault.contracts.errors import ErrorCode, RekanVaultError
from rekanvault.sources.notion import NotionConnector

NOTION_BASE = "https://api.notion.com"
TEST_TOKEN = "secret_test_token_for_unit_tests"
PAGE_A = "11111111-1111-1111-1111-111111111111"


def _page_response(page_id: str, title: str, *, in_trash: bool = False) -> dict[str, Any]:
    return {
        "object": "page",
        "id": page_id,
        "created_time": "2024-01-01T00:00:00.000Z",
        "last_edited_time": "2024-06-01T12:00:00.000Z",
        "in_trash": in_trash,
        "properties": {
            "title": {
                "id": "title",
                "type": "title",
                "title": [{"type": "text", "plain_text": title, "text": {"content": title}}],
            }
        },
    }


def _empty_children() -> dict[str, Any]:
    return {"object": "list", "results": [], "has_more": False, "next_cursor": None}


# ---- archive (in_trash=true) ----------------------------------------------


@pytest.mark.asyncio
async def test_notion_archived_page_excluded_from_scan() -> None:
    """P3-T2 (archive): a page with ``in_trash=true`` is not surfaced by
    ``scan()`` — it is classified as archived and the connector skips it.
    """
    async with respx.mock(assert_all_called=True, base_url=NOTION_BASE) as router:
        router.get(f"/v1/pages/{PAGE_A}").mock(
            return_value=httpx.Response(200, json=_page_response(PAGE_A, "Archived", in_trash=True))
        )

        async with httpx.AsyncClient() as client:
            connector = NotionConnector(
                source_id="src_notion_1",
                config={"root_page_id": PAGE_A},
                client=client,
                token=TEST_TOKEN,
            )
            docs = await connector.scan()

    assert docs == []


# ---- restore (in_trash=true then false) -----------------------------------


@pytest.mark.asyncio
async def test_notion_restored_page_reappears_in_scan() -> None:
    """P3-T2 (restore): once ``in_trash`` flips back to ``false``, the
    page is surfaced by ``scan()`` again. Same page id, different state.

    The test models the flow as two consecutive ``scan()`` calls with
    different respx fixtures — a coarse but faithful simulation of the
    safety poll catching the restore.
    """
    # First scan: page is archived, scan returns nothing.
    async with respx.mock(assert_all_called=True, base_url=NOTION_BASE) as router:
        router.get(f"/v1/pages/{PAGE_A}").mock(
            return_value=httpx.Response(200, json=_page_response(PAGE_A, "Doc", in_trash=True))
        )
        async with httpx.AsyncClient() as client:
            connector = NotionConnector(
                source_id="src_notion_1",
                config={"root_page_id": PAGE_A},
                client=client,
                token=TEST_TOKEN,
            )
            archived_docs = await connector.scan()
        assert archived_docs == []

    # Second scan: same page, now restored. The block-children endpoint
    # is hit only when the page is not in_trash.
    async with respx.mock(assert_all_called=True, base_url=NOTION_BASE) as router:
        router.get(f"/v1/pages/{PAGE_A}").mock(
            return_value=httpx.Response(200, json=_page_response(PAGE_A, "Doc", in_trash=False))
        )
        router.get(f"/v1/blocks/{PAGE_A}/children").mock(return_value=httpx.Response(200, json=_empty_children()))
        async with httpx.AsyncClient() as client:
            connector = NotionConnector(
                source_id="src_notion_1",
                config={"root_page_id": PAGE_A},
                client=client,
                token=TEST_TOKEN,
            )
            restored_docs = await connector.scan()

    assert len(restored_docs) == 1
    assert restored_docs[0].title == "Doc"


# ---- delete (page gone from /v1/search) -----------------------------------


@pytest.mark.asyncio
async def test_notion_deleted_page_returns_empty_search() -> None:
    """P3-T2 (delete): a page that was deleted is not in the ``/v1/search``
    response, so the safety poll reports zero changes for it. The
    reconciliation layer is what would deactivate the row in storage."""
    async with respx.mock(assert_all_called=True, base_url=NOTION_BASE) as router:
        # /v1/search returns no results — the page is gone.
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
            result = await connector.fetch_changes(cursor="2024-01-01T00:00:00.000Z")

    assert result["changes_count"] == 0
    assert result["has_more"] is False
    # Cursor still advances — we just didn't see anything.
    assert "new_cursor" in result


# ---- revoke (404 on a previously-known page) -------------------------------


@pytest.mark.asyncio
async def test_notion_revoked_access_raises_not_found() -> None:
    """P3-T2 (revoke): a 404 on the page fetch is mapped to a
    :class:`RekanVaultError` with code ``NOT_FOUND`` and target
    ``notion_api``. The worker uses this signal to mark the source in
    an error state (401/403 do the same with their own codes)."""
    async with respx.mock(assert_all_called=True, base_url=NOTION_BASE) as router:
        router.get(f"/v1/pages/{PAGE_A}").mock(
            return_value=httpx.Response(404, json={"object": "error", "status": 404, "message": "Not found"})
        )

        async with httpx.AsyncClient() as client:
            connector = NotionConnector(
                source_id="src_notion_1",
                config={"root_page_id": PAGE_A},
                client=client,
                token=TEST_TOKEN,
            )
            with pytest.raises(RekanVaultError) as excinfo:
                await connector.scan()

    assert excinfo.value.code == ErrorCode.NOT_FOUND
    assert excinfo.value.target == "notion_api"


# ---- move (Notion has no parents resource; the test is best-effort) -------


@pytest.mark.asyncio
async def test_notion_move_in_classified_preserved_in_locator() -> None:
    """P3-T2 (move): Notion does not have a parents[].move() surface —
    moving a page is just a relink that changes nothing in the page
    response. The connector preserves ``native_id`` and ``uri`` (and
    therefore the citation locator) across what is, from the connector's
    perspective, an invisible-to-us state change. This is the property
    the AC calls out: lifecycle mutations must not lose document
    identity."""
    async with respx.mock(assert_all_called=True, base_url=NOTION_BASE) as router:
        router.get(f"/v1/pages/{PAGE_A}").mock(
            return_value=httpx.Response(200, json=_page_response(PAGE_A, "Doc", in_trash=False))
        )
        router.get(f"/v1/blocks/{PAGE_A}/children").mock(return_value=httpx.Response(200, json=_empty_children()))

        async with httpx.AsyncClient() as client:
            connector = NotionConnector(
                source_id="src_notion_1",
                config={"root_page_id": PAGE_A},
                client=client,
                token=TEST_TOKEN,
            )
            first = await connector.scan()
            second = await connector.scan()  # imagine a "move" happened in between

    assert len(first) == 1
    assert len(second) == 1
    # Document identity is preserved.
    assert first[0].locator.native_id == second[0].locator.native_id
    assert first[0].locator.uri == second[0].locator.uri
