### RV-DEC-P3-0005 — Google Docs Multi-Tab Parsing and Citation Locators

- Phase: P3
- Status: Approved
- Owner: Sigit
- Date: 2026-08-02
- Decision required by: SDLC Plan Phase 3 Google Docs structured extraction
- Context: Modern Google Docs support multiple internal tabs within a single document object.
- Options:
  1. Ingest all tabs and preserve tab locators (`doc_id#tab_id`).
  2. Ingest main (first) tab only.
- Chosen option: Option 1 — Ingest all tabs and preserve tab locators.
- Why: Guarantees complete document content extraction and enables exact citation deep-linking to specific tabs where evidence originates.
- Impact: Google Docs extractor parses `documents.get` JSON structure recursively per tab and appends `#tab_id` to document reference locators.
- Reversal trigger: None (foundational to evidence completeness).
- Related ADR/tests: P3-T1, `rekanvault/sources/google_drive.py`.
