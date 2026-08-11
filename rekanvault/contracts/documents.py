from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class SourceProvider(StrEnum):
    GOOGLE_DRIVE = "google_drive"
    NOTION = "notion"
    LOCAL_FILE = "local_file"


class DocumentLocator(BaseModel):
    provider: SourceProvider
    native_id: str
    uri: str
    path: str | None = None
    mime_type: str | None = None


class DocumentBlock(BaseModel):
    block_id: str
    block_type: str
    content: str
    sequence: int
    metadata: dict[str, Any] = Field(default_factory=dict)


class DocumentVersion(BaseModel):
    version_id: str
    document_id: str
    version_number: int
    content_hash: str
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    blocks: list[DocumentBlock] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class NormalizedDocument(BaseModel):
    document_id: str = Field(..., min_length=1)
    workspace_id: str = Field(..., min_length=1)
    source_id: str = Field(..., min_length=1)
    title: str = Field(..., min_length=1)
    provider: SourceProvider
    locator: DocumentLocator
    active_version_id: str = Field(..., min_length=1)
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    versions: list[DocumentVersion] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


# P3: Source file extraction limits (RV-DEC-P3-0004).
# 50 MiB — hardcoded because contracts must not import from apps.* (would
# create a circular import: apps -> rekanvault.contracts -> apps.config).
# Kept in sync with RV_MAX_SOURCE_FILE_BYTES in apps/api/config.py.
MAX_SOURCE_FILE_BYTES: int = 50 * 1024 * 1024  # 52_428_800

SUPPORTED_MIME_TYPES: dict[str, str] = {
    "application/vnd.google-apps.document": "Google Docs",
    "application/vnd.google-apps.spreadsheet": "Google Sheets",
    "application/vnd.google-apps.presentation": "Google Slides",
    "application/pdf": "PDF",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "DOCX",
    "text/markdown": "Markdown",
    "text/plain": "Plain Text",
}


class ExtractionWarning(BaseModel):
    """Non-fatal extraction issue raised by a connector (skip + continue)."""

    code: str
    message: str
    document_external_id: str
