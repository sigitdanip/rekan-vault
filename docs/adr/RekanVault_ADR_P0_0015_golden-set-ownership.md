### RV-DEC-0015 — Golden-set ownership and change-review process

- Phase: P0
- Status: Approved
- Owner: Sigit
- Date: 2026-07-31
- Decision required by: Before P4-GATE (first point the golden set is actually used); first batch should exist before P4 begins
- Context: Several first-release acceptance criteria (Product Build Plan §25 — Recall@10, citation resolution, decision resolution, answer support) can only be measured by running a golden set of known question/expected-answer/expected-evidence triples against the system. The golden set did not yet have a defined owner or a process for how its contents get changed over time.
- Options:
  1. No single owner; anyone on the team can add or edit golden questions freely.
  2. Sigit owns the golden set — writes the initial ~100 questions (exact, semantic, temporal, negative, permission categories per SDLC §9) once the pilot corpus (Drive folder + Notion page) is connected and visible, and any later change to an existing question's expected answer is documented with a stated reason, not silently edited.
- Chosen option: Option 2.
- Why: The golden set is only trustworthy as a measurement tool if its answer key isn't casually changed under pressure — e.g. "fixing" a failing benchmark by editing the expected answer instead of fixing the actual retrieval/answer bug. A single accountable owner, plus a lightweight discipline of recording *why* an expected answer changed, protects the golden set's integrity without adding heavy process overhead inappropriate for a small pilot team.
- Impact:
  - Golden questions are written against real pilot corpus content (not hypothetical content), meaning question-writing is sequenced to happen once P3 (source connection) has synced real content — practically, this means writing them in a dedicated session once the corpus is visible, not before.
  - A first batch must exist before P4-GATE, since P4-GATE cannot close without a measurable golden set (see `RekanVault_Requirements_Traceability_Matrix.md`, Gap 1).
  - Any change to an existing golden question's expected answer/evidence must include a brief recorded reason (e.g. "source document was legitimately updated on [date]" vs. "original expected answer was incorrect on review"). This can be a simple changelog entry within the golden-set file itself — no separate heavy review tooling required at pilot scale.
  - Golden set is expected to grow over time (SDLC §17, Phase 12 operating cadence: "monthly... golden-set additions") — this ADR's ownership and change-discipline applies to all future additions, not just the initial batch.
- Reversal trigger: If golden-set maintenance becomes a bottleneck once the team grows beyond the current pilot scale, revisit whether a second person should co-own or review golden-set changes — similar to the reconsideration point already flagged for RV-DEC-0004 (sole reviewer).
- Related ADR/tests: `RekanVault_Requirements_Traceability_Matrix.md` (Gap 1 — golden set as a hard dependency for multiple acceptance criteria), P4-GATE, P6-GATE, P7-GATE (all three consume the golden set).
