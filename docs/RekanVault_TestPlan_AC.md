# RekanVault — Test Plan Acceptance Criteria

| Field | Value |
|---|---|
| Status | Living document — updated phase by phase, manually, right before or during that phase |
| Companion | `REKANVAULT_SDLC_PLAN.md` — test plan lines there carry matching IDs (e.g. `P2-T1`); this file defines what each ID's pass bar actually is |
| Created | 2026-08-02 |
| P0 to-do reference | Extends P0 to-do #6 ("Map Product Build Plan requirements to phases and test IDs") one level deeper — from *phase* traceability to *individual test-case* traceability |

---

## Purpose

The SDLC plan's test plan lines say **what** to test. This document says **what counts as passing**. Every test plan line in the SDLC gets a stable ID (`P<phase>-T<n>`); this file has one row per ID with the actual acceptance criterion, so a coding agent (or Sigit) never has to guess what "correct" means when a test is run.

## Relationship to other documents

- **`REKANVAULT_SDLC_PLAN.md`** — owns the test plan line wording and the ID. If a line's wording changes, edit it there; the ID stays the same unless the test case itself is fundamentally different.
- **`REKANVAULT_PRODUCT_BUILD_PLAN.md` §25 / §26** — the ultimate source of truth for numeric acceptance targets (Recall@10, citation resolution %, etc.). Where an AC below cites a percentage, it traces back to §25, not invented here.
- **`RekanVault_Requirements_Traceability_Matrix.md`** — maps requirements → phase → gate, one level up from this document (phase-level, not test-case-level). Read together: the matrix tells you *which phase and gate* prove a requirement; this file tells you *what result the test case itself must produce*.
- **`RekanVault_Risk_Register.md`** — where a gap is found while writing an AC (e.g. undefined behavior, missing owning phase), it's raised there, not silently resolved by guessing.

## How this document is maintained

This is **manually updated, one phase at a time**, right before that phase starts — never written in advance for all phases in one pass. Reasons:

- Requirements shift as earlier phases complete. P2 itself changed after P0 was written (job engine and artifact storage decisions were made during P2, not before).
- Writing detailed ACs for phases that are months away means guessing at implementation details not yet decided.
- Each phase-prep session should re-derive ACs fresh against current reality, not stale assumptions carried from P0.

**Process per phase, repeated at the start of every phase:**

1. Copy that phase's test plan lines from the SDLC doc.
2. Assign or confirm IDs (`P<phase>-T<n>`, sequential, never renumbered once assigned — only appended to).
3. For each line, write the AC and record its **Source**:
   - *Test line* — the pass bar is already explicit in the SDLC wording.
   - *Exit gate* — the pass bar comes from that phase's `P<n>-GATE` description.
   - *§25 / §26* — the pass bar is a numeric target from the Product Build Plan.
   - *Newly decided* — no existing document defined it; a decision was made during this AC-writing session and should be dated.
4. Anything without a traceable pass bar is marked **Status: Open** and must be resolved — by decision or by a flagged gap in the Risk Register — before that phase begins. Never guessed at silently.
5. If resolving a line requires changing the SDLC doc itself (new to-do, reworded test line, new ADR), update the SDLC doc in the same session. These two documents must never drift out of sync — an ID that exists in one and not the other is treated as a bug in this process.

---

## P2 — PostgreSQL, Identity, Authorization, Jobs, and Audit Foundation

**Status: complete** (P2 to-dos are checked off in the SDLC plan). ACs below were written retroactively during this review; `P2-T8` and `P2-T9` triggered corrections to the SDLC test plan itself (see SDLC change log v0.2).

