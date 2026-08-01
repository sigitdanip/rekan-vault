### RV-DEC-0010 — Supabase provides authentication and PostgreSQL hosting

- Phase: P0
- Status: Approved
- Owner: Imi; ratified for execution by Sigit
- Date: 2026-07-31
- Decision required by: P2 (identity and authorization foundation)
- Context: RekanVault needs user authentication, session handling, and a managed PostgreSQL instance with row-level security support. Building custom auth from scratch, or self-hosting PostgreSQL without a managed auth layer, are both viable alternatives.
- Options:
  1. Custom-built authentication (password hashing, session tokens, etc.) plus self-hosted PostgreSQL.
  2. Supabase for both authentication (JWT-based, verified via JWKS) and managed PostgreSQL, using its row-level security (RLS) features for workspace isolation.
- Chosen option: Option 2.
- Why: Supabase provides production-grade JWT auth, RLS integration, and managed PostgreSQL out of the box, avoiding the security risk of hand-rolled authentication. It remains self-hostable in principle (Supabase itself is open-source), keeping RekanVault's core vendor-replaceable per product principle 15. A second, equally important reason emerged during hosting-topology discussion (see RV-DEC-0013): running PostgreSQL on Supabase rather than on the VPS keeps the VPS's tight ~8 GB resource budget dedicated to the API, worker, and web processes rather than competing with a growing database for RAM and disk.
- Impact: P2 introduces `RV_SUPABASE_URL`, `RV_SUPABASE_JWKS_URL`, JWT verification middleware, and RLS policies. Browser code uses only the publishable key (`NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY`) per Supabase's current key model — the secret/service-role key is server-only and restricted to migrations/admin jobs. This ties directly into RV-DEC-0004: since Sigit is the sole pre-merge reviewer, service-role key usage should stay narrowly scoped to reduce the blast radius of any missed review.
- Reversal trigger: If Supabase's hosted service becomes unsuitable (cost, data residency, or control requirements), self-hosted Supabase or a custom auth layer can be substituted since Supabase itself is open-source.
- Related ADR/tests: P2-GATE (JWT and RLS negative tests), RekanVault_ADR_P0_0004 (delivery ownership — service-role key handling ties into the sole-reviewer risk), RV-DEC-0013 (hosting topology — confirms and extends this ADR's PostgreSQL-on-Supabase choice with the explicit "keep the VPS lean" rationale).

### Update — 2026-07-31

RV-DEC-0013 (hosting topology) confirmed and reinforced this decision: PostgreSQL stays on Supabase, not the VPS. The original "Why" here was framed mainly around auth quality and RLS; the fuller reasoning — freeing the VPS's limited RAM/disk for compute rather than data storage — is now captured explicitly in RV-DEC-0013 and added above. No change to the chosen option itself.
