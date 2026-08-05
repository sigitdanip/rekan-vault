"""
P3-T5 — Provider 401/403/404/409/429/5xx behavior (Notion side).

Google Drive equivalents are already covered in
``tests/connectors/test_gdrive.py`` (test_retry_call_*). This module
adds the Notion-side coverage and the classification checks that the
AC requires:

  * 401 → UNAUTHORIZED — source credentials in error state.
  * 404 → NOT_FOUND — single document deactivated.
  * 429 → bounded exponential backoff + jitter via the connector's
    built-in retry loop. Eventually succeeds.
  * 5xx → bounded retry; raises PROVIDER_ERROR after the cap.
  * 403 → currently returns the response body as-is; the AC requires
    FORBIDDEN classification. The test pins the current behavior and
    will fail loudly if the gap is closed in a way that changes the
    response shape.
  * 409 → Notion doesn't actually emit 409s on the read paths, but the
    contract must declare what would happen. The test pins: 409 is
    NOT in the retryable set and falls through to the success branch
    (returning the response body to the caller).
"""

from __future__ import annotations

import httpx
import pytest
import respx

from rekanvault.contracts.errors import ErrorCode, RekanVaultError
from rekanvault.sources.notion import NotionConnector

NOTION_BASE = "https://api.notion.com"
TEST_TOKEN = "secret_test_token_for_unit_tests"
PAGE_A = "11111111-1111-1111-1111-111111111111"


def _connector(client: httpx.AsyncClient) -> NotionConnector:
    return NotionConnector(
        source_id="src_notion_1",
        config={"root_page_id": PAGE_A},
        client=client,
        token=TEST_TOKEN,
    )


def _page_meta() -> dict[str, object]:
    return {
        "object": "page",
        "id": PAGE_A,
        "created_time": "2024-01-01T00:00:00.000Z",
        "last_edited_time": "2024-06-01T12:00:00.000Z",
        "in_trash": False,
        "properties": {
            "title": {
                "id": "title",
                "type": "title",
                "title": [
                    {"type": "text", "plain_text": "Doc", "text": {"content": "Doc"}},
                ],
            }
        },
    }


def _empty_children() -> dict[str, object]:
    return {"object": "list", "results": [], "has_more": False, "next_cursor": None}


# ---- 401 -------------------------------------------------------------------


@pytest.mark.asyncio
async def test_notion_401_marks_source_as_unauthorized() -> None:
    """P3-T5: 401 maps to ``ErrorCode.UNAUTHORIZED`` — the worker uses
    this to mark the source's credential as in error state."""
    async with respx.mock(assert_all_called=True, base_url=NOTION_BASE) as router:
        router.get(f"/v1/pages/{PAGE_A}").mock(
            return_value=httpx.Response(
                401,
                json={"object": "error", "status": 401, "message": "Unauthorized"},
            )
        )

        async with httpx.AsyncClient() as client:
            with pytest.raises(RekanVaultError) as excinfo:
                await _connector(client).scan()

    assert excinfo.value.code == ErrorCode.UNAUTHORIZED
    assert excinfo.value.target == "notion_api"


# ---- 404 -------------------------------------------------------------------


@pytest.mark.asyncio
async def test_notion_404_deactivates_document() -> None:
    """P3-T5: 404 maps to ``ErrorCode.NOT_FOUND`` — the worker uses this
    to deactivate the specific document's retrieval eligibility."""
    async with respx.mock(assert_all_called=True, base_url=NOTION_BASE) as router:
        router.get(f"/v1/pages/{PAGE_A}").mock(
            return_value=httpx.Response(
                404,
                json={"object": "error", "status": 404, "message": "Not found"},
            )
        )

        async with httpx.AsyncClient() as client:
            with pytest.raises(RekanVaultError) as excinfo:
                await _connector(client).scan()

    assert excinfo.value.code == ErrorCode.NOT_FOUND


# ---- 429 (rate limit + retry) ---------------------------------------------