| ID | Test line | Acceptance criterion | Source | Status |
|---|---|---|---|---|
| P2-T1 | Clean migration and upgrade from previous revision | `alembic upgrade head` against an empty database completes with zero errors. `alembic downgrade -1` followed by `alembic upgrade head` again is idempotent — schema state is identical to a fresh `upgrade head`. | Test line | Defined |
| P2-T2 | Concurrent active-version creation cannot violate uniqueness | Two simultaneous write attempts for the same document within the same corpus: exactly one succeeds, the other fails via a database constraint violation, not application-level locking alone. | Test line | Defined |
| P2-T3 | Duplicate idempotency key returns the original result | A second request using the same idempotency key and payload returns the exact stored response from the first request. No second row/side effect is created. | Test line | Defined |
| P2-T4 | Worker crash releases an expired lease safely | Killing a worker mid-job: after `RV_JOB_LEASE_SECONDS` elapses (default 300s), the job becomes claimable by a different worker. No duplicate side effects and no data corruption from the interrupted attempt. | Test line + env registry default (§4.3) | Defined |
| P2-T5 | Outbox event is never committed without state and vice versa | A forced failure injected between the domain-state write and the outbox-event write causes both to roll back in the same transaction. Neither can be observed to have committed alone. | Test line | Defined |
| P2-T6 | Viewer cannot cross workspace/corpus boundaries | A Viewer-role actor querying a workspace/corpus they are not a member of receives an empty result set or 403 — enforced at the PostgreSQL RLS layer, verified by a test that bypasses the application layer's own filtering to confirm RLS itself blocks it. | Test line | Defined |
| P2-T7 | Invalid/expired/wrong-issuer JWT is rejected | Three independent negative cases (invalid signature, expired token, wrong issuer) each return 401. None falls through to an authenticated request context. | Test line | Defined |
| P2-T8 | Credential re-encryption clears rows off an outgoing key before retirement; no row references an unconfigured key ID | Rotate through active → previous → drop: every credential row still encrypted under the outgoing key is re-encrypted onto the current active key **before** that outgoing key is removed from `RV_CREDENTIAL_KEY_ACTIVE`/`RV_CREDENTIAL_KEY_PREVIOUS`. At no point does any row reference a key ID outside the two currently configured. | Newly decided, 2026-08-02 — original wording ("decrypts only with approved active/previous key") did not define behavior once a key is fully retired; see ADR update to `RekanVault_ADR_P2_0004_credential-key-custody-envelope-encryption.md` | Defined |
| P2-T9 | Seeded P2-scope high-impact actions produce complete audit records | Seed only the §18.4 action types that actually exist at P2 — **permission widening** (grant changes) and **schema migration** — and confirm each produces one audit record with actor, action, target, time, reason, and pipeline/schema version populated. The remaining six §18.4 action types (verification, entity merge/unmerge, decision reversal/supersession, bulk invalidation, skill mastery approval, destructive purge, external-system writeback) are not testable yet because their underlying features don't exist until later phases — each gets its own test line in its owning phase (see distribution table below). Full cross-system rollup happens at `P10-GATE` per Traceability Matrix Gap 3. | Newly decided, 2026-08-02 — original wording ("every seeded high-impact mutation") implied testing all 8 action types at P2, which is impossible since 6 of them depend on features not built until P5/P6/P9 | Defined — scope narrowed from original SDLC wording |

### Audit-coverage distribution (from P2-T9 narrowing)

Tracks where each remaining §18.4 high-impact action type's audit-record test line will be added, so it doesn't get lost.

| §18.4 action type | Owning phase | Status |
|---|---|---|
| Permission widening | P2 (`P2-T9`) | Covered in P2 |
| Schema migration | P2 (`P2-T9`) | Covered in P2 |
| Verification of high-impact knowledge | P5 (`P5-T10`) | Assigned in SDLC & AC plan |
| Entity merge or unmerge | P6 (`P6-T9`) | Assigned in SDLC & AC plan |
| Decision reversal or supersession | P6 (`P6-T10`) | Assigned in SDLC & AC plan |
| Bulk invalidation | P5 (`P5-T11`) | Assigned in SDLC & AC plan |
| Skill mastery approval (Proficient/Teaching) | P9 (`P9-T8`) | Assigned in SDLC & AC plan |
| Destructive purge | **No owning phase identified** | Open gap — see `RekanVault_Risk_Register.md` R-018 |
| External-system writeback | **No owning phase identified**; may conflict with RV-DEC-0017's frozen non-goal ("automatic actions in external systems") | Open gap — see `RekanVault_Risk_Register.md` R-018 |
| Consolidated rollup (all 8 types) | P10 (`P10-T9`) | Assigned in SDLC & AC plan |

