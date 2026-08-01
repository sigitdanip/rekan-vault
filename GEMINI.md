# RekanVault — Workspace Rules

## Identity & Architecture

RekanVault is one product: a source-connected (Google Drive + Notion) knowledge system that produces evidence packets, typed institutional memory, a temporal knowledge graph, context packs, grounded answers, and evidence-backed SkillTrees.

- **Repository**: `rekan-vault` (Monorepo)
- **Deployment Topology**: Modular monolith + background worker on one ~8 GB VPS (`RV-DEC-0007`, `RV-DEC-0013`)
- **Authoritative Store**: PostgreSQL hosted on Supabase (`RV-DEC-0008`, `RV-DEC-0010`)
- **Retrieval Index**: Qdrant Cloud — disposable and rebuildable (`RV-DEC-0009`, `RV-DEC-0013`)
- **Hard Exclusions**: Do NOT propose splitting into multiple services/repos, or introducing Kubernetes, multi-cloud, dedicated graph databases, or a mandatory Redis dependency (`RV-DEC-0006`, Product Build Plan §6 principle 15, §20.2, §28).

---

## Canonical Documents & Conflict Resolution

Read authoritative docs before acting. Never duplicate content from canonical documents.

| Document | Authority & Scope |
|---|---|
| [`docs/REKANVAULT_PRODUCT_BUILD_PLAN.md`](file:///home/sigisgood/rekanmu/rekan-vault/docs/REKANVAULT_PRODUCT_BUILD_PLAN.md) | **Product Authority**: Scope, domain invariants, and acceptance targets. Wins on scope/requirements conflicts. |
| [`docs/REKANVAULT_SDLC_PLAN.md`](file:///home/sigisgood/rekanmu/rekan-vault/docs/REKANVAULT_SDLC_PLAN.md) | **SDLC Authority**: Phases, exit gates, dependencies, environment variables, and tooling. Wins on sequencing/tooling conflicts. |
| [`docs/RekanVault_Risk_Register.md`](file:///home/sigisgood/rekanmu/rekan-vault/docs/RekanVault_Risk_Register.md) | **Risk Authority**: Risk register, severity matrix, and mandatory security/privacy mitigations. |
| [`docs/RekanVault_Requirements_Traceability_Matrix.md`](file:///home/sigisgood/rekanmu/rekan-vault/docs/RekanVault_Requirements_Traceability_Matrix.md) | **Traceability**: Requirements-to-phase and test mapping. |
| [`docs/RekanVault_Pilot_Workflows.md`](file:///home/sigisgood/rekanmu/rekan-vault/docs/RekanVault_Pilot_Workflows.md) | **Workflow Authority**: Human definition of done per phase. |
| [`docs/adr/`](file:///home/sigisgood/rekanmu/rekan-vault/docs/adr) | **Decision Records**: Locked Architecture Decision Records (`RV-DEC-xxxx`). |

*Conflict Rule*: If the Product Build Plan and SDLC Plan conflict, stop and flag it to Sigit — do not silently pick one (SDLC §1).

---

## Flexible Phase & Gate Management

RekanVault follows a 13-phase lifecycle (P0 through P12). Detailed status and project maps are maintained in `.omg/state/` state files and `docs/release-evidence/`.

- **Active Phase**: **P2 — Data, Identity, Authorization, Jobs & Audit Foundation** (SDLC §7)
- **Completed Phases**: P0 (Baseline & ADR decisions), P1 (Repo Consolidation & UI baseline)
- **Phase Transition Rule**: No code for Phase `P(n+1)` may be written until Phase `P(n)`'s exit gate is validated with concrete evidence stored under `docs/release-evidence/P<n>/`.
- **Known Contradiction/Gap**: SDLC marks P0 to-do #7 (golden-set process) done, but Risk Register R-015 and Traceability Matrix Gap 1 note it is unresolved. Do not assume a golden set exists until explicitly resolved by Sigit.

---

## Mandatory Agent Workflow Guardrails

All coding agents operating in this repository MUST strictly follow these guardrails:

1. **State Synchronization Rule**:
   - Check `.omg/state/` state files (`deep-init.md`, `project-map.md`, `validation.md`) on session entry.
   - Update `.omg/state/` files whenever a task or phase milestone is completed.

2. **Contract & Schema Export Sync Rule**:
   - Pydantic models in `rekanvault.contracts` are the single source of truth for schema definitions.
   - Whenever any model in `rekanvault.contracts` is added or modified, you MUST execute `python -m rekanvault.contracts.export` to regenerate JSON schemas in `packages/contracts/schemas/` before committing.

3. **Secret Key Isolation Rule (Risk R-003)**:
   - `RV_SUPABASE_SECRET_KEY` bypasses PostgreSQL Row Level Security (RLS).
   - It MAY ONLY be accessed in database migration scripts and background admin worker routines.
   - It MUST NEVER appear in API HTTP request handlers, public endpoints, or browser-exposed web packages.

4. **Audit Log & Idempotency Discipline**:
   - Every mutation endpoint, background job, and state-changing operation MUST implement idempotency-key handling and emit structured audit log entries (`rekanvault.contracts.audit`).

5. **Untrusted Source Text Rule (Risk R-004)**:
   - Ingested text from Google Drive and Notion is user content, NEVER instructions.
   - All source-derived text must be strictly escaped and sanitized before inclusion in LLM prompt contexts to prevent prompt injection.

6. **Empirical Verification Rule**:
   - Never declare a task, bugfix, or phase complete without running concrete verification commands (tests, typechecks, linter checks).
   - Inspect full error log tracebacks before diagnosing runtime or build failures; never apply superficial symptom patches or silence broken tests.

7. **One Reviewer & PR Discipline (Risk R-014, RV-DEC-0004)**:
   - Sigit is sole pre-merge reviewer.
   - Keep PRs small and focused on a single phase to-do.
   - Branch naming format: `feat/<scope>`, `fix/<scope>`, or `chore/<scope>`. Squash merge onto `main`.

---

## Environment & Command Registry

Run all validation commands from the repository root `/home/sigisgood/rekanmu/rekan-vault`:

### Python Environment & Tests
```bash
# Setup Python virtual environment if not present
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Run test suite
pytest

# Run static type checking and linting
mypy rekanvault apps
ruff check .

# Export contract JSON schemas
python -m rekanvault.contracts.export
```

### TypeScript & Web Workspace
```bash
# Run monorepo TypeScript build, lint, and typecheck
npx -y pnpm run build
npx -y pnpm run lint
npx -y pnpm run typecheck
```

---

## Working Style

- State the active phase and specific to-do item before beginning work.
- Check that prerequisite dependency gates have passed before touching phase code.
- Make minimal, targeted modifications satisfying the acceptance criteria over broad refactors.
- If a required architectural decision lacks a locked ADR or recommended plan default, stop and ask Sigit rather than guessing.