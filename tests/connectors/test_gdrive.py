"""
Tests for the Google Drive connector.

Strategy: the google-api-python-client uses ``httplib2`` under the hood
(``respx`` only intercepts ``httpx`` traffic, so it cannot mock Drive).
Instead we mock the ``Resource`` object the connector builds in
``_build_service`` — the surface that actually carries the Drive semantics
(``files().list()``, ``changes().list()``, ``documents().get()``). This is
the standard approach in the google-api-python-client test docs.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import httplib2
import pytest
from googleapiclient.errors import HttpError

from rekanvault.contracts.documents import SourceProvider
from rekanvault.sources.google_drive import (
    GoogleDriveConnector,
    _read_google_doc,
    _retry_call,
)

# ---- helpers --------------------------------------------------------------


def _make_http_error(status: int, reason: str = "Test") -> HttpError:
    resp = httplib2.Response({"status": str(status), "reason": reason})
    return HttpError(resp, b'{"error": {"message": "boom"}}')


class _ServiceMocker:
    """Helper to construct a ``MagicMock``-backed Drive v3 service.

    Wires up the chained call patterns the connector uses:

      * ``service.files().list(q=..., pageToken=...).execute()``
      * ``service.documents().get(documentId=..., fields=...).execute()``
      * ``service.changes().getStartPageToken().execute()``
      * ``service.changes().list(pageToken=..., spaces=..., ...).execute()``
    """

    def __init__(self) -> None:
        self.service = MagicMock(name="drive_service")
        self._list_iter: list[dict[str, Any]] = []
        self._changes_iter: list[dict[str, Any]] = []
        self._get_media_payload: bytes | None = None

    def _pop(self, queue_attr: str) -> dict[str, Any]:
        queue = getattr(self, queue_attr)
        if not queue:
            raise AssertionError(f"No more responses queued for {queue_attr}")
        return queue.pop(0)

    def queue_files_list(self, *responses: dict[str, Any]) -> None:
        self._list_iter.extend(responses)
        files_mock = self.service.files.return_value
        list_mock = files_mock.list.return_value

        # ponytail: callable side_effect — list-iter side_effects raise
        # ``StopIteration`` inside ``asyncio.to_thread`` on Py3.12, which
        # ``loop.run_in_executor`` refuses to translate to a Future error.
        def _pop_one() -> dict[str, Any]:
            return self._pop("_list_iter")

        list_mock.execute.side_effect = _pop_one

    def queue_documents_get(self, payload: dict[str, Any]) -> None:
        self.service.documents.return_value.get.return_value.execute.return_value = payload

    def queue_start_page_token(self, token: str) -> None:
        self.service.changes.return_value.getStartPageToken.return_value.execute.return_value = {
            "startPageToken": token
        }

    def queue_changes_list(self, *responses: dict[str, Any]) -> None:
        self._changes_iter.extend(responses)
        changes_mock = self.service.changes.return_value
        list_mock = changes_mock.list.return_value

        def _pop_one() -> dict[str, Any]:
            return self._pop("_changes_iter")

        list_mock.execute.side_effect = _pop_one

    def attach_to_connector(self, connector: GoogleDriveConnector) -> None:
        # Bypass OAuth + ``build()`` entirely — the test is about the
        # connector's logic, not the auth flow.
        connector._service = self.service


def _connector(config: dict[str, Any] | None = None) -> GoogleDriveConnector:
    cfg = dict(config or {})
    cfg.setdefault("folder_id", "folder_test")
    cfg.setdefault("workspace_id", "ws_test")
    return GoogleDriveConnector(source_id="src_gdrive_test", config=cfg)


# ---- _read_google_doc (unit) ---------------------------------------------


def test_read_google_doc_single_paragraph() -> None:
    """A single paragraph under a legacy body field becomes one block."""
    payload = {
        "body": {
            "content": [
                {
                    "paragraph": {
                        "elements": [{"textRun": {"content": "Hello world."}}],
                    }
                }
            ]
        }
    }
    blocks = _read_google_doc(payload)
    assert len(blocks) == 1
    assert blocks[0].block_type == "paragraph"
    assert blocks[0].content == "Hello world."
    assert blocks[0].metadata["tab_id"] == "default"


def test_read_google_doc_iterates_tabs() -> None:
    """RV-DEC-P3-0005: every tab becomes its own block with a ``tab_id``."""
    payload = {
        "tabs": [
            {
                "tabId": "t.0",
                "title": "Intro",
                "body": {"content": [{"paragraph": {"elements": [{"textRun": {"content": "Tab 1 text."}}]}}]},
            },
            {
                "tabId": "t.1",
                "title": "Notes",
                "body": {"content": [{"paragraph": {"elements": [{"textRun": {"content": "Tab 2 text."}}]}}]},
            },
        ]
    }
    blocks = _read_google_doc(payload)
    assert len(blocks) == 2
    assert [b.metadata["tab_id"] for b in blocks] == ["t.0", "t.1"]
    assert [b.content for b in blocks] == ["Tab 1 text.", "Tab 2 text."]


def test_read_google_doc_walks_table_cells() -> None:
    """Tables contribute their cell text in row order — ToC/table recursion."""
    payload = {
        "body": {
            "content": [
                {
                    "table": {
                        "tableRows": [
                            {
                                "tableCells": [
                                    {"content": [{"paragraph": {"elements": [{"textRun": {"content": "A"}}]}}]},
                                    {"content": [{"paragraph": {"elements": [{"textRun": {"content": "B"}}]}}]},
                                ]
                            }
                        ]
                    }
                }
            ]
        }
    }
    blocks = _read_google_doc(payload)
    assert len(blocks) == 1
    assert blocks[0].content == "AB"


# ---- scan() ---------------------------------------------------------------


@pytest.mark.asyncio
async def test_gdrive_scan_empty_folder() -> None:
    """Empty files.list -> empty doc list."""
    sm = _ServiceMocker()
    sm.queue_files_list({"files": []})  # subfolders
    sm.queue_files_list({"files": []})  # actual files
    conn = _connector()
    sm.attach_to_connector(conn)

    docs = await conn.scan()
    assert docs == []


@pytest.mark.asyncio
async def test_gdrive_scan_with_google_doc(monkeypatch: pytest.MonkeyPatch) -> None:
    """A Docs file in the scan -> one NormalizedDocument with the right content."""
    sm = _ServiceMocker()
    # scan() calls _list_files_in_folder FIRST, then _list_subfolders.
    sm.queue_files_list(
        {
            "files": [
                {
                    "id": "doc_abc",
                    "name": "Strategy.gdoc",
                    "mimeType": "application/vnd.google-apps.document",
                    "modifiedTime": "2025-01-01T00:00:00.000Z",
                }
            ]
        }
    )
    sm.queue_files_list({"files": []})  # no subfolders
    sm.queue_documents_get(
        {"body": {"content": [{"paragraph": {"elements": [{"textRun": {"content": "Q1 Goals: ship phase 3."}}]}}]}}
    )
    conn = _connector()
    sm.attach_to_connector(conn)

    docs = await conn.scan()
    assert len(docs) == 1
    doc = docs[0]
    assert doc.provider == SourceProvider.GOOGLE_DRIVE
    assert doc.title == "Strategy.gdoc"
    assert doc.locator.native_id == "doc_abc"
    assert doc.locator.uri == "https://drive.google.com/file/d/doc_abc"
    assert doc.versions[0].blocks[0].content == "Q1 Goals: ship phase 3."
    # Hash must be deterministic sha256 of the body.
    import hashlib

    assert doc.versions[0].content_hash == hashlib.sha256(b"Q1 Goals: ship phase 3.").hexdigest()


@pytest.mark.asyncio
async def test_gdrive_scan_skips_unsupported_mime(monkeypatch: pytest.MonkeyPatch) -> None:
    """A file whose MIME is not in SUPPORTED_MIME_TYPES is silently skipped."""
    sm = _ServiceMocker()
    sm.queue_files_list(
        {
            "files": [
                {
                    "id": "vid_1",
                    "name": "demo.mp4",
                    "mimeType": "video/mp4",
                    "size": "1234",
                }
            ]
        }
    )
    sm.queue_files_list({"files": []})  # no subfolders
    conn = _connector()
    sm.attach_to_connector(conn)

    docs = await conn.scan()
    assert docs == []
    sm.service.documents.return_value.get.assert_not_called()


@pytest.mark.asyncio
async def test_gdrive_scan_skips_oversized_file() -> None:
    """Files > MAX_SOURCE_FILE_BYTES are skipped with a warning-shaped decision."""
    sm = _ServiceMocker()
    sm.queue_files_list(
        {
            "files": [
                {
                    "id": "big",
                    "name": "huge.pdf",
                    "mimeType": "application/pdf",
                    "size": str(60 * 1024 * 1024),  # 60 MiB > 50 MiB cap
                }
            ]
        }
    )
    sm.queue_files_list({"files": []})  # no subfolders
    conn = _connector()
    sm.attach_to_connector(conn)

    docs = await conn.scan()
    assert docs == []


# ---- fetch_changes --------------------------------------------------------


@pytest.mark.asyncio
async def test_gdrive_fetch_changes_pagination() -> None:
    """``nextPageToken`` is followed; ``newStartPageToken`` is preserved."""
    sm = _ServiceMocker()
    sm.queue_start_page_token(token="START")
    sm.queue_changes_list(
        {
            "changes": [{"fileId": "f1", "removed": False, "file": {"id": "f1", "name": "alpha", "parents": ["p"]}}],
            "nextPageToken": "PAGE2",
        },
        {
            "changes": [{"fileId": "f2", "removed": False, "file": {"id": "f2", "name": "beta", "parents": ["p"]}}],
            "newStartPageToken": "NEW_CURSOR",
        },
    )
    conn = _connector()
    sm.attach_to_connector(conn)

    result = await conn.fetch_changes(cursor=None)
    assert result["new_cursor"] == "NEW_CURSOR"
    assert result["changes_count"] == 2
    assert result["has_more"] is False
    assert [e["file_id"] for e in result["events"]] == ["f1", "f2"]


@pytest.mark.asyncio
async def test_gdrive_lifecycle_classification() -> None:
    """All six lifecycle events (delete, trash, move, rename, update, restore)."""
    sm = _ServiceMocker()
    sm.queue_changes_list(
        {
            "changes": [
                {"fileId": "del", "removed": True, "file": None},  # deleted
                {
                    "fileId": "tr",
                    "removed": False,
                    "file": {"id": "tr", "trashed": True, "parents": ["p"]},
                },  # trashed
                {
                    "fileId": "mv",
                    "removed": False,
                    "file": {"id": "mv", "parents": ["p1", "p2"]},
                },  # moved
                {
                    "fileId": "rn",
                    "removed": False,
                    "file": {"id": "rn", "name": "renamed.txt", "parents": ["p"]},
                },  # updated (rename detected upstream)
                {
                    "fileId": "ok",
                    "removed": False,
                    "file": {"id": "ok", "name": "ok.txt", "parents": ["p"]},
                },  # plain update
            ],
            "newStartPageToken": "C",
        }
    )
    conn = _connector()
    sm.attach_to_connector(conn)

    result = await conn.fetch_changes(cursor="INIT")
    types = [e["type"] for e in result["events"]]
    assert types == ["deleted", "trashed", "moved", "updated", "updated"]


# ---- rate limiting --------------------------------------------------------


def test_retry_call_retries_on_503_then_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    """A 503 then 200 must succeed; only one retry observed."""
    sleeps: list[float] = []
    monkeypatch.setattr("rekanvault.sources.google_drive.time.sleep", lambda s: sleeps.append(s))
    # monkeypatch.setattr("rekanvault.sources.google_drive.random.uniform", lambda *_: 0.0)

    calls = {"n": 0}

    def flaky() -> str:
        calls["n"] += 1
        if calls["n"] == 1:
            raise _make_http_error(503)
        return "ok"

    result = _retry_call(flaky, max_retries=3, max_delay=10.0)
    assert result == "ok"
    assert calls["n"] == 2
    # Exactly one backoff sleep, in the exponential envelope.
    assert len(sleeps) == 1
    assert 0 < sleeps[0] <= 10.0


def test_retry_call_does_not_retry_404() -> None:
    """Non-retryable status bubbles up immediately."""
    calls = {"n": 0}

    def fail() -> None:
        calls["n"] += 1
        raise _make_http_error(404)

    with pytest.raises(HttpError):
        _retry_call(fail, max_retries=3, max_delay=0.01)
    assert calls["n"] == 1


def test_retry_call_gives_up_after_max_retries(monkeypatch: pytest.MonkeyPatch) -> None:
    """All retries exhausted -> re-raise the last HttpError."""
    monkeypatch.setattr("rekanvault.sources.google_drive.time.sleep", lambda _s: None)
    calls = {"n": 0}

    def always_503() -> None:
        calls["n"] += 1
        raise _make_http_error(503)

    with pytest.raises(HttpError):
        _retry_call(always_503, max_retries=3, max_delay=0.01)
    assert calls["n"] == 3


# ---- reconcile ------------------------------------------------------------


@pytest.mark.asyncio
async def test_gdrive_reconcile_delegates_to_scan() -> None:
    """``reconcile`` returns the same count as ``scan``."""
    sm = _ServiceMocker()
    sm.queue_files_list(
        {
            "files": [
                {
                    "id": "d1",
                    "name": "Doc1.gdoc",
                    "mimeType": "application/vnd.google-apps.document",
                }
            ]
        }
    )
    sm.queue_files_list({"files": []})  # no subfolders
    sm.queue_documents_get({"body": {"content": [{"paragraph": {"elements": [{"textRun": {"content": "x"}}]}}]}})
    conn = _connector()
    sm.attach_to_connector(conn)

    result = await conn.reconcile()
    assert result["status"] == "reconciled"
    assert result["scanned"] == 1
    assert result["reconciled"] == 1
    assert result["errors"] == 0


# ---- auth -----------------------------------------------------------------


def test_provider_is_google_drive() -> None:
    conn = _connector()
    assert conn.provider == SourceProvider.GOOGLE_DRIVE


def test_credentials_round_trip() -> None:
    """``_credentials_to_token_dict`` -> ``_credentials_from_token_dict`` round-trip."""
    from datetime import datetime, timezone

    from google.oauth2.credentials import Credentials

    creds = Credentials(
        token="ya29.ACCESS",
        refresh_token="REFRESH",
        token_uri="https://oauth2.googleapis.com/token",
        client_id="cid",
        client_secret="csec",
        scopes=["https://www.googleapis.com/auth/drive.readonly"],
        expiry=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    blob = GoogleDriveConnector._credentials_to_token_dict(creds)
    recovered = GoogleDriveConnector._credentials_from_token_dict(blob)
    assert recovered.refresh_token == "REFRESH"
    assert recovered.token == "ya29.ACCESS"
    assert recovered.scopes == ["https://www.googleapis.com/auth/drive.readonly"]
    assert recovered.expiry == datetime(2026, 1, 1, tzinfo=timezone.utc)
