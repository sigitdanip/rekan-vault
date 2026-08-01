### RV-DEC-P1-0004 — Legacy artifact retention & canonical package namespace

- Phase: P1
- Status: Approved
- Owner: Sigit
- Date: 2026-08-01
- Decision required by: P1 repository consolidation & migration
- Context: Prior to Phase 1 consolidation, legacy connector prototypes existed under legacy naming. SDLC Phase 1 required deciding artifact retention and runtime namespace policies.
- Options:
  1. Retain legacy runtime namespace with backward-compatibility compatibility shims.
  2. Preserve original legacy release ZIPs in static archive while standardizing strictly on canonical `rekanvault` package namespace.
- Chosen option: Option 2 — Static archive preservation of legacy ZIPs; single canonical `rekanvault` Python package at runtime.
- Why: Eliminates technical debt and dual-path code paths early, ensuring clean architecture across CLI, API, worker, and core modules.
- Impact: All imports use `rekanvault.*`. CLI entrypoint is `rekanvault`. No runtime aliases or shims maintained for pre-consolidation names.
- Reversal trigger: None (migration is complete and validated by 29 inherited tests).
- Related ADR/tests: RV-DEC-0006 (one product not several).
