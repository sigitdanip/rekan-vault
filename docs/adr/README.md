# RekanVault — Architecture Decision Record Index

This index tracks every locked decision for RekanVault. Each row links to one ADR file.
Template for new ADRs: `template.md`.

## File naming convention

```
RekanVault_ADR_<Phase>_<4-digit-number>_<short-title>.md
```

- `<Phase>` — the phase the decision belongs to (`P0`, `P1`, `P2`, ...).
- `<4-digit-number>` — sequential within that phase, matches the `RV-DEC-####` ID used inside the file. Starts at `0001` per phase.
- `<short-title>` — lowercase, hyphen-separated, short.

Example: `RekanVault_ADR_P0_0001_repo-private-internal-use.md`

| ID | Decision | Phase | Status | Date | File |
|---|---|---|---|---|---|
| RV-DEC-0001 | Repository stays private; internal use only | P0 | Approved | 2026-07-31 | `RekanVault_ADR_P0_0001_repo-private-internal-use.md` |
| RV-DEC-0002 | Pilot corpus scope: 1 Drive folder tree + 1 Notion root page with nested databases | P0 | Approved | 2026-07-31 | `RekanVault_ADR_P0_0002_pilot-corpus-scope.md` |
| RV-DEC-0003 | UI language: English primary, Indonesian-ready strings | P0 | Approved | 2026-07-31 | `RekanVault_ADR_P0_0003_ui-language-english-primary.md` |
| RV-DEC-0004 | Delivery ownership: Sigit is sole pre-merge reviewer | P0 | Approved | 2026-07-31 | `RekanVault_ADR_P0_0004_delivery-ownership-sole-reviewer.md` |
| RV-DEC-0005 | Data classification labels: Public, Internal, Confidential, Restricted | P0 | Approved | 2026-07-31 | `RekanVault_ADR_P0_0005_data-classification-labels.md` |
| RV-DEC-0006 | RekanVault is one product, not several | P0 | Approved | 2026-07-31 | `RekanVault_ADR_P0_0006_one-product-not-several.md` |
| RV-DEC-0007 | Architecture is a modular monolith plus workers | P0 | Approved | 2026-07-31 | `RekanVault_ADR_P0_0007_modular-monolith-architecture.md` |
| RV-DEC-0008 | PostgreSQL is the authoritative store, with bounded-traversal + Apache AGE escalation path for deep graph queries | P0 | Approved | 2026-07-31 | `RekanVault_ADR_P0_0008_postgresql-authoritative-store.md` |
| RV-DEC-0009 | Qdrant is a rebuildable retrieval index, never the source of truth | P0 | Approved | 2026-07-31 | `RekanVault_ADR_P0_0009_qdrant-rebuildable-index.md` |
| RV-DEC-0010 | Supabase provides authentication and PostgreSQL hosting | P0 | Approved | 2026-07-31 | `RekanVault_ADR_P0_0010_supabase-auth-and-postgres.md` |
| RV-DEC-0011 | Extractors/embeddings/rerankers/vector stores/LLMs stay behind replaceable provider-adapter interfaces | P0 | Approved | 2026-07-31 | `RekanVault_ADR_P0_0011_provider-adapter-vendor-independence.md` |
| RV-DEC-0012 | Every derived state has a deterministic rebuild or reconciliation path | P0 | Approved | 2026-07-31 | `RekanVault_ADR_P0_0012_rebuildability-guarantee.md` |
| RV-DEC-0013 | Hosting topology: VPS runs app code only; Supabase holds PostgreSQL; Qdrant Cloud holds vector data | P0 | Approved | 2026-07-31 | `RekanVault_ADR_P0_0013_hosting-topology.md` |
| RV-DEC-0014 | Redaction policy: Confidential = content-masked, Restricted = fully hidden | P0 | Approved | 2026-07-31 | `RekanVault_ADR_P0_0014_redaction-policy.md` |
| RV-DEC-0015 | Golden-set ownership and change-review process: Sigit owns, changes require a stated reason | P0 | Approved | 2026-07-31 | `RekanVault_ADR_P0_0015_golden-set-ownership.md` |
| RV-DEC-0016 | Release evidence folder structure: `docs/release-evidence/`, one folder per phase, sub-folders per release candidate in P11 | P0 | Approved | 2026-07-31 | `RekanVault_ADR_P0_0016_release-evidence-structure.md` |
| RV-DEC-0017 | Frozen non-goals for `0.1.0`: 12 from Product Build Plan §8.3 + 4 surfaced during P0 | P0 | Approved | 2026-07-31 | `RekanVault_ADR_P0_0017_frozen-non-goals.md` |
| RV-DEC-P1-0001 | Repository visibility mechanics: Private until P11 release candidate | P1 | Approved | 2026-08-01 | `RekanVault_ADR_P1_0001_repo-visibility-private.md` |
| RV-DEC-P1-0002 | Monorepo orchestration: Plain uv and pnpm scripts without Turborepo | P1 | Approved | 2026-08-01 | `RekanVault_ADR_P1_0002_monorepo-orchestration-uv-pnpm.md` |
| RV-DEC-P1-0003 | UI visual direction: Quiet intelligence workspace baseline | P1 | Approved | 2026-08-01 | `RekanVault_ADR_P1_0003_ui-visual-direction-quiet-intelligence.md` |
| RV-DEC-P1-0004 | Legacy artifact retention & canonical package namespace | P1 | Approved | 2026-08-01 | `RekanVault_ADR_P1_0004_legacy-artifact-retention-canonical-package.md` |
| RV-DEC-P2-0001 | Database environment: Dedicated Supabase project and schema isolation | P2 | Approved | 2026-08-02 | `RekanVault_ADR_P2_0001_database-environment-supabase-isolation.md` |
| RV-DEC-P2-0002 | Authentication: Email magic link login with administrator-created memberships | P2 | Approved | 2026-08-02 | `RekanVault_ADR_P2_0002_first-login-magic-link-admin-memberships.md` |
| RV-DEC-P2-0003 | Authorization: Strict isolation of Supabase service-role key (Risk R-003) | P2 | Approved | 2026-08-02 | `RekanVault_ADR_P2_0003_service-role-key-isolation.md` |
| RV-DEC-P2-0004 | Security: Credential key custody with runtime envelope encryption | P2 | Approved | 2026-08-02 | `RekanVault_ADR_P2_0004_credential-key-custody-envelope-encryption.md` |
| RV-DEC-P2-0005 | Architecture: PostgreSQL-backed durable job queue (FOR UPDATE SKIP LOCKED) without Redis | P2 | Approved | 2026-08-02 | `RekanVault_ADR_P2_0005_job-engine-postgres-lease.md` |
| RV-DEC-P2-0006 | Storage: Local VPS filesystem for normalized extracted artifacts | P2 | Approved | 2026-08-02 | `RekanVault_ADR_P2_0006_artifact-storage-vps-filesystem.md` |