---

## P3 — Production Google Drive and Notion Lifecycle

**Status: In Progress** — Acceptance criteria elaborated at Phase 3 start.

| ID | Test line | Acceptance criterion | Source | Status |
|---|---|---|---|---|
| P3-T1 | Contract fixtures plus provider HTTP recordings with secrets removed. | Provider HTTP recordings (Google Drive API v3, Google Docs API v1, Notion API `2026-03-11`) and contract fixtures have all secrets (bearer tokens, secret keys) scrubbed/replaced with placeholders. Fixtures validate cleanly against Pydantic contract schemas. | Test line + `RV-DEC-P3-0001` + `RV-DEC-P3-0002` + `RV-DEC-P3-0005` | Defined |
| P3-T2 | Sandbox create, edit, rename, move, move out, restore, delete, and revoke. | Live or mock lifecycle mutations (create, edit content, rename title, move folder, move out of root, trash/archive, restore, revoke access) in Google Drive and Notion update active eligibility and record version changes without losing document identity. Notion attachment links preserved per `RV-DEC-P3-0006`. | Test line + `RV-DEC-P3-0006` + `P3-GATE` | Defined |
| P3-T3 | Duplicate/delayed/out-of-order event property tests. | Out-of-order, duplicate, or delayed webhook/event notifications for a single resource converge to identical final database state as sequential events, producing no duplicate active versions or orphaned outbox events. Cadence per `RV-DEC-P3-0003`. | Test line + `RV-DEC-P3-0003` | Defined |
| P3-T4 | Crash before and after cursor commit. | Interruption (worker crash) before cursor/start-page-token commit causes clean re-execution upon restart without duplicate active versions. Interruption after cursor commit resumes accurately from saved cursor without missing changes. | Test line + `P3-GATE` | Defined |
| P3-T5 | Provider 401/403/404/409/429/5xx behavior. | Provider status codes handle deterministically: 401/403 mark source credentials in error state; 404 deactivates document retrieval eligibility; 429/5xx execute bounded exponential backoff with jitter via `tenacity`; 409 handles concurrent revision conflict. | Test line + SDLC §8 | Defined |
| P3-T6 | Large/unsupported/corrupt file behavior. | Files exceeding `RV_MAX_SOURCE_FILE_BYTES` (50 MiB cap per `RV-DEC-P3-0004`), unsupported MIME types, or unparseable byte streams raise structured `FILE_TOO_LARGE` or `UNSUPPORTED_FORMAT` extraction diagnostic warnings without crashing worker execution. | Test line + `RV-DEC-P3-0004` | Defined |
| P3-T7 | Missed Notion webhook repaired by poll/reconciliation. | A dropped or unreceived Notion webhook event is detected and repaired by the 5-minute safety poll (`RV-DEC-P3-0003`) or daily full reconciliation, converging state to 100% agreement with provider inventory. | Test line + `RV-DEC-P3-0003` | Defined |
| P3-T8 | API/UI source health agrees with database state. | FastAPI source health API endpoints (`/sources/health`, `/sources/status`) and Next.js Sources UI reflect exact database state for connected roots, active sync status, freshness timestamps, and extraction warning counts. | Test line + SDLC §8 | Defined |

## P4 — Evidence Layer, Hybrid RAG, and Search

