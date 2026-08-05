"""
Source API contracts (P3).

Typed request/response models for the sources router. Pydantic models
double as the JSON schemas exported by ``rekanvault.contracts.export``.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class RegisterSourceRequest(BaseModel):
    """Body for ``POST /api/v1/sources``."""

    provider: str = Field(min_length=1, description="Provider key — google_drive or notion")
    name: str = Field(min_length=1, max_length=255)
    root_external_id: str = Field(min_length=1, description="Provider-native ID of the root container")
    root_path: str = Field(min_length=1, description="Human-readable path/name for the root")
    config: dict[str, Any] = Field(default_factory=dict)


class SourceSummary(BaseModel):
    """Lightweight source row for the list endpoint."""

    source_id: str
    provider: str
    name: str
    status: str
    workspace_id: str
    created_at: datetime
    last_sync_at: datetime | None = None
    last_sync_status: str | None = None


class SourceRootEntry(BaseModel):
    external_id: str
    path_or_name: str
    created_at: datetime


class SyncJobEntry(BaseModel):
    sync_job_id: str
    job_type: str
    status: str
    started_at: datetime | None = None
    completed_at: datetime | None = None
    stats: dict[str, Any] = Field(default_factory=dict)


class SourceDetail(BaseModel):
    source_id: str
    workspace_id: str
    provider: str
    name: str
    status: str
    config: dict[str, Any] = Field(default_factory=dict)
    roots: list[SourceRootEntry] = Field(default_factory=list)
    cursor: str | None = None
    cursor_updated_at: datetime | None = None
    recent_jobs: list[SyncJobEntry] = Field(default_factory=list)


class SourceHealth(BaseModel):
    source_id: str
    status: str
    online: bool
    last_sync_at: datetime | None = None
    last_sync_status: str | None = None
    error_count: int = 0
    warning_count: int = 0
    cursor_freshness_seconds: int | None = None
    document_count: int = 0


class JobTriggerResponse(BaseModel):
    """Response for ``POST /sources/{id}/sync`` and ``/reconcile``."""

    sync_job_id: str
    job_type: str
    status: str


__all__ = [
    "JobTriggerResponse",
    "RegisterSourceRequest",
    "SourceDetail",
    "SourceHealth",
    "SourceRootEntry",
    "SourceSummary",
    "SyncJobEntry",
]
