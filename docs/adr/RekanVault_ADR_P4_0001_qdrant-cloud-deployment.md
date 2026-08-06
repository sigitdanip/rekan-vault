### RV-DEC-P4-0001 — Qdrant Cloud deployment for pilot retrieval index

- Phase: P4
- Status: Approved
- Owner: Sigit
- Date: 2026-08-06
- Decision required by: Phase P4 hybrid search and vector index setup
- Context: RekanVault runs on an ~8 GB VPS (RV-DEC-0013). Running a heavy vector database locally alongside PostgreSQL, FastAPI, workers, and background ML models would risk memory starvation.
- Options:
  1. Deploy a local Qdrant container on the VPS via Docker Compose.
  2. Use Qdrant Cloud cluster for pilot, keeping local Compose profile as fallback.
- Chosen option: Option 2 — Use Qdrant Cloud for pilot vector indexing.
- Why: Minimizes VPS RAM and CPU overhead, ensuring reliable performance under pilot load while adhering to RV-DEC-0009 (Qdrant is disposable and rebuildable from Postgres).
- Impact: Vector indexing, payload filtering, and search endpoints connect to Qdrant Cloud via `RV_QDRANT_URL` and `RV_QDRANT_API_KEY`.
- Reversal trigger: If external network latency to Qdrant Cloud violates query SLA targets or cloud cost limits are exceeded.
- Related ADR/tests: RV-DEC-0009, RV-DEC-0013, P4-T7 (Qdrant deletion and rebuild).
