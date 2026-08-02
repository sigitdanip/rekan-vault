### RV-DEC-P3-0004 — Maximum Source File Size Ingestion Cap

- Phase: P3
- Status: Approved
- Owner: Sigit
- Date: 2026-08-02
- Decision required by: SDLC Plan Phase 3 ingestion limits
- Context: Need to establish maximum file size limit for document downloading and text extraction.
- Options:
  1. 50 MiB default cap (`RV_MAX_SOURCE_FILE_BYTES=52428800`), configurable lower per workspace.
  2. 25 MiB strict cap.
  3. 100 MiB+ high cap.
- Chosen option: Option 1 — 50 MiB default cap.
- Why: Accommodates large technical PDFs, multi-tab slide decks, and heavy docs while preventing memory spikes and OOM worker crashes on the 8 GB VPS.
- Impact: Ingestion pipeline rejects files over 50 MiB with an audited `FILE_TOO_LARGE` diagnostic warning.
- Reversal trigger: Pilot user requirement for ingesting larger media or CAD files.
- Related ADR/tests: P3-T6, `RV_MAX_SOURCE_FILE_BYTES`.
