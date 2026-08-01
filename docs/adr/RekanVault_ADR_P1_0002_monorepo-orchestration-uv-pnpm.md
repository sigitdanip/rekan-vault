### RV-DEC-P1-0002 — Monorepo orchestration: Plain uv and pnpm scripts without Turborepo

- Phase: P1
- Status: Approved
- Owner: Sigit
- Date: 2026-08-01
- Decision required by: P1 build setup
- Context: RekanVault is a modular monolith containing a Python backend (`rekanvault`), TypeScript web app (`apps/web`), and shared packages (`packages/contracts`). SDLC Phase 1 requires establishing a monorepo orchestration strategy.
- Options:
  1. Introduce Turborepo for build orchestration and remote caching.
  2. Use plain `uv` for Python environment/packages and `pnpm` workspace scripts for JS/TS.
- Chosen option: Option 2 — Plain `uv` + `pnpm` recursive scripts without Turborepo.
- Why: Keeps build tooling minimal, fast, and dependency-light on a single VPS/developer machine without adding Turborepo configuration overhead for early phase codebases.
- Impact: Root `package.json` delegates commands (`build`, `lint`, `test`, `typecheck`) directly via `pnpm --recursive`. Python workflows use `uv run pytest`, `uv run ruff`, `uv run mypy`.
- Reversal trigger: If frontend/package build graph complexity significantly degrades CI build times in later phases (P7+).
- Related ADR/tests: RV-DEC-0007 (modular monolith architecture).
