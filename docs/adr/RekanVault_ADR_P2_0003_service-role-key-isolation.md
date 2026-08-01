### RV-DEC-P2-0003 — Authorization: Strict isolation of Supabase service-role key (Risk R-003)

- Phase: P2
- Status: Approved
- Owner: Sigit
- Date: 2026-08-02
- Decision required by: P2 repository & API middleware implementation
- Context: `RV_SUPABASE_SECRET_KEY` bypasses PostgreSQL Row Level Security (RLS). Risk R-003 requires enforcing strict blast radius boundaries.
- Options:
  1. Allow API handlers to selectively use service-role key for administrative multi-tenant queries.
  2. Restrict service-role key strictly to database migration scripts and background admin worker routines; HTTP API endpoints must strictly use user JWTs with PostgreSQL RLS.
- Chosen option: Option 2 — Strict restriction of service-role key to DB migrations & admin workers.
- Why: Mitigates Risk R-003 by preventing any public API endpoint, request handler, or web client package from leaking or misusing the service-role key to bypass RLS.
- Impact: HTTP API handlers operate under caller user JWT context. RLS negative isolation tests implemented in P2 test suite.
- Reversal trigger: None (mandatory security invariant).
- Related ADR/tests: Risk R-003, Rule 3 in GEMINI.md.
