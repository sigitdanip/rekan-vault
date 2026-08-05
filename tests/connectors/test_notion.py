"""
Notion connector tests (P3 — RV-DEC-P3-0002, RV-DEC-P3-0003, RV-DEC-P3-0006).

Respx-mocks the Notion REST API. No real network calls. Tests use a synthetic
``token`` passed directly to the connector constructor so the production
``RV_NOTION_TOKEN`` env var does not leak into the test suite.

Each test gets a fresh ``httpx.AsyncClient`` + ``respx.mock`` context so
patterns don't leak between tests.
"""

from __future__ import annotations

import hashlib
import hmac

import httpx
import pytest
import respx

from rekanvault.contracts.documents import SourceProvider
from rekanvault.sources.notion import NotionConnector

# ---- fixtures ---------------------------------------------------------------

NOTION_BASE = "https://api.notion.com"
TEST_TOKEN = "secret_test_token_for_unit_tests"
PAGE_A = "11111111-1111-1111-1111-111111111111"
PAGE_B = "22222222-2222-2222-2222-222222222222"
BLOCK_P1 = "33333333-3333-3333-3333-333333333333"
BLOCK_P2 = "44444444-4444-4444-4444-444444444444"
BLOCK_CHILD = "55555555-5555-5555-5555-555555555555"
DB_ID = "66666666-6666-6666-6666-666666666666"
DS_ID = "77777777-7777-7777-7777-777777777777"
ROW_ID = "88888888-8888-8888-8888-888888888888"

# 32-char stripped form (no dashes) — what we expect DocumentBlock.block_id to contain.
PAGE_A_32 = PAGE_A.replace("-", "")
BLOCK_P1_32 = BLOCK_P1.replace("-", "")


def _page_response(page_id: str, title: str, in_trash: bool = False) -> dict[str, object]:
    return {
        "object": "page",
        "id": page_id,
        "created_time": "2024-01-01T00:00:00.000Z",
        "last_edited_time": "2024-06-01T12:00:00.000Z",
        "in_trash": in_trash,  # 2026-03-11 field (replaces ``archived``)
        "properties": {
            "title": {
                "id": "title",
                "type": "title",
                "title": [{"type": "text", "plain_text": title, "text": {"content": title}}],
            }
        },
    }


def _block_response(block_id: str, block_type: str, content: str, *, has_children: bool = False) -> dict[str, object]:
    payload: dict[str, object] = {"rich_text": [{"type": "text", "plain_text": content, "text": {"content": content}}]}
    return {
        "object": "block",
        "id": block_id,
        "type": block_type,
        "has_children": has_children,
        block_type: payload,
    }


def _children_response(
    blocks: list[dict[str, object]], *, has_more: bool = False, next_cursor: str | None = None
) -> dict[str, object]:
    return {
        "object": "list",
        "results": blocks,
        "has_more": has_more,
        "next_cursor": next_cursor,
    }


# ---- tests ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_notion_scan_page_with_blocks() -> None:
    """``scan()`` returns one ``NormalizedDocument`` per page with the page's
    top-level blocks as ``DocumentBlock`` entries. Real Notion block IDs
    (32-char UUID, dashes stripped) are preserved as ``DocumentBlock.block_id``."""
    async with respx.mock(assert_all_called=True, base_url=NOTION_BASE) as router:
        router.get(f"/v1/pages/{PAGE_A}").mock(
            return_value=httpx.Response(200, json=_page_response(PAGE_A, "Engineering Guidelines"))
        )
        router.get(f"/v1/blocks/{PAGE_A}/children").mock(
            return_value=httpx.Response(
                200,
                json=_children_response(
                    [
                        _block_response(BLOCK_P1, "heading_1", "Working agreements"),
                        _block_response(BLOCK_P2, "bulleted_list_item", "Anti-slop directives"),
                    ]
                ),
            )
        )

        async with httpx.AsyncClient() as client:
            connector = NotionConnector(
                source_id="src_notion_1",
                config={"root_page_id": PAGE_A, "workspace_id": "ws_test"},
                client=client,
                token=TEST_TOKEN,
            )
            docs = await connector.scan()

    assert len(docs) == 1
    doc = docs[0]
    assert doc.provider == SourceProvider.NOTION
    assert doc.title == "Engineering Guidelines"
    assert doc.locator.provider == SourceProvider.NOTION
    assert doc.locator.native_id == PAGE_A_32
    assert doc.locator.uri == f"https://notion.so/{PAGE_A_32}"

    blocks = doc.versions[0].blocks
    assert len(blocks) == 2
    assert blocks[0].block_id == BLOCK_P1_32
    assert blocks[0].block_type == "heading_1"
    assert blocks[0].content == "Working agreements"
    assert blocks[1].block_id == BLOCK_P1_32.replace(BLOCK_P1_32[:8], BLOCK_P2.replace("-", "")[:8])
    assert blocks[1].block_type == "bulleted_list_item"
    # Sequence is monotonically increasing from 1.
    assert [b.sequence for b in blocks] == [1, 2]


