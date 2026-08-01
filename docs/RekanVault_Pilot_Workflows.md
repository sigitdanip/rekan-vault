# RekanVault — First-Release Persona and Pilot Workflows

| Field | Value |
|---|---|
| Related | RekanVault_ADR_P0_0006 through 0013 |
| Persona owner | Sigit |
| Status | Locked 2026-07-31 |
| P0 to-do item | #3 — "Define first-release persona and exact pilot workflows" |

---

## Primary persona: Leader / Decision-maker

Defined per Product Build Plan section 4: someone who needs to *"retrieve current decisions, rationale, risks, dependencies, and historical context."*

**What this persona is NOT:** an administrator managing source connections, sync health, or permissions day-to-day (that's a secondary/supporting role in this project — see ADR discussion, 2026-07-31).

**What "success" means for this persona:**
- Asks a question in plain language and gets a grounded, cited answer — not a pile of raw search results to sift through.
- Trusts the answer enough to act on it, because uncertainty and contradictions are surfaced explicitly rather than hidden.
- Can tell current state from historical state at a glance ("is this decision still valid, or was it reversed?").
- Rarely, if ever, needs to open Sources/Admin screens directly.

**Known constraint:** this persona's real workflow (Ask, grounded answers, decision timeline) is not buildable until **P7 (Context Packs and Ask)**. P3–P6 must be validated by their own exit-gate criteria and interim workflows below, not by the Leader persona directly, since the tools they'd need don't exist yet.

---

## Interim validation workflows (P3–P6)

These exist to give each phase something concrete to test against before the full Leader workflow is possible. They are run by Sigit (or a stand-in tester), not by the eventual pilot Leader user — think of these as pre-pilot smoke tests.

### P3 — Source Lifecycle (gate: pilot Drive/Notion scopes converge through full lifecycle, duplicate delivery, missed signals, throttling, downtime)

**Interim workflow — "Does the connector actually keep up with reality?"**
1. Connect the pilot Drive folder tree and the pilot Notion page (per RV-DEC-0002 scope).
2. Confirm initial scan completes and Sources UI shows correct document/page counts.
3. Manually edit a file in Drive and a database row in Notion; confirm the change is detected and reflected in sync status within the expected interval.
4. Manually rename, move, and trash a document in Drive; confirm identity is preserved and lifecycle state updates correctly.
5. Revoke access to one test file; confirm it's immediately excluded from future retrieval eligibility (even though retrieval doesn't fully exist yet — this is checked at the normalized-record level).
6. Force a worker restart mid-sync; confirm no duplicate processing occurs on resume.

This is not a Leader-persona workflow — it's an operator/tester workflow. No "ask a question" step exists yet, because there's nothing to ask.

### P4 — Evidence Layer, Hybrid RAG, Search (gate: live source change becomes searchable with correct citation; stale content disappears)

**Interim workflow — "Can I find the right passage and trust the citation?"**
1. Using the Search UI (not Ask — Ask doesn't exist yet), search for a known phrase that exists in the pilot corpus.
2. Confirm the top result is the correct passage, with a citation pointing to the exact source location.
3. Edit the source document; confirm the updated content becomes searchable and the old version's citation is no longer returned.
4. Search using an Indonesian-language query against English-language content (and vice versa) to sanity-check multilingual retrieval, since RekanVault must preserve both languages correctly (Product Build Plan section 4).
5. Search for something that doesn't exist in the corpus; confirm the system returns a typed "insufficient evidence" result rather than a weak/irrelevant guess.

This is the first point where a Leader-like question ("where did we discuss X?") becomes answerable — but only via Search, not Ask, and without synthesis.

### P5 — Typed Memory Formation and Review (gate: memory types meet extraction precision; 100% of verified source-derived memories have valid evidence)

**Interim workflow — "Does the system correctly turn evidence into structured memory?"**
1. Pick a document containing an obvious decision (e.g. "we decided to use X because Y").
2. Confirm the extraction pipeline proposes a Decision memory candidate with the correct evidence anchor.
3. As reviewer, approve, correct, or reject the candidate through the Review UI.
4. Directly author one memory manually (per the initial direct-write templates: Decision, Idea, Project, Risk, Lesson, or Procedure) and confirm it records the correct author, origin, and audit trail.
5. Edit the source document that a memory was extracted from; confirm the memory is flagged for re-review rather than silently going stale.

### P6 — Entity Resolution and Temporal Graph (gate: entity/temporal fixtures pass; graph neighborhoods are explainable, bounded, reversible, permission-safe)

**Interim workflow — "Can I trust the graph's picture of who/what/when?"**
1. Confirm two different names/aliases for the same real person or project resolve to one canonical entity.
2. Open a bounded neighborhood view for one entity; confirm it's readable and doesn't silently include anything outside test permissions.
3. Walk a known decision's timeline; confirm current vs. historical state is visually distinguishable.
4. **Run the deep-traversal benchmark committed in RV-DEC-0008** — a representative 6-7 hop query (e.g. a SkillTree prerequisite chain or a multi-step causal chain) — and record actual latency against Supabase-hosted PostgreSQL. This is a mandatory P6 checkpoint, not optional interim validation.

---

## Full pilot workflow (P7 onward) — the actual Leader persona test

This is what "pilot success" means once Ask and grounded answers exist (P7), running inside the full workspace (P8).

### Core workflow — "I need to know what we decided and whether it still holds"

1. **Leader opens Ask**, types a natural-language question about a real decision, risk, or project status from the pilot corpus (e.g. "What did we decide about X, and why?").
2. **RekanVault returns a grounded answer** with citations visible next to each claim.
3. **Leader checks currency** — the answer clearly states whether this is the current state, and flags if history/reversal exists.
4. **Leader opens a citation** to view the exact source passage and confirm it in context, without needing to search manually.
5. **Leader asks a follow-up** touching a related entity or project, testing whether context carries forward sensibly.
6. **Leader deliberately asks something outside the corpus** (a known-unanswerable question) and confirms RekanVault says so explicitly rather than guessing.
7. **Leader opens the decision timeline** (Vault/Graph) for one real decision, and confirms the rationale, alternatives, and current status are legible without needing to ask a follow-up question.
8. **Leader gives feedback** (thumbs up/down or correction) on one answer, testing that the feedback loop is real and not cosmetic.

### Secondary workflow — light review touch (still Leader, not Admin)

9. **Leader opens the Review queue** once, to see what's pending (even if they don't personally clear it), confirming visibility into uncertain/candidate knowledge is available to non-admin roles.

### Success criteria for this pilot workflow

Directly tied to the Product Build Plan's acceptance targets (section 25) and P7/P8 gates:
- At least 90% of material claims in answers are supported by returned evidence.
- At least 95% of citations open the correct source and location.
- Unsupported questions return an explicit insufficient-evidence state, never a fabricated answer.
- Leader completes steps 1–8 above without needing engineering assistance or database/CLI access (P8-GATE requirement).

---

## Open note

This document defines *what* the pilot workflows are. It does not yet define *who* the actual pilot Leader user will be (you, or someone else in the 3–5 person pilot group per SDLC section 16's recommendation) — that's a P11 decision, not P0, and doesn't block anything right now.
