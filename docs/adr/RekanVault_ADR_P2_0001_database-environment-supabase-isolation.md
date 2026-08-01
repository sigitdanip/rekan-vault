### RV-DEC-P2-0001 — Database environment: Dedicated Supabase project and schema isolation

- Phase: P2
- Status: Approved
- Owner: Sigit
- Date: 2026-08-02
- Decision required by: P2 database setup & migrations
- Context: RekanVault requires transactional PostgreSQL as its authoritative state store (RV-DEC-0008, RV-DEC-0010). SDLC Phase 2 requires locking the database environment boundary for the pilot.
- Options:
  1. Share an existing Supabase project with other applications using a schema prefix.
  2. Provision a dedicated Supabase project and database schema specifically for RekanVault.
- Chosen option: Option 2 — Separate dedicated Supabase project and schema.
- Why: Guarantees complete database-level isolation, independent connection pooling, isolated RLS policies, and clean backup/restore boundaries from unrelated company systems.
- Impact: Environment variables `RV_DATABASE_URL`, `RV_SUPABASE_URL`, `RV_SUPABASE_ANON_KEY`, and `RV_SUPABASE_SECRET_KEY` point to a dedicated RekanVault Supabase project.
- Reversal trigger: None (isolation is standard infrastructure policy).
- Related ADR/tests: RV-DEC-0008 (PostgreSQL authoritative store), RV-DEC-0010 (Supabase hosting).