@pytest.mark.asyncio
async def test_notion_scan_nested_children() -> None:
    """A block with ``has_children=true`` is recursed into, and the nested
    blocks appear in the same document with sequence numbers continuing from
    the parent's last sequence. Depth is capped at 8."""
    async with respx.mock(assert_all_called=True, base_url=NOTION_BASE) as router:
        router.get(f"/v1/pages/{PAGE_A}").mock(return_value=httpx.Response(200, json=_page_response(PAGE_A, "Parent")))
        # Top-level: one block that has a child.
        router.get(f"/v1/blocks/{PAGE_A}/children").mock(
            return_value=httpx.Response(
                200,
                json=_children_response([_block_response(BLOCK_P1, "toggle", "Show details", has_children=True)]),
            )
        )
        # Nested: one child block.
        router.get(f"/v1/blocks/{BLOCK_P1}/children").mock(
            return_value=httpx.Response(
                200,
                json=_children_response([_block_response(BLOCK_CHILD, "paragraph", "Hidden detail")]),
            )
        )

        async with httpx.AsyncClient() as client:
            connector = NotionConnector(
                source_id="src_notion_1",
                config={"root_page_id": PAGE_A},
                client=client,
                token=TEST_TOKEN,
            )
            docs = await connector.scan()

    blocks = docs[0].versions[0].blocks
    assert len(blocks) == 2
    assert blocks[0].block_id == BLOCK_P1_32
    assert blocks[0].block_type == "toggle"
    assert blocks[1].block_id == BLOCK_CHILD.replace("-", "")
    assert blocks[1].block_type == "paragraph"
    assert blocks[1].content == "Hidden detail"
    # Nested block gets sequence 2, not 1.
    assert [b.sequence for b in blocks] == [1, 2]


@pytest.mark.asyncio
async def test_notion_scan_database_rows() -> None:
    """Database query path: ``GET /v1/databases/{id}`` discovers the
    ``data_sources[]``, then ``POST /v1/data_sources/{id}/query`` returns rows
    which are themselves pages (2025-09-03 split)."""
    async with respx.mock(assert_all_called=True, base_url=NOTION_BASE) as router:
        # Root page is a database container — its first child is child_database.
        router.get(f"/v1/pages/{PAGE_A}").mock(return_value=httpx.Response(200, json=_page_response(PAGE_A, "DB Root")))
        router.get(f"/v1/blocks/{PAGE_A}/children").mock(
            return_value=httpx.Response(
                200,
                json=_children_response(
                    [
                        {
                            "object": "block",
                            "id": DB_ID,
                            "type": "child_database",
                            "has_children": False,
                            "child_database": {"title": "Tasks"},
                        }
                    ]
                ),
            )
        )
        router.get(f"/v1/databases/{DB_ID}").mock(
            return_value=httpx.Response(
                200, json={"object": "database", "id": DB_ID, "data_sources": [{"id": DS_ID, "name": "Tasks"}]}
            )
        )
        router.post(f"/v1/data_sources/{DS_ID}/query").mock(
            return_value=httpx.Response(
                200,
                json={
                    "object": "list",
                    "results": [{"object": "page", "id": ROW_ID, "in_trash": False}],
                    "has_more": False,
                    "next_cursor": None,
                },
            )
        )
        # The row page itself — title + children.
        router.get(f"/v1/pages/{ROW_ID}").mock(return_value=httpx.Response(200, json=_page_response(ROW_ID, "Row 1")))
        router.get(f"/v1/blocks/{ROW_ID}/children").mock(
            return_value=httpx.Response(
                200,
                json=_children_response([_block_response(BLOCK_P1, "paragraph", "row content")]),
            )
        )

        async with httpx.AsyncClient() as client:
            connector = NotionConnector(
                source_id="src_notion_1",
                config={"root_page_id": PAGE_A},
                client=client,
                token=TEST_TOKEN,
            )
            docs = await connector.scan()

    # Two documents: the parent + the row page (deduplicated by seen_page_ids).
    assert len(docs) == 2
    titles = sorted(d.title for d in docs)
    assert titles == ["DB Root", "Row 1"]


