### RV-DEC-P2-0006 — Storage: Local VPS filesystem for normalized extracted artifacts

- Phase: P2
- Status: Approved
- Owner: Sigit
- Date: 2026-08-02
- Decision required by: RV-DEC-0013 follow-up & P3 (Source Layer implementation)
- Context: RV-DEC-0013 offloaded PostgreSQL to Supabase and vectors to Qdrant Cloud, but left normalized artifact storage location (`RV_ARTIFACT_STORAGE_BACKEND`) as an explicit follow-up decision.
- Options:
  1. Local VPS filesystem (`filesystem` under `RV_ARTIFACT_STORAGE_PATH`).
  2. External S3-compatible cloud storage (AWS S3 / Cloudflare R2).
  3. Supabase Storage buckets (`supabase_storage`).
- Chosen option: Option 1 — Local VPS filesystem (`RV_ARTIFACT_STORAGE_BACKEND=filesystem`).
- Why: Provides maximum I/O read/write speed for background extraction and worker processing, avoids external network latency/bandwidth overhead during heavy document parsing, and keeps local offline development completely self-contained.
- Impact: Environment variable `RV_ARTIFACT_STORAGE_BACKEND` defaults to `filesystem`, saving files under `RV_ARTIFACT_STORAGE_PATH`. Disk usage monitoring is included in P10 resource profiling to prevent VPS disk exhaustion.
- Reversal trigger: Measured VPS disk utilization exceeding threshold under large pilot corpora.
- Related ADR/tests: RV-DEC-0013 (hosting topology), P10 resource profiling.
