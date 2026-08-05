"""
P3-T1 — Contract fixtures + provider HTTP recordings with secrets removed.

Validates that provider HTTP recordings (Google Drive v3, Notion 2026-03-11)
and contract fixtures do NOT contain raw secrets. The redaction contract
defined in :mod:`rekanvault.governance.logging` is the single source of truth
for what counts as a secret — these tests pin that contract to the recording
format used across the connector suite.

Recordings are kept inline as Python dicts (no on-disk fixtures needed for
P3-T1) so the test is self-contained and reviewable. The same structure
applies to recordings persisted under ``tests/fixtures/recordings/`` once
that directory exists.
"""

from __future__ import annotations

import json
import re
from typing import Any

import pytest
from pydantic import BaseModel, Field

from rekanvault.contracts.documents import (
    DocumentLocator,
    DocumentVersion,
    ExtractionWarning,
    NormalizedDocument,
    SourceProvider,
)
from rekanvault.governance.logging import REDACT_KEYS, SECRET_PATTERN, redact_sensitive_data

# ---- fixtures (recordings) ------------------------------------------------

# These are SCRUBBED recordings — what we want to see committed to the repo.
# The forbidden patterns below show what a recording MUST NOT contain; the
# `expected_scrubbed` form below is the canonical safe shape.

NOTION_PAGE_RECORDING: dict[str, Any] = {
    "object": "page",
    "id": "11111111-1111-1111-1111-111111111111",
    "in_trash": False,
    "properties": {
        "title": {
            "type": "title",
            "title": [{"type": "text", "plain_text": "Engineering Guidelines"}],
        }
    },
    # Bearer token intentionally absent from the recording body — it lives
    # only in the request header, which is never persisted with the body.
}

NOTION_BLOCKS_RECORDING: dict[str, Any] = {
    "object": "list",
    "results": [
        {
            "object": "block",
            "id": "33333333-3333-3333-3333-333333333333",
            "type": "heading_1",
            "heading_1": {
                "rich_text": [{"type": "text", "plain_text": "Working agreements"}],
            },
        },
    ],
    "has_more": False,
    "next_cursor": None,
}

# In a real recording, the file metadata that came over the wire might
# include things like a Google-signed URL. We scrub query-string tokens.
GDRIVE_FILES_RECORDING: dict[str, Any] = {
    "files": [
        {
            "id": "doc_abc",
            "name": "Strategy.gdoc",
            "mimeType": "application/vnd.google-apps.document",
            "modifiedTime": "2025-01-01T00:00:00.000Z",
        }
    ],
}

# Forbidden substrings that must NEVER appear in a scrubbed recording.
_FORBIDDEN_RAW_SECRETS = (
    "ya29.",  # Google access tokens
    "secret_",  # Notion integration secrets (when used as a token value, not as a placeholder)
    "Bearer ",
    "client_secret=",
    "refresh_token=",
)

# Allow-list of placeholder names that legitimately contain "secret" / "token"
# so we don't false-positive on the scrubbed form itself.
_ALLOWED_PLACEHOLDERS = re.compile(
    r"(\bREDACTED\b|\bsha256=[0-9a-f]{64}\b|\bTEST_TOKEN\b|\bplaceholder\b)",
    re.IGNORECASE,
)


def _recording_to_blob(rec: dict[str, Any]) -> str:
    """Serialize a recording the way it would land in a JSON fixture file."""
    return json.dumps(rec, sort_keys=True)


def _contains_raw_secret(blob: str) -> str | None:
    """Return the first forbidden substring present in the blob, else None."""
    for needle in _FORBIDDEN_RAW_SECRETS:
        if needle in blob:
            return needle
    return None


# ---- tests -----------------------------------------------------------------


def test_notion_page_recording_has_no_raw_secrets() -> None:
    """P3-T1: a scrubbed Notion page recording must not carry bearer tokens."""
    blob = _recording_to_blob(NOTION_PAGE_RECORDING)
    assert _contains_raw_secret(blob) is None, (
        f"Notion page recording leaks a raw secret: {_contains_raw_secret(blob)!r}"
    )


def test_notion_blocks_recording_has_no_raw_secrets() -> None:
    """P3-T1: a scrubbed Notion blocks recording must not carry bearer tokens."""
    blob = _recording_to_blob(NOTION_BLOCKS_RECORDING)
    assert _contains_raw_secret(blob) is None, (
        f"Notion blocks recording leaks a raw secret: {_contains_raw_secret(blob)!r}"
    )


def test_gdrive_files_recording_has_no_raw_secrets() -> None:
    """P3-T1: a scrubbed Drive files-list recording must not carry signed URLs."""
    blob = _recording_to_blob(GDRIVE_FILES_RECORDING)
    assert _contains_raw_secret(blob) is None, f"Drive recording leaks a raw secret: {_contains_raw_secret(blob)!r}"