*(Placeholder — several of this phase's test lines depend on the golden question set, which does not exist yet per RV-DEC-0015. Cannot be fully populated until that dependency clears.)*

| ID | Test line | Acceptance criterion | Source | Status |
|---|---|---|---|---|
| — | — | — | — | Not yet elaborated |

## P5 — Typed Memory Formation and Review

*(Assigned audit-coverage test lines below. Full phase AC table elaborated before P5 starts.)*

| ID | Test line | Acceptance criterion | Source | Status |
|---|---|---|---|---|
| `P5-T10` | Verification of high-impact knowledge produces complete audit record | Verification of a high-impact memory item records an audit log entry with actor ID, timestamp, target memory ID, action (`VERIFICATION`), and decision metadata. | P2-T9 distribution / SDLC §18.4 | Defined |
| `P5-T11` | Bulk invalidation produces complete audit record | Bulk invalidation of memories or evidence items emits structured audit events recording the count of affected records, target scope, actor ID, and reason. | P2-T9 distribution / SDLC §18.4 | Defined |

## P6 — Entity Resolution, Temporal State, and Knowledge Graph

*(Assigned audit-coverage and benchmark test lines below. Full phase AC table elaborated before P6 starts.)*

| ID | Test line | Acceptance criterion | Source | Status |
|---|---|---|---|---|
| `P6-T9` | Entity merge or unmerge operation produces complete audit record | Executing an entity merge or unmerge emits an audit event linking primary entity ID, secondary entity ID(s), actor ID, timestamp, and audit trail. | P2-T9 distribution / SDLC §18.4 | Defined |
| `P6-T10` | Decision reversal or supersession produces complete audit record | Reversing or superseding a decision node records an audit entry with original decision ID, superseding decision ID, rationale, and actor ID. | P2-T9 distribution / SDLC §18.4 | Defined |
| `P6-T11` | Deep-traversal graph query benchmark executes within latency limits | Bounded deep-traversal graph queries execute under load within target performance limits (`RV-DEC-0008`). | RV-DEC-0008 benchmark | Defined |

## P7 — Context Packs, Grounded Answers, and Ask

*(Placeholder — depends on golden set, same as P4.)*

| ID | Test line | Acceptance criterion | Source | Status |
|---|---|---|---|---|
| — | — | — | — | Not yet elaborated |

## P8 — Integrated Human Workspace

*(Placeholder.)*

| ID | Test line | Acceptance criterion | Source | Status |
|---|---|---|---|---|
| — | — | — | — | Not yet elaborated |

## P9 — Evidence-Backed SkillTree

*(Assigned audit-coverage test line below. Full phase AC table elaborated before P9 starts.)*

| ID | Test line | Acceptance criterion | Source | Status |
|---|---|---|---|---|
| `P9-T8` | Skill mastery approval produces complete audit record | Approval of Proficient or Teaching skill mastery produces an audit record with candidate actor, approving reviewer, skill ID, stage, and timestamp. | P2-T9 distribution / SDLC §18.4 | Defined |

## P10 — Security, Governance, Observability, Recovery, and Deployment

*(Assigned audit rollup test line below. Full phase AC table elaborated before P10 starts.)*

| ID | Test line | Acceptance criterion | Source | Status |
|---|---|---|---|---|
| `P10-T9` | Consolidated audit rollup verifies complete coverage across §18.4 high-impact action types | System-wide audit verification test confirms all configured high-impact action types emit structured, sanitized audit events under end-to-end load. | P2-T9 distribution / SDLC §18.4 | Defined |

## P11 — Pilot, Release Candidate, and First Release

*(Placeholder.)*

| ID | Test line | Acceptance criterion | Source | Status |
|---|---|---|---|---|
| — | — | — | — | Not yet elaborated |

## P12 — Operate, Measure, and Extend

*(Placeholder — this phase is ongoing/non-terminal per its own exit gate. ACs here are added incrementally as each operational extension occurs, not upfront in one batch.)*

| ID | Test line | Acceptance criterion | Source | Status |
|---|---|---|---|---|
| — | — | — | — | Not yet elaborated |

---

## Change Log

| Version | Date | Change |
|---|---|---|
| 0.1 | 2026-08-02 | Created as companion to `REKANVAULT_SDLC_PLAN.md`. P2 fully populated (9 IDs). `P2-T8` and `P2-T9` required corrections to the SDLC plan's test plan wording — see SDLC change log v0.2. Raised `RekanVault_Risk_Register.md` R-018 for two §18.4 action types with no owning phase. P3–P12 seeded as placeholders per the phase-by-phase maintenance process. |
| 0.2 | 2026-08-02 | Assigned explicit test IDs in P5 (`P5-T10`, `P5-T11`), P6 (`P6-T9`, `P6-T10`, `P6-T11`), P9 (`P9-T8`), and P10 (`P10-T9`) for the high-impact action audit distribution and RV-DEC-0008 graph benchmark, preventing context loss. |