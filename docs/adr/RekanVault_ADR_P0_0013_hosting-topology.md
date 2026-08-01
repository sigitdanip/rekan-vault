### RV-DEC-0013 — Hosting topology: VPS runs application code only; Supabase holds PostgreSQL; Qdrant Cloud holds vector data

- Phase: P0
- Status: Approved
- Owner: Sigit
- Date: 2026-07-31
- Decision required by: P2 (database connection), P4 (Qdrant connection), P10 (deployment)
- Context: The Product Build Plan targets "one modular deployment on an approximately 8 GB VPS" (section 20.2) but never explicitly locked which components live on that VPS versus external managed services. As written, the plan already implies PostgreSQL and Qdrant are "external" to the VPS (section 20.2), and separately leaves Qdrant's deployment location as an open P4 decision (SDLC section 9: "Qdrant Cloud for pilot, or retain self-hosted Compose profile?"). Sigit's core concern is resource pressure: an 8 GB VPS is tight, and the VPS's job should be running the API, worker, and web processes (the "main engines") — not also hosting growing data stores (database records, vector embeddings, large extracted artifacts) that compete with those processes for RAM and disk.
- Options:
  1. Fully self-hosted: PostgreSQL and Qdrant both run on the VPS alongside the application code.
  2. Split: PostgreSQL on Supabase (managed cloud), Qdrant self-hosted on the VPS.
  3. Fully offloaded: PostgreSQL on Supabase, Qdrant on Qdrant Cloud — VPS runs only the API, worker, and Next.js processes.
- Chosen option: Option 3.
- Why: Keeps the 8 GB VPS's resource budget dedicated entirely to compute (API requests, background jobs, embedding/reranking inference) rather than splitting it between compute and growing data storage. This directly addresses the resource-pressure concern Sigit raised, and applies the same reasoning consistently to both PostgreSQL and Qdrant rather than solving it for one and leaving a gap in the other. It also keeps both derivatives-and-data stores on providers with their own managed backup/scaling tooling, reducing operational burden on the VPS itself.
- Impact:
  - `RV_DATABASE_URL` points to a Supabase-hosted PostgreSQL instance, not a local Postgres process on the VPS.
  - `RV_QDRANT_URL` points to Qdrant Cloud, not a local Qdrant container. The SDLC plan's self-hosted Qdrant Compose profile (section 20.2's Docker Compose orchestration) is retained only as a fallback/dev-local option, not the pilot/production default.
  - Normalized artifact storage (`RV_ARTIFACT_STORAGE_BACKEND`, currently defaulted to `filesystem`) still needs a decision — see follow-up below. If large extracted content (big PDFs, etc.) is expected, filesystem-on-VPS may reintroduce the exact storage pressure this ADR is meant to avoid.
  - Network latency between the VPS and both external services is a new consideration for every database query and every vector search — acceptable tradeoff for the storage/ops benefit, but worth monitoring once real latency numbers exist (P10 resource profiling).
  - This ADR also changes the framing of "self-hostable core" (product principle 15): the *code* remains self-hostable and vendor-replaceable (Supabase and Qdrant Cloud can both be swapped for self-hosted equivalents later, per RV-DEC-0010 and RV-DEC-0009's reversal triggers), but the default pilot deployment is not fully self-contained on one box.
- Reversal trigger: If Supabase or Qdrant Cloud costs, data residency requirements, or network latency prove unacceptable at pilot scale, fall back to self-hosting the affected component on the VPS or an additional VPS, using the already-designed Docker Compose profile.
- Related ADR/tests: RV-DEC-0008 (PostgreSQL as authoritative store — this ADR specifies *where* that PostgreSQL instance is hosted), RV-DEC-0009 (Qdrant rebuildability — this ADR specifies *where* Qdrant runs), RV-DEC-0010 (Supabase Auth — this ADR extends Supabase's role to database hosting, not just auth), P10 resource profiling (SDLC plan section 20.4).

### Follow-up decision needed

Normalized artifact storage (large extracted content, e.g. big PDFs) currently defaults to `filesystem` — i.e. local VPS disk — per `RV_ARTIFACT_STORAGE_BACKEND` (SDLC plan section 4.3). This was not addressed by this ADR and should be revisited under the same "keep the VPS lean" reasoning: if the pilot corpus includes large files, this could quietly reintroduce the storage pressure this decision was meant to solve. Recommend deciding this explicitly before P3 (Source Layer implementation) rather than defaulting silently.
