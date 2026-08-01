### RV-DEC-0009 — Qdrant is a rebuildable retrieval index, never the source of truth

- Phase: P0
- Status: Approved
- Owner: Imi; ratified for execution by Sigit
- Date: 2026-07-31
- Decision required by: P4 (evidence/RAG layer)
- Context: RekanVault needs dense vector search for semantic retrieval. The question is whether the vector index is treated as authoritative data or as a disposable, rebuildable derivative of PostgreSQL.
- Options:
  1. Treat Qdrant as authoritative — if lost, data is permanently lost.
  2. Treat Qdrant as a rebuildable derivative — fully reconstructable from PostgreSQL and normalized artifact storage at any time.
- Chosen option: Option 2.
- Why: Semantic retrieval quality matters, but the vector index itself must never become a single point of permanent data loss. This also allows safe re-embedding when models change, without any risk to institutional memory.
- Impact: P4 must implement a "delete and rebuild" command with a comparison report (SDLC plan section 9 to-do list). P10 exit gate explicitly requires demonstrating Qdrant loss and rebuild before production release.
- Reversal trigger: None anticipated — this is a durability guarantee, not a performance tradeoff to revisit.
- Related ADR/tests: P4-GATE (Qdrant deletion and deterministic rebuild test), P10-GATE (Qdrant rebuild demonstrated), Scenario H in Product Build Plan (index loss), RV-DEC-0013 (hosting topology — specifies Qdrant runs on Qdrant Cloud rather than self-hosted on the VPS; this ADR's rebuildability guarantee is what makes that hosting choice safe to reverse later if needed).

### Update — 2026-07-31

RV-DEC-0013 (hosting topology) locked Qdrant Cloud as the default hosting location, superseding the earlier open question in SDLC plan section 9 ("Qdrant Cloud for pilot, or retain self-hosted Compose profile?"). This ADR's core decision — Qdrant is rebuildable, never authoritative — is unaffected by *where* Qdrant runs; if anything, hosting it on Qdrant Cloud makes the rebuild guarantee more important, not less, since the team has less direct operational visibility into a managed service.