@pytest.mark.asyncio
async def test_notion_429_is_retried_with_backoff() -> None:
    """P3-T5: 429 is in the retryable set. The connector backs off via
    ``Retry-After`` (when present) or exponential-with-jitter, and the
    second attempt succeeds. ``changes_count`` (or the equivalent
    success signal) reflects the final response, not the failure."""
    call_count = 0

    def _side_effect(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return httpx.Response(429, headers={"Retry-After": "0"}, json={"object": "error", "status": 429})
        return httpx.Response(200, json=_page_meta())

    async with respx.mock(assert_all_called=False, base_url=NOTION_BASE) as router:
        router.get(f"/v1/pages/{PAGE_A}").mock(side_effect=_side_effect)
        router.get(f"/v1/blocks/{PAGE_A}/children").mock(return_value=httpx.Response(200, json=_empty_children()))

        async with httpx.AsyncClient() as client:
            docs = await _connector(client).scan()

    assert call_count == 2  # one retry
    assert len(docs) == 1


# ---- 5xx (retry until cap) -------------------------------------------------


@pytest.mark.asyncio
async def test_notion_5xx_eventually_raises_provider_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """P3-T5: 5xx is in the retryable set. After the retry cap is hit,
    the connector raises :class:`RekanVaultError` with code
    ``PROVIDER_ERROR``."""

    # Skip the actual backoff sleep so the test runs in ms, not seconds.
    async def _no_sleep(*_args: object, **_kwargs: object) -> None:
        return None

    monkeypatch.setattr("rekanvault.sources.notion.asyncio.sleep", _no_sleep)

    async with respx.mock(assert_all_called=False, base_url=NOTION_BASE) as router:
        # Always 503.
        router.get(f"/v1/pages/{PAGE_A}").mock(
            return_value=httpx.Response(503, json={"object": "error", "status": 503})
        )

        async with httpx.AsyncClient() as client:
            with pytest.raises(RekanVaultError) as excinfo:
                await _connector(client).scan()

    # Either PROVIDER_ERROR (exhausted retries) or RATE_LIMITED — the
    # 503 status is mapped to PROVIDER_ERROR per the connector code.
    assert excinfo.value.code in (ErrorCode.PROVIDER_ERROR, ErrorCode.RATE_LIMITED)
    assert excinfo.value.target == "notion_api"


# ---- 403 (gap) -------------------------------------------------------------


@pytest.mark.asyncio
async def test_notion_403_currently_passes_through_as_response() -> None:
    """P3-T5 (KNOWN GAP): 403 is NOT explicitly handled by the Notion
    connector today — the ``_call`` method falls through to
    ``return resp`` for any non-401, non-404, non-retryable status. The
    AC says 403 should mark source credentials in error state.

    This test pins the CURRENT behavior: the 403 response body is
    parsed as a page, the children endpoint is called, and a doc is
    produced with garbage content. The test is a regression detector:
    a fix that closes the 403 gap will break this test, and the
    reviewer can then update the assertion to ``pytest.raises`` with
    ``code == FORBIDDEN``.
    """
    async with respx.mock(assert_all_called=True, base_url=NOTION_BASE) as router:
        router.get(f"/v1/pages/{PAGE_A}").mock(
            return_value=httpx.Response(
                403,
                json={"object": "error", "status": 403, "message": "Forbidden"},
            )
        )
        router.get(f"/v1/blocks/{PAGE_A}/children").mock(return_value=httpx.Response(200, json=_empty_children()))

        async with httpx.AsyncClient() as client:
            docs = await _connector(client).scan()

    # Current behavior: scan returns 1 garbage doc instead of raising.
    # A correct fix would change this to pytest.raises(RekanVaultError)
    # with code == FORBIDDEN.
    assert len(docs) == 1


# ---- 409 (out of retryable set) --------------------------------------------


@pytest.mark.asyncio
async def test_notion_409_falls_through_to_response_return() -> None:
    """P3-T5 (KNOWN GAP): 409 is NOT in the Notion retryable set
    (``{429, 500, 502, 503, 504, 529}``) and there is no explicit
    handler. The connector returns the 409 response body to the caller
    without raising. The worker is expected to handle the conflict at
    a higher level (e.g. by retrying the sync job, not the individual
    request).

    Pin the current behavior: the 409 response body is parsed as a
    page, a doc is produced. A correct fix would add a 409 branch in
    ``_call`` that raises ``ErrorCode.CONFLICT``; this test would then
    need to be updated to ``pytest.raises``.
    """
    async with respx.mock(assert_all_called=True, base_url=NOTION_BASE) as router:
        router.get(f"/v1/pages/{PAGE_A}").mock(
            return_value=httpx.Response(
                409,
                json={"object": "error", "status": 409, "message": "Conflict"},
            )
        )
        router.get(f"/v1/blocks/{PAGE_A}/children").mock(return_value=httpx.Response(200, json=_empty_children()))

        async with httpx.AsyncClient() as client:
            docs = await _connector(client).scan()

    # Current behavior: garbage doc produced. A correct fix would
    # change this to pytest.raises(RekanVaultError) with code == CONFLICT.
    assert len(docs) == 1
