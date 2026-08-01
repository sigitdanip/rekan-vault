### RV-DEC-P2-0006 — Storage: Supabase Storage buckets for normalized extracted artifacts

- Phase: P2
- Status: Approved
- Owner: Sigit
- Date: 2026-08-02
- Decision required by: RV-DEC-0013 follow-up & P3 (Source Layer implementation)
- Context: RV-DEC-0013 offloaded PostgreSQL to Supabase and vectors to Qdrant Cloud to keep the ~8 GB VPS lean, but left normalized artifact storage (`RV_ARTIFACT_STORAGE_BACKEND`) as an open follow-up. Storing large extracted files (PDF text blocks, inline images, parsed JSON artifacts) on local VPS disk risks exhausting local VPS storage under large pilot corpora.
- Options:
  1. Local VPS filesystem (`filesystem`).
  2. External S3-compatible cloud storage (AWS S3 / Cloudflare R2).
  3. Supabase Storage buckets (`supabase_storage`).
- Chosen option: Option 3 — Supabase Storage buckets (`RV_ARTIFACT_STORAGE_BACKEND=supabase_storage`).
- Why: Extends the existing Supabase project topology (RV-DEC-P2-0001) to object storage. Prevents local VPS disk bloat without introducing additional third-party cloud vendors or complex credentials.
- Impact: Environment variable `RV_ARTIFACT_STORAGE_BACKEND` defaults to `supabase_storage`. Extracted artifacts use bucket pathing under the workspace ID. Local `filesystem` backend is retained for dev/offline testing.
- Reversal trigger: Storage bandwidth or file size limits on Supabase free/pro tiers exceeding threshold.
- Related ADR/tests: RV-DEC-0013 (hosting topology), RV-DEC-P2-0001 (dedicated Supabase project).