@pytest.mark.asyncio
async def test_notion_rate_limit_retry() -> None:
    """A 429 response with ``Retry-After: 0.05`` is retried and the second
    response is returned. The request count reflects the retry."""
    call_count = 0

    def _side_effect(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return httpx.Response(429, headers={"Retry-After": "0"}, json={"object": "error", "status": 429})
        return httpx.Response(200, json=_page_response(PAGE_A, "After Retry"))

    async with respx.mock(assert_all_called=False, base_url=NOTION_BASE) as router:
        router.get(f"/v1/pages/{PAGE_A}").mock(side_effect=_side_effect)
        router.get(f"/v1/blocks/{PAGE_A}/children").mock(return_value=httpx.Response(200, json=_children_response([])))

        async with httpx.AsyncClient() as client:
            connector = NotionConnector(
                source_id="src_notion_1",
                config={"root_page_id": PAGE_A},
                client=client,
                token=TEST_TOKEN,
            )
            docs = await connector.scan()

    assert call_count == 2  # one retry
    assert len(docs) == 1
    assert docs[0].title == "After Retry"


@pytest.mark.asyncio
async def test_notion_block_id_preserved_as_citation_locator() -> None:
    """DocumentBlock.block_id MUST be the real 32-char Notion UUID (dashes
    stripped) — the citation locator the downstream pipeline resolves to."""
    async with respx.mock(assert_all_called=True, base_url=NOTION_BASE) as router:
        router.get(f"/v1/pages/{PAGE_A}").mock(
            return_value=httpx.Response(200, json=_page_response(PAGE_A, "Citation Test"))
        )
        router.get(f"/v1/blocks/{PAGE_A}/children").mock(
            return_value=httpx.Response(
                200,
                json=_children_response(
                    [_block_response(BLOCK_P1, "paragraph", "first"), _block_response(BLOCK_P2, "paragraph", "second")]
                ),
            )
        )

        async with httpx.AsyncClient() as client:
            connector = NotionConnector(
                source_id="src_notion_1",
                config={"root_page_id": PAGE_A},
                client=client,
                token=TEST_TOKEN,
            )
            docs = await connector.scan()

    blocks = docs[0].versions[0].blocks
    # Real 32-char UUIDs, dashes stripped — exactly what Notion returns.
    assert blocks[0].block_id == BLOCK_P1_32
    assert blocks[1].block_id == BLOCK_P2.replace("-", "")
    # No dashes in the stored block_id (Notion URL form is 32 hex chars).
    for b in blocks:
        assert "-" not in b.block_id
        assert len(b.block_id) == 32


def test_notion_webhook_signature_verification() -> None:
    """HMAC-SHA256 over the raw body, compared with hmac.compare_digest.
    Notion sends the signature as ``sha256=<hex>``."""
    secret = "whsec_test_secret"
    body = b'{"entity":{"id":"abc"}}'
    good_sig = "sha256=" + hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()

    # Correct signature + secret → True.
    assert NotionConnector.verify_webhook_signature(body, good_sig, secret) is True
    # Wrong signature → False.
    assert NotionConnector.verify_webhook_signature(body, "sha256=" + "0" * 64, secret) is False
    # Missing signature header → False.
    assert NotionConnector.verify_webhook_signature(body, None, secret) is False
    # Missing token → False (fail-secure).
    assert NotionConnector.verify_webhook_signature(body, good_sig, "") is False
    # Tampered body → False.
    assert NotionConnector.verify_webhook_signature(body + b"x", good_sig, secret) is False
    # Stripped prefix also rejected (defense in depth — we expect the full ``sha256=`` form).
    stripped = good_sig.removeprefix("sha256=")
    assert NotionConnector.verify_webhook_signature(body, stripped, secret) is False


def test_notion_webhook_handshake_detection() -> None:
    """The one-time handshake payload contains a ``verification_token`` field;
    handlers should accept it without a signature."""
    assert NotionConnector.is_handshake_payload({"verification_token": "abc123"}) is True
    assert NotionConnector.is_handshake_payload({"type": "page.created"}) is False
    assert NotionConnector.is_handshake_payload({}) is False


@pytest.mark.asyncio
async def test_notion_in_trash_excluded() -> None:
    """2026-03-11: pages with ``in_trash: true`` are not surfaced as docs.
    The 2025-09-03 ``archived`` field is also still tolerated (graceful)."""
    async with respx.mock(assert_all_called=True, base_url=NOTION_BASE) as router:
        router.get(f"/v1/pages/{PAGE_A}").mock(
            return_value=httpx.Response(200, json=_page_response(PAGE_A, "Trashed", in_trash=True))
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


@pytest.mark.asyncio
async def test_notion_attachment_metadata_preserved() -> None:
    """File blocks: the URL + expiry_time are stored on DocumentBlock.metadata
    so downstream code can re-fetch when needed. No recursive download."""
    file_block_id = "99999999-9999-9999-9999-999999999999"
    async with respx.mock(assert_all_called=True, base_url=NOTION_BASE) as router:
        router.get(f"/v1/pages/{PAGE_A}").mock(
            return_value=httpx.Response(200, json=_page_response(PAGE_A, "Attachments"))
        )
        router.get(f"/v1/blocks/{PAGE_A}/children").mock(
            return_value=httpx.Response(
                200,
                json=_children_response(
                    [
                        {
                            "object": "block",
                            "id": file_block_id,
                            "type": "file",
                            "has_children": False,
                            "file": {
                                "file": {
                                    "url": "https://s3.us-west-2.amazonaws.com/secure.notion-static.com/x/y.pdf?X-Amz-...",
                                    "expiry_time": "2024-01-01T01:00:00.000Z",
                                },
                                "name": "spec.pdf",
                            },
                        }
                    ]
                ),
            )
        )

        async with httpx.AsyncClient() as client:
            connector = NotionConnector(
                source_id="src_notion_1",
                config={"root_page_id": PAGE_A},
                client=client,
                token=TEST_TOKEN,
            )
            docs = await connector.scan()

    block = docs[0].versions[0].blocks[0]
    assert block.block_type == "file"
    assert block.metadata["kind"] == "file"
    assert block.metadata["filename"] == "spec.pdf"
    assert "s3.us-west-2" in block.metadata["url"]
    # Body content is empty — attachment reference, not contents.
    assert block.content == ""


@pytest.mark.asyncio
async def test_notion_fetch_changes_returns_new_cursor() -> None:
    """``fetch_changes()`` calls ``/v1/search`` and returns a new ISO cursor
    and a non-negative changes_count. The cursor advances to ``now``."""
    async with respx.mock(assert_all_called=True, base_url=NOTION_BASE) as router:
        router.post("/v1/search").mock(
            return_value=httpx.Response(
                200,
                json={
                    "object": "list",
                    "results": [
                        {
                            "object": "page",
                            "id": PAGE_A,
                            "last_edited_time": "2024-06-01T12:00:00.000Z",
                            "in_trash": False,
                        },
                        {
                            "object": "page",
                            "id": PAGE_B,
                            "last_edited_time": "2024-06-02T12:00:00.000Z",
                            "in_trash": False,
                        },
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
            result = await connector.fetch_changes(cursor="2024-01-01T00:00:00.000Z")

    assert result["changes_count"] == 2
    assert "new_cursor" in result
    # Cursor is a valid ISO 8601 timestamp.
    from datetime import datetime

    datetime.fromisoformat(result["new_cursor"].replace("Z", "+00:00"))


@pytest.mark.asyncio
async def test_notion_provider_property() -> None:
    """Sanity: the connector declares NOTION as its provider."""
    async with httpx.AsyncClient() as client:
        connector = NotionConnector(source_id="src_x", config={}, client=client, token=TEST_TOKEN)
    assert connector.provider == SourceProvider.NOTION
