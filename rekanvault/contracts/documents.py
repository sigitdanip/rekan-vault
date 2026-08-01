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
    document_id: str
    workspace_id: str
    source_id: str
    title: str
    provider: SourceProvider
    locator: DocumentLocator
    active_version_id: str
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    versions: list[DocumentVersion] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
