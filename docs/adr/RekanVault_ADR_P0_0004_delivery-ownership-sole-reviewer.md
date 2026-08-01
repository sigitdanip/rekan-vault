### RV-DEC-0004 — Delivery ownership: Sigit is sole pre-merge reviewer

- Phase: P0
- Status: Approved
- Owner: Sigit
- Date: 2026-07-31
- Decision required by: P1
- Context: The SDLC plan's default recommendation is one technical owner per phase, plus a *mandatory independent review* for security-sensitive and data-migration changes — meaning a second human should review and be able to block such changes before they merge. RekanVault's work is produced by coding agents reporting to Sigit. Sigit will personally review and approve all changes, including security/migration work, before merge. Zuri and other stakeholders receive delivery after merge, for visibility, not as a blocking pre-merge gate.
- Options:
  1. Two-person gate: Sigit reviews, then Zuri (Direktur Teknologi) independently reviews and can block security/migration PRs before merge.
  2. Single-person gate: Sigit is the sole reviewer and approver for all changes; others are informed post-merge.
- Chosen option: Option 2.
- Why: Reflects the team's actual operating structure — Sigit is the accountable technical owner for this project, and a second formal blocking reviewer is not currently available or desired in the workflow.
- Impact: There is no second-person safety net before security-sensitive or data-migration code ships. This raises real risk specifically in P2 (credential encryption, RLS policies, JWT auth) and P10 (security hardening, secret scanning, access control) — a mistake in these areas that Sigit's own review misses will not be caught before merge.
- Reversal trigger: Recommended to revisit this decision specifically when entering P2 and P10 — these phases involve the highest-consequence security work, and pulling in a second reviewer (even informally) for those specific PRs is worth reconsidering even if the general policy stays single-reviewer.
- Related ADR/tests: P2 exit gate (RLS/authorization negative tests), P10 exit gate (security checklist).
