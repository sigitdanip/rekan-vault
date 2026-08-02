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
| [`docs/RekanVault_TestPlan_AC.md`](file:///home/sigisgood/rekanmu/rekan-vault/docs/RekanVault_TestPlan_AC.md) | **Acceptance Criteria Authority**: The pass bar for every test-plan ID (`P<phase>-T<n>`) in the SDLC plan. Populated phase by phase, right before that phase starts — do not assume a future phase's row exists. |
| [`docs/RekanVault_Risk_Register.md`](file:///home/sigisgood/rekanmu/rekan-vault/docs/RekanVault_Risk_Register.md) | **Risk Authority**: Risk register, severity matrix, and mandatory security/privacy mitigations. |
| [`docs/RekanVault_Requirements_Traceability_Matrix.md`](file:///home/sigisgood/rekanmu/rekan-vault/docs/RekanVault_Requirements_Traceability_Matrix.md) | **Traceability**: Requirements-to-phase and test mapping. |
| [`docs/RekanVault_Pilot_Workflows.md`](file:///home/sigisgood/rekanmu/rekan-vault/docs/RekanVault_Pilot_Workflows.md) | **Workflow Authority**: Human definition of done per phase. |
| [`docs/adr/`](file:///home/sigisgood/rekanmu/rekan-vault/docs/adr) | **Decision Records**: Locked Architecture Decision Records (`RV-DEC-xxxx`). |

*Conflict Rule*: If the Product Build Plan and SDLC Plan conflict, stop and flag it to Sigit — do not silently pick one (SDLC §1).

---

## Phase & Gate State Management

RekanVault follows a 13-phase lifecycle (P0–P12), defined in `docs/REKANVAULT_SDLC_PLAN.md`.

**This file does not track live phase status.** Active phase, completed phases, and open gaps change over time; hardcoding them here means they go stale the moment a phase closes, and this file should not be relied on to self-update. That state lives in `.omg/state/`, checked and updated every session instead.

- **State files** (initialize if the directory or any file is missing — do not assume they exist):
  - `.omg/state/project-map.md` — current active phase, completed phases, phase-transition history.
  - `.omg/state/validation.md` — currently open gaps/contradictions (e.g. golden-set status, unresolved risks) and their resolution status.
  - `.omg/state/deep-init.md` — one-time session onboarding summary (canonical docs read, current repo structure).

  If none exist yet, create them using the template at the end of this section, seeded by actually counting `[x]` vs `[ ]` to-dos per phase in `docs/REKANVAULT_SDLC_PLAN.md` — never infer phase status from memory or from a prior session's claim.

- **Session Start Rule**: Read all three `.omg/state/` files before taking any action, every session, no exceptions.

- **Update Rule**: Whenever a to-do is completed, a phase gate is validated, or a new gap/contradiction is found, update the relevant `.omg/state/` file in the same session. Do not defer this and do not record it only in a PR description.

- **Conflict Rule**: If `.omg/state/project-map.md`'s claimed active phase disagrees with the SDLC plan's actual checkbox state, stop and flag it to Sigit rather than trusting either source silently — this exact drift has already happened once (P2 was marked complete in the SDLC plan while this file separately claimed it was still active).

- **Phase Transition Rule**: No code for Phase `P(n+1)` may be written until Phase `P(n)`'s exit gate is validated with concrete evidence stored under `docs/release-evidence/P<n>/`, and `.omg/state/project-map.md` reflects the transition.

**`.omg/state/project-map.md` starter template, if the file needs to be created:**

```markdown
# RekanVault — Project Phase State

| Field | Value |
|---|---|
| Last updated | <date, by which agent/session> |
| Active phase | <P<n> — verified against SDLC checkbox state, not assumed> |
| Completed phases | <list, each with the release-evidence folder that proves it> |

## Verification note
Active phase above was last cross-checked against `docs/REKANVAULT_SDLC_PLAN.md`
to-do checkboxes on <date>. If this file is more than one session old, re-verify
before trusting it.
```

**`.omg/state/validation.md` starter template, if the file needs to be created:**

```markdown
# RekanVault — Open Gaps and Contradictions

| ID | Description | Source | Status |
|---|---|---|---|
| <e.g. GAP-001> | <short description> | <ADR / Risk Register / Traceability Matrix reference> | Open / Resolved |
```

Seed this file's initial contents from currently known open items in `docs/RekanVault_Risk_Register.md` (all `Open` status risks) and `docs/RekanVault_Requirements_Traceability_Matrix.md` (Gaps 0–5) — do not leave it empty on first creation. This should also include, at minimum: P0 to-do #7's unresolved golden-set status (Risk R-015 / Traceability Gap 1), the P2 credential re-encryption backfill found during acceptance-criteria review (`P2-T8` in `RekanVault_Test_Plan_Acceptance_Criteria.md`), and R-018 (destructive purge / external-system writeback have no owning phase).

---

## Mandatory Agent Workflow Guardrails

All coding agents operating in this repository MUST strictly follow these guardrails:

1. **State Synchronization Rule**:
   - See "Phase & Gate State Management" above — session-start read, initialize-if-missing, and update-on-milestone rules for `.omg/state/` apply as mandatory guardrails, not just guidance.

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

8. **Test-Plan ID Citation Rule**:
   - Every SDLC test plan line has a stable ID (`P<phase>-T<n>`, e.g. `P2-T8`). Every PR that closes or partially addresses a test plan line MUST cite that ID in the PR description, not a paraphrase of the test line.
   - Before implementing behavior a test ID covers, check `docs/RekanVault_Test_Plan_Acceptance_Criteria.md` for that ID's row. If the row says "Not yet elaborated," stop and flag it — do not implement against a guessed pass bar.
   - If implementation reveals that a test line's ID needs a new sibling ID (a genuinely new test case), append the next number in sequence (e.g. add `P3-T9`, do not renumber existing IDs). Update both the SDLC plan and the AC doc in the same PR.

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
- Before marking a test plan line satisfied, confirm against its acceptance criterion in `docs/RekanVault_Test_Plan_Acceptance_Criteria.md` — the test plan line names the test, the AC doc defines what passing means.
- Make minimal, targeted modifications satisfying the acceptance criteria over broad refactors.
- If a required architectural decision lacks a locked ADR or recommended plan default, stop and ask Sigit rather than guessing.