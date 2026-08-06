# AGENTS.md — Quickstart for OpenCode

**Full SDLC/workflow rules** → `GEMINI.md`. This file covers only what an agent needs to avoid mistakes when writing code.

## Architecture (not obvious from file names)

- **Modular monolith** on a single VPS. `rekanvault/` is the core Python library — every app imports it. Do NOT propose splitting into services or adding Redis/K8s/multi-cloud.
- **PostgreSQL = authoritative store** (Supabase). **Qdrant Cloud = disposable retrieval index** — rebuildable from Postgres, never the source of truth.
- `apps/api` = FastAPI (port 8000). `apps/worker` = background job runner. `apps/web` = Next.js 14 App Router (port 3000).
- `packages/contracts/schemas/` = auto-generated JSON schemas — never edit by hand.

## Commands (run from repo root)

```bash
# Python (use uv, not pip directly)
uv venv && source .venv/bin/activate && uv pip install -e ".[dev]"

# Run a single test file
pytest tests/path/to/test_file.py

# Lint + typecheck (order matters: ruff first, then mypy)
ruff check . && ruff format --check . && mypy rekanvault apps/api apps/worker

# Full CI check
pytest --cov=rekanvault --cov-report=term-missing && ruff check . && ruff format --check . && mypy rekanvault apps/api apps/worker && python -m rekanvault.contracts.export

# TypeScript (pnpm, not npm/yarn)
pnpm install && pnpm run typecheck && pnpm run build
```

## Critical gotchas

1. **Schema export sync**: After ANY Pydantic model change in `rekanvault/contracts/`, run `python -m rekanvault.contracts.export`. CI checks this. Missing export = broken build.
2. **`RV_SUPABASE_SECRET_KEY`**: Only in Alembic migrations and admin background workers. NEVER in API handlers or browser code. `grep` for this before opening a PR if you touched auth or DB code.
3. **Python 3.12 only** — `.python-version`, `pyproject.toml`, and CI all enforce this.
4. **mypy strict mode** — no `type: ignore` without a comment explaining why.
5. **Ruff line length 120**, rules E/F/I/B. E501 (line length) is suppressed globally.
6. **pytest asyncio_mode = auto** — async test functions work without `@pytest.mark.asyncio`.

## Environment

- Copy `.env.example` → `.env`. All config keys are prefixed `RV_` (backend) or `NEXT_PUBLIC_` (frontend).
- Database migrations: `alembic upgrade head` (run from repo root, `alembic.ini` auto-prepends `.` to sys.path).
- State tracking lives in `.omg/state/` — read `project-map.md` at session start for the current phase.

## Git conventions

- Branches: `feat/<scope>`, `fix/<scope>`, `chore/<scope>`. Squash-merge to `main`.
- Sigit is sole reviewer — PRs must be small, single-phase-todo focused.
- Every PR must cite the test-plan ID it addresses (e.g. `P2-T8`) from `docs/REKANVAULT_SDLC_PLAN.md`.
