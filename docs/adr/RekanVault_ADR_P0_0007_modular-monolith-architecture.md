### RV-DEC-0007 — Architecture is a modular monolith plus workers

- Phase: P0
- Status: Approved
- Owner: Imi; ratified for execution by Sigit
- Date: 2026-07-31
- Decision required by: P1 repository structure
- Context: Given RekanVault is one product (RV-DEC-0006), the internal architecture still needs a shape: microservices, a single undifferentiated monolith, or a modular monolith with a separate worker process.
- Options:
  1. Microservices per module (source, evidence, memory, graph, context, etc.), each independently deployed.
  2. Single undifferentiated monolith with no internal module boundaries.
  3. Modular monolith: one API deployment, one worker deployment, one Next.js deployment, with clear internal module boundaries in code (`rekanvault/sources/`, `rekanvault/evidence/`, `rekanvault/memory/`, etc.) but not separate network services.
- Chosen option: Option 3.
- Why: Preserves internal separation of concerns (needed for testability and future flexibility) without the operational cost of distributed systems — service discovery, network failure handling, cross-service transactions — which is not justified at the target scale (one workspace, ~8 GB VPS, small pilot team).
- Impact: Repository shape follows Product Build Plan section 22 (`apps/api`, `apps/worker`, `apps/web`, with `rekanvault/<module>/` internal packages). Split services only when measured scale, reliability, or ownership requires it (explicitly deferred, not ruled out).
- Reversal trigger: Measured scale, reliability, or team-ownership pressure that a modular monolith cannot satisfy — must be backed by actual metrics, not speculation.
- Related ADR/tests: P1-GATE (build/install all applications from one repository).
