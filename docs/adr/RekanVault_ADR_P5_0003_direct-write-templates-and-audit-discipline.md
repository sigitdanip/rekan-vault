### RV-DEC-P5-0003 — Direct-Write Memory Templates and Audit Discipline

- Phase: P5
- Status: Approved
- Owner: Sigit
- Date: 2026-08-12
- Decision required by: Phase P5 direct human contribution and memory verification engine
- Context: Users need to create or edit institutional memory directly without waiting for automated source extraction, requiring author attribution, full confidence score (1.0), and structured audit logging.
- Options:
  1. Provide 6 initial direct-write templates (`Decision`, `Idea`, `Project`, `Risk`, `Lesson`, `Procedure`) via API/UI. Assign author user ID, confidence 1.0, and emit structured audit log entries (`rekanvault.contracts.audit`) for creation, verification, edit, dispute, and bulk invalidation.
  2. Unstructured markdown note-taking without schema typing or mandatory audit trail.
- Chosen option: Option 1 — 6 Direct-Write Templates with full schema typing and audit log integration.
- Why: Ensures direct user knowledge contributions match the exact same schema structure as source-extracted memories, while maintaining an immutable audit log of who created, verified, or invalidated each item.
- Impact: `rekanvault/memory/direct.py` service, API router `POST /api/v1/memory/direct`, and audit event bindings added.
- Reversal trigger: If template schemas need customization per organization or domain workspace.
- Related ADR/tests: P5-T8 (direct write author & audit), P5-T10 (verification audit record), P5-T11 (bulk invalidation audit record).
