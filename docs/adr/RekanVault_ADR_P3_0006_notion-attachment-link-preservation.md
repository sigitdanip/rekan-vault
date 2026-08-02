### RV-DEC-P3-0006 — Notion Block Attachment Handling in Initial Release

- Phase: P3
- Status: Approved
- Owner: Sigit
- Date: 2026-08-02
- Decision required by: SDLC Plan Phase 3 Notion block parser
- Context: Notion page blocks may contain file attachments with short-lived (1-hour) AWS S3 URLs.
- Options:
  1. Preserve attachment links and metadata only (no binary file downloads).
  2. Download and parse all attached files recursively.
- Chosen option: Option 1 — Preserve attachment links and metadata only.
- Why: Prevents local VPS storage exhaustion and avoids background job complexity required to continuously renew expiring S3 URLs.
- Impact: Notion block parser stores file metadata and external attachment URLs; standalone attached files are not downloaded into local storage in 0.1.0.
- Reversal trigger: Post-0.1.0 feature request for inline attachment text extraction.
- Related ADR/tests: P3-T2, `rekanvault/sources/notion.py`.