## How this index works

- Every new architecturally significant decision gets a new `RV-DEC-####` file, numbered sequentially.
- Status starts at `Proposed` and moves to `Approved` once Sigit confirms, or `Reversed` if a later decision overturns it.
- A `Reversed` ADR is never deleted — a new ADR supersedes it and both remain in the index for audit history (this mirrors RekanVault's own product principle: "current truth does not erase history").
- When a coding agent's work forces a decision to change (e.g. a technical constraint discovered during implementation), Sulaiman updates the relevant ADR file and this index, then flags the change to Sigit for confirmation.

## Open / not yet recorded

All P0, P1, and P2 decisions are now recorded and approved as of RV-DEC-P2-0006 (2026-08-02). Remaining known upcoming decisions belong to P3+:

## Cross-ADR alignment log

Tracks when a new decision required updating earlier, already-approved ADRs (rather than leaving them silently stale).

- **2026-07-31** — RV-DEC-0013 (hosting topology) locked. Reviewed all prior ADRs for impact:
  - `0008` (PostgreSQL authoritative store) — updated. Flagged that the P6 deep-traversal benchmark must now account for Supabase network latency, not just local query time.
  - `0009` (Qdrant rebuildable index) — updated. Added cross-reference; core decision unaffected, hosting location now explicit.
  - `0010` (Supabase Auth + Postgres) — updated. Strengthened the "Why" to include the storage-pressure reasoning that RV-DEC-0013 made explicit; original ADR only captured the auth/RLS justification.
  - `0012` (rebuildability guarantee) — reviewed, no change needed. Decision is about *whether* rebuild paths exist, not *where* components are hosted.
  - `0001`–`0007`, `0011` — reviewed, no hosting-related content, no change needed.

- **RV-DEC-0008** commits P6 to running a real benchmark of 6-7 hop graph queries against pilot-scale fixtures before P6-GATE closes, with Apache AGE pre-approved as the first escalation step if PostgreSQL recursive CTEs prove too slow. This is not optional — track it as a P6 to-do.
- **RV-DEC-P2-0005** locks PostgreSQL as the durable job queue (`FOR UPDATE SKIP LOCKED`), but explicitly **pre-approves Redis (Celery / BullMQ) as the escalation path** if P10 resource profiling, soak testing, or real queue load proves PostgreSQL locking to be a bottleneck.
- **RV-DEC-0013 follow-up resolved by RV-DEC-P2-0006**: Normalized artifact storage location (`RV_ARTIFACT_STORAGE_BACKEND`) is locked to local VPS filesystem (`filesystem`), using `RV_ARTIFACT_STORAGE_PATH` with P10 disk usage profiling.
- **RV-DEC-0014** requires P4 (Search) and P6 (Graph) to implement Restricted-tier existence-hiding across every surface that could leak a hint (result counts, graph gaps, autocomplete, error-message wording) — not just the direct content-serving path. This is a stricter requirement than typical permission filtering and should get explicit test coverage, not be assumed to "come for free" from a basic permission check.
- **RV-DEC-0015** defers the actual writing of the ~100 golden questions to a dedicated future session, once the pilot Drive/Notion corpus is connected and synced (post-P3). This is a hard P4-GATE blocker (see traceability matrix Gap 1) — track it so it doesn't get forgotten once P3 wraps up.
