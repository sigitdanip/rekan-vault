### RV-DEC-0005 — Data classification labels: Public, Internal, Confidential, Restricted

- Phase: P0 (labels), enforced at P2 schema
- Status: Approved
- Owner: Sigit
- Date: 2026-07-31
- Decision required by: P2 schema
- Context: The SDLC plan's default recommendation is a four-tier classification: Public, Internal, Confidential, Restricted. This affects permissions, logging, and export behavior throughout the system.
- Options:
  1. Adopt the plan's default four-tier model.
  2. Define a custom classification scheme (e.g. regulatory-driven labels).
- Chosen option: Option 1 — the default four labels, unchanged.
- Why: No regulatory or compliance requirement was identified that would need a different scheme. The default is standard and sufficient for the pilot's internal use case.
- Impact: P2 schema work (`documents`, `memories`, audit records, etc.) implements exactly these four labels as the classification field's allowed values.
- Reversal trigger: If a compliance or regulatory requirement emerges (e.g. handling of personal employee data under specific law), this should be revisited before P2 schema is finalized.
- Related ADR/tests: P2 schema work, redaction policy (not yet written — see ADR index "Open" section).
