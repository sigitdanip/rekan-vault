# RekanVault — Requirements-to-Phase-and-Test Traceability Matrix

| Field | Value |
|---|---|
| Status | Living document — update if acceptance criteria or phase gates change |
| Source | Product Build Plan section 25 (First-Release Acceptance Criteria), cross-referenced against SDLC Plan phase gates |
| P0 to-do item | #6 — "Map Product Build Plan requirements to phases and test IDs" |
| Created | 2026-07-31 |

---

## Purpose

Every acceptance criterion in Product Build Plan section 25 must have a clear answer to: **which phase builds this, and what test proves it's actually true when P11 (pilot) checks the full list?** Without this mapping, "done" has no checkable meaning — you'd be trusting the system works rather than verifying it.

---

## Part A — First-release acceptance criteria (Product Build Plan §25)

| # | Acceptance criterion (Product Build Plan §25) | Target | Building phase | Proving gate / test |
|---|---|---|---|---|
| 1 | Source lifecycle: 100% of tested create, update, rename, move, trash, restore, delete, permission, access-loss transitions converge | 100% | **P3** | `P3-GATE` — "pilot Drive and Notion scopes converge after full lifecycle tests, duplicate delivery, missed signals, provider throttling, and forced worker downtime" |
| 2 | Stale evidence: no stale active chunk remains queryable after update/deletion/revocation/reconciliation | 0 stale chunks | **P4** | `P4-GATE` test plan — "stale/revoked evidence negative tests"; also re-verified at P3→P4 boundary since it depends on P3's lifecycle convergence |
| 3 | Retry safety: duplicate processing creates no duplicate active version/chunk/memory/event | 0 duplicates | **P2** (idempotency foundation) verified through **P3–P5** | `P2-GATE` — "duplicate idempotency key returns the original result"; `P3-GATE` — "duplicate/delayed/out-of-order event property tests"; `P5-GATE` — "duplicate extraction replay" |
| 4 | Retrieval recall: at least 85% Recall@10 on golden question set | ≥85% | **P4** | `P4-GATE` — "initial golden set reaches Product Build Plan retrieval and citation targets" — **depends on golden set existing (see to-do #7, not yet done)** |
| 5 | Citation resolution: at least 95% of benchmark citations open correct source/location | ≥95% | **P4** | `P4-GATE`, same golden-set dependency as above |
| 6 | Answer support: at least 90% of material benchmark claims supported by evidence | ≥90% | **P7** | `P7-GATE` — "answer-support... benchmarks meet Product Plan targets" |
| 7 | Unknown behavior: unsupported questions return explicit insufficient-evidence state | Explicit state, no fabrication | **P4** (typed result defined) + **P7** (used in Ask) | `P4-GATE` (evidence packet insufficiency), `P7-GATE` — "unknown-behavior benchmarks" |
| 8 | Memory evidence: 100% of verified source-derived memories retain valid evidence links | 100% | **P5** | `P5-GATE` — "100% of verified source-derived memories resolve to valid authorized evidence" |
| 9 | Entity precision: at least 95% precision for auto-accepted entity matches | ≥95% | **P6** | `P6-GATE` — "entity and temporal golden fixtures pass"; release metrics (SDLC §16) restate this explicitly |
| 10 | Temporal integrity: historical states never presented as current without explicit request | No false-current | **P6** | `P6-GATE` — "graph neighborhoods are explainable, bounded, reversible" (reversibility implies correct current/historical distinction); tested via P6 test plan "historical query returns the correct past state" |
| 11 | Decision resolution: golden decision histories identify correct current/reversed/superseded/in-review state | 100% of golden set | **P6** | `P6-GATE`, same as above — depends on golden decision fixtures existing (to-do #7) |
| 12 | Contradiction visibility: all seeded high-impact contradictions surfaced or routed to review | 100% | **P7** | `P7-GATE` — "contradiction... benchmarks meet Product Plan targets"; P7 test plan — "conflicting Drive/Notion evidence" |
| 13 | Permission isolation: zero unauthorized source/memory/edge/backlink/context/answer/skill exposure | Zero leakage | **Cross-cutting: P2 (RLS foundation) through P9 (skill permissions)** | `P2-GATE` (RLS negative tests), `P6-GATE` (permission-safe neighborhoods), `P7-GATE` (permission benchmarks), `P9-GATE` (permission-safe skill evidence), consolidated at `P10-GATE` security checklist and restated as a release metric (SDLC §16: "Permission leakage: zero") |
| 14 | Workspace completion: user can connect/search/ask/inspect/capture/review/link/supersede/trace via UI | Full loop, no CLI/DB needed | **P8** | `P8-GATE` — "representative user completes the Product Plan workspace acceptance workflow without engineering assistance" |
| 15 | Skill evidence: high-confidence skill progression always resolves to defined evidence or approval | 100% | **P9** | `P9-GATE` — "skill progress and recommendations are... evidence-backed, reviewable, permission-safe" |
| 16 | Audit coverage: every high-impact action records actor/action/time/reason/pipeline versions/state refs | 100% of high-impact actions | **P2** (audit foundation) verified through **P10** | `P2-GATE` — "audit records exist for every seeded high-impact mutation"; consolidated check at `P10-GATE` security checklist |
| 17 | Recovery: PostgreSQL backup restore and Qdrant rebuild demonstrated | Both demonstrated | **P10** | `P10-GATE` — "backup/restore and index rebuild are demonstrated" |
| 18 | Resource fit: first release operates reliably on ~8 GB VPS with bounded workers | Reliable operation | **P10** (24-hour soak) | `P10-GATE` — "24-hour soak fits target resources with no unresolved critical/high issue" — **note: since RV-DEC-0013 moved PostgreSQL and Qdrant off the VPS, this criterion's meaning has narrowed to "API + worker processes fit the VPS," not "everything fits the VPS." Worth confirming this reinterpretation is intentional — see note below.** |

---

## Part B — First-release user outcome (Product Build Plan §8.1)

This is a separate, more basic list — "can the product do the ten fundamental things at all" — distinct from §25's percentage-based acceptance targets. Missed in the first pass of this matrix; added on recheck.

| # | User outcome (§8.1) | Building phase | Proving gate / test |
|---|---|---|---|
| 1 | Connect Drive and Notion | **P3** | `P3-GATE` |
| 2 | See successful synchronization and source health | **P3** (backend) + **P7/P8** (Sources UI, though a thin version exists earlier per P3 to-do "Build Sources UI") | `P3-GATE`; full UI at `P8-GATE` |
| 3 | Search or ask questions across both sources | **P4** (Search) + **P7** (Ask) | `P4-GATE`, `P7-GATE` |
| 4 | Open exact citations | **P4** | `P4-GATE` — "citation resolution" |
| 5 | View extracted decisions, claims, entities, projects, topics, risks, lessons, skills | **P5** (memory types exist) + **P8** (Vault pages to view them) | `P5-GATE`, `P8-GATE` |
| 6 | Correct or approve uncertain memories | **P5** (Review API) + **P8** (Review UI) | `P5-GATE`, `P8-GATE` |
| 7 | Browse backlinks, a bounded graph, and decision history | **P6** (graph/timeline backend) + **P8** (Graph UI, backlinks) | `P6-GATE`, `P8-GATE` |
| 8 | Create direct structured memories | **P5** (direct-write API) + **P8** (editor UI) | `P5-GATE`, `P8-GATE` |
| 9 | Build and inspect a basic evidence-backed SkillTree | **P9** | `P9-GATE` |
| 10 | Observe a source change propagate through retrieval and memory state | **Cross-cutting: P3 (change detection) → P4 (retrieval update) → P5 (memory re-evaluation)** | No single gate — this is really Scenario A/B/C behavior (see Part C below), first fully demonstrable once P5-GATE passes |

**Observation:** every item in this list requires at least two phases (a backend phase + a UI/experience phase) to be *actually usable* by a person, even though the backend alone can pass its own gate earlier. This confirms something already implicit in the SDLC's phase structure, but worth stating plainly: **P8 (workspace) is where most of §8.1 becomes real for an actual user**, not the individual backend phases. This aligns with — and reinforces — why the Leader persona's *full* pilot workflow could not start before P7/P8, as already noted in `RekanVault_Pilot_Workflows.md`.

---

## Part C — Reference End-to-end scenarios (Product Build Plan §26)

Eight named scenarios the plan requires the system to handle correctly. These are more concrete than §25's abstract targets and often exercise multiple phases' work together. Missed in the first pass; added on recheck.

| Scenario | Description (abridged) | Phases exercised | Proving gate / test |
|---|---|---|---|
| **A — Current decision** | A decision is recorded, then reversed by a later document; history preserved, current state updated, timeline/graph reflect the transition | **P5** (memory formation) + **P6** (temporal/current-state resolution) + **P7** (grounded answers reflect the update) | Closest existing test: `P6-GATE` "superseded/reversed decision resolves current state correctly"; `P7-GATE` contradiction/current-state benchmarks. **No single named gate fully covers the end-to-end scenario as written — recommend an explicit P7 or P8 test built from this exact scenario.** |
| **B — Complete source lifecycle** | Full lifecycle (create/edit/rename/move in/move out/restore/delete) converges correctly at every step across identity, versions, chunks, evidence, memory, permissions, events, UI | **P3** (lifecycle) → **P4** (evidence) → **P5** (memory bindings) → **P8** (UI state) | `P3-GATE` covers the source-layer part directly. The full chain through memory and UI isn't explicitly re-tested end-to-end anywhere named — **recommend a dedicated cross-phase regression test once P8 exists**, since P3-GATE alone only proves the source layer converges, not that memory/UI stay in sync with it. |
| **C — Missed Notion signal** | Missed webhook; safety polling/reconciliation produces the same state as direct processing | **P3** | `P3-GATE` — "missed signals" explicitly named; SDLC P3 test plan — "Missed Notion webhook repaired by poll/reconciliation" |
| **D — Insufficient evidence** | Unsupported question gets an honest "insufficient evidence" response, not a fabrication | **P4** (typed result) + **P7** (surfaced in Ask) | `P4-GATE`, `P7-GATE` unknown-behavior benchmark — same two-phase composition risk already noted as Gap 4 in the notes below |
| **E — Entity aliases** | Full name/nickname/title/abbreviation resolve correctly; ambiguous cases go to review | **P6** | `P6-GATE` — entity fixtures ("full name, nickname, role title, and organization acronym fixtures" explicitly in P6 test plan) |
| **F — Access revocation** | Revoked access immediately removes content from search/chat; independently-supported memories stay active | **P3** (revocation detection) + **P4** (immediate retrieval exclusion) + **P5** (memory re-evaluation) | `P3-GATE` (access-loss handling), `P4-GATE` (stale/revoked evidence tests), `P5-GATE` (source deletion with single vs. multiple remaining evidence anchors) — **three-phase composition, no single named end-to-end test; same class of gap as Scenario B** |
| **G — Skill progression** | Artifact/assessment demonstrates a skill; progress proposed, evidence shown, approval recorded | **P9** | `P9-GATE` |
| **H — Index loss** | Qdrant deleted; rebuilds from PostgreSQL, retrieval benchmarks reproduced within tolerance | **P4** (rebuild capability) + **P10** (demonstrated at scale) | `P4-GATE` — "Qdrant deletion and deterministic rebuild"; `P10-GATE` — "Qdrant rebuild demonstrated"; release metric in SDLC §16 |

**Pattern worth naming:** three of the eight scenarios (A, B, F) span three or more phases with no single named gate testing the full scenario end-to-end — see Gap 5 below.

---

### Gap 0 — First pass of this matrix only covered §25, missed §8.1 and §26
On first build, this matrix only mapped Product Build Plan section 25 (acceptance criteria table). Sigit asked "is that all?" which prompted a recheck — section 8.1 (first-release user outcome, 10 items) and section 26 (eight reference end-to-end scenarios) are also requirement sources and were missing. Both are now included as Part B and Part C above. Recorded here as a reminder to check *all* requirement-bearing sections, not just the one formatted as a clean table, when doing this kind of mapping in the future.

### Gap 1 — Golden set is a hard dependency for criteria #4, #5, #11, and indirectly others
Four separate acceptance criteria (Recall@10, citation resolution, decision resolution, and implicitly answer support) cannot be measured at all without a golden question/decision set existing. **P0 to-do #7 (golden-set ownership and change-review process) is not yet done** — this matrix confirms it's not just a "nice to have," it's a blocking dependency for verifying roughly a quarter of the acceptance criteria. Recommend prioritizing #7 soon.

### Gap 2 — RV-DEC-0013 changes what "resource fit" (#18) actually means
The original Product Build Plan criterion assumes PostgreSQL and Qdrant run on the same VPS as the application (its own architecture section 20.1 originally listed "External PostgreSQL and Qdrant" ambiguously). Since RV-DEC-0013 explicitly locked Supabase + Qdrant Cloud, the P10 soak test now only needs to prove the **API + worker processes** fit comfortably in ~8 GB — not the full data layer. This is very likely the right outcome (it's *why* RV-DEC-0013 was made), but it's worth Sigit explicitly confirming this reframing rather than it being an implicit side effect nobody stated out loud.

### Gap 3 — Permission isolation (#13) and audit coverage (#16) are cross-cutting, not single-phase
Unlike most criteria which map cleanly to one phase, these two are built incrementally across nearly the whole roadmap and only fully provable at P10. This means a partial regression could be introduced in, say, P7 and not get caught until P10's consolidated check — worth having lighter permission/audit spot-checks at each intermediate gate (P2, P6, P7, P9), not just relying on the final P10 pass. Several of these are already named in individual phase test plans; this matrix just makes the cross-cutting nature explicit.

### Gap 4 — Criterion #7 (unknown behavior) currently spans two phases without one clear "owning" gate
The typed insufficient-evidence result is defined at P4 (evidence layer) but only actually experienced by a user through P7 (Ask). If P4 defines it correctly but P7 doesn't correctly surface it in the answer flow, this criterion could silently fail even though both individual gates "passed." Recommend an explicit end-to-end check of this specific criterion at P7-GATE, not just trusting the two phases compose correctly.

### Gap 5 — No named gate tests full end-to-end scenarios that span 3+ phases
Scenarios A, B, and F (Part C) each require correct behavior across three or more phases (e.g. Scenario B: source lifecycle → evidence → memory → UI), but no single gate in the SDLC plan explicitly tests the *complete* scenario as narrated — only each phase's own slice. This is the same class of problem as Gap 4, just recurring at larger scale. A bug in how phases compose together (not within any single phase) could pass every individual gate and still fail the actual scenario. Recommend either: (a) adding explicit cross-phase scenario tests once enough of the system exists (likely at P8 or P11), or (b) consciously accepting that composition bugs may only surface during P11 pilot testing.

---

## Traceability from the other direction

For completeness: SDLC plan section 18 ("Cross-Phase Dependency Matrix") already covers *capability* dependencies (e.g. "Active evidence and citations → unlocks Source-backed memory and Ask"). This matrix is the complementary view — *acceptance criteria* dependencies, i.e. which measurable target depends on which phase. Both should be read together; neither replaces the other.
