### RV-DEC-0017 — Frozen non-goals for version 0.1.0

- Phase: P0
- Status: Approved
- Owner: Sigit
- Date: 2026-07-31
- Decision required by: P0 (before implementation begins, to prevent scope drift)
- Context: Product Build Plan section 8.3 already lists explicitly deferred scope, but SDLC plan P0 to-do #9 requires this to be formally re-confirmed and frozen as a P0 artifact — meaning any of these items re-entering scope for `0.1.0` requires a deliberate decision (a new or reversed ADR), not a quiet drift during implementation by a coding agent or under delivery pressure.
- Options:
  1. Leave section 8.3 as informal guidance only, without a P0 artifact formally locking it.
  2. Freeze the list as an explicit ADR, re-confirmed for `0.1.0`, incorporating anything additionally surfaced during P0 decision-making that belongs in this list.
- Chosen option: Option 2.
- Why: A written-but-unlocked deferral list is easy to erode under pressure — a coding agent or a rushed decision could quietly start building toward one of these items without anyone deciding to reverse the deferral. Freezing it as a numbered ADR makes reversal a visible, deliberate act (a new ADR, or an explicit status change to this one), consistent with how every other locked decision in this project is handled.
- Chosen non-goals for `0.1.0` (from Product Build Plan §8.3, unchanged):
  1. Exact end-user ACL mirroring for every provider object.
  2. Spreadsheet cell-level ingestion.
  3. Slide-level extraction.
  4. OCR for scanned files.
  5. Audio and video transcription.
  6. Governed web research.
  7. Automatic actions in external systems.
  8. Multiple organizations with workload isolation.
  9. A dedicated graph database.
  10. Unbounded autonomous agents.
  11. Native editing of canonical Drive or Notion documents.
  12. Large-scale analytics and billing.
- Additional non-goals surfaced during P0 decision-making, added to this freeze:
  13. Public distribution or open-source release (RV-DEC-0001 — repository stays private, internal use only; no license decision needed for `0.1.0`).
  14. Adopting Apache AGE or any additional PostgreSQL graph extension now (RV-DEC-0008 — Apache AGE is a pre-approved *escalation path*, contingent on a P6 benchmark showing it's needed; it is explicitly not in scope for `0.1.0` unless that benchmark triggers it).
  15. Self-hosting PostgreSQL or Qdrant on the VPS (RV-DEC-0013 — both are cloud-hosted external services for `0.1.0`; self-hosted fallback profiles are retained in the repo but not the default deployment target).
  16. Full existence-hiding for Confidential-tier content (RV-DEC-0014 — only Restricted tier gets full existence-hiding; Confidential is content-masked only, by design, not as a temporary simplification).
- Impact: Any implementation work — by Sigit, by a coding agent, or proposed in a future session — that would build toward one of the 16 items above must be treated as a scope change requiring a new decision, not something to proceed on quietly. This list should be checked against periodically (e.g. at each phase gate) as a lightweight scope-drift guard.
- Reversal trigger: Any individual item can be un-deferred for a future version through a new ADR that explicitly supersedes its entry here — this ADR's role is to make that a visible, deliberate act, not to permanently forbid these items forever.
- Related ADR/tests: Product Build Plan section 8.3 (original source list), RV-DEC-0001, RV-DEC-0008, RV-DEC-0013, RV-DEC-0014 (sources of the four additional items).