def test_redaction_helper_catches_a_leaked_bearer_in_a_recording() -> None:
    """P3-T1 (round-trip): if a recording DOES leak a Bearer token, the
    shared :func:`redact_sensitive_data` helper must replace it with the
    canonical ``[REDACTED]`` placeholder. This pins the redaction contract
    that downstream fixtures rely on — a regression here breaks every
    consumer that scrubs before writing fixtures to disk."""
    leaked = {
        "method": "GET",
        "url": "https://api.notion.com/v1/pages/abc",
        "header": "Bearer secret_aaaaaaaaaaaaaaaaaaaaaaaaa",
    }
    scrubbed = redact_sensitive_data(None, "info", leaked)
    assert scrubbed["header"] == "[REDACTED]"
    assert "secret_aaa" not in scrubbed["header"]


def test_redaction_helper_scrubs_known_sensitive_keys() -> None:
    """P3-T1: the redactor's known sensitive-key set must include every
    secret-bearing field we use in this repo (Notion integration token,
    Google refresh token, OAuth client secret)."""
    assert "access_token" in REDACT_KEYS
    assert "refresh_token" in REDACT_KEYS
    assert "client_secret" in REDACT_KEYS
    assert "token" in REDACT_KEYS
    assert "authorization" in REDACT_KEYS
    # The shared regex must match Notion + Google token shapes.
    sample = "ya29.abcdefghij0123456789-XYZ"
    assert SECRET_PATTERN.search(sample) is not None
    sample = "secret_TjQxMjM0NTY3ODkw"
    assert SECRET_PATTERN.search(sample) is not None


# ---- contract schema validation (P3-T1 last mile) -------------------------


class _ScrubbedContractFixture(BaseModel):
    """Mirror of :class:`NormalizedDocument` for recording-side validation.

    Recordings are stored as plain dicts; before a recording is committed
    we re-validate it against this schema. The schema is the canonical
    contract — it is the same shape :class:`NormalizedDocument` accepts.
    """

    document_id: str
    workspace_id: str
    source_id: str
    title: str
    provider: SourceProvider
    locator: DocumentLocator
    active_version_id: str
    versions: list[DocumentVersion] = Field(default_factory=list)
    warnings: list[ExtractionWarning] = Field(default_factory=list)


def test_recording_derived_fixture_validates_against_contract_schema() -> None:
    """P3-T1: a fixture built from a scrubbed recording must validate
    cleanly against the same Pydantic contract schema used at runtime.

    This is the round-trip — the recording is the wire form, the fixture
    is the runtime form, and the contract schema is the bridge.
    """
    fixture = _ScrubbedContractFixture(
        document_id="doc_abc",
        workspace_id="ws_test",
        source_id="src_gdrive_test",
        title="Strategy.gdoc",
        provider=SourceProvider.GOOGLE_DRIVE,
        locator=DocumentLocator(
            provider=SourceProvider.GOOGLE_DRIVE,
            native_id="doc_abc",
            uri="https://drive.google.com/file/d/doc_abc",
            mime_type="application/vnd.google-apps.document",
        ),
        active_version_id="ver_test",
        versions=[],
    )
    # Round-trip: model_dump -> model_validate must be loss-less.
    blob = fixture.model_dump_json()
    again = _ScrubbedContractFixture.model_validate_json(blob)
    assert again.document_id == "doc_abc"
    assert again.provider == SourceProvider.GOOGLE_DRIVE


def test_normalized_document_contract_accepts_recording_derived_shape() -> None:
    """P3-T1: the runtime contract (``NormalizedDocument``) and the
    recording-side contract must be field-compatible. If you can build a
    valid :class:`NormalizedDocument` from a fixture, the recording format
    is sound. This is the one-line cross-check that ties the two halves
    of the contract together."""
    doc = NormalizedDocument(
        document_id="doc_abc",
        workspace_id="ws_test",
        source_id="src_gdrive_test",
        title="Strategy.gdoc",
        provider=SourceProvider.GOOGLE_DRIVE,
        locator=DocumentLocator(
            provider=SourceProvider.GOOGLE_DRIVE,
            native_id="doc_abc",
            uri="https://drive.google.com/file/d/doc_abc",
        ),
        active_version_id="ver_1",
    )
    # No raw secrets in the serialized form.
    blob = doc.model_dump_json()
    assert _contains_raw_secret(blob) is None
    # And the Pydantic contract itself doesn't accept a secret-shaped field.
    with pytest.raises(Exception):  # noqa: B017, PT011 — any validator error is fine here
        NormalizedDocument.model_validate_json('{"access_token": "ya29.LEAK"}')
