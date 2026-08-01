### RV-DEC-0012 — Every derived state has a deterministic rebuild or reconciliation path

- Phase: P0
- Status: Approved
- Owner: Imi; ratified for execution by Sigit
- Date: 2026-07-31
- Decision required by: P2 (job/outbox foundation), enforced through P4 (Qdrant rebuild), P6 (graph consistency checks), P10 (backup/restore)
- Context: RekanVault distinguishes canonical sources, normalized records, retrieval derivatives, and institutional memory (Product Build Plan section 1, "Non-negotiable internal separation"). Derivatives (chunks, embeddings, lexical indexes) can be lost or become stale. The system needs a defined answer for what happens when that occurs — silent data loss, manual reconstruction, or automatic, deterministic rebuild.
- Options:
  1. Treat derivative loss as an operational incident requiring manual intervention/reconstruction.
  2. Guarantee that every derivative (chunks, embeddings, lexical vectors, graph materialized views) can be deterministically rebuilt from PostgreSQL's normalized source records, with no data loss, via an explicit rebuild command.
- Chosen option: Option 2.
- Why: This is what makes RV-DEC-0009 (Qdrant rebuildability) and RV-DEC-0008's Apache AGE escalation path both actually safe to adopt — if a derivative's rebuild path isn't real, adding or changing retrieval/graph infrastructure later becomes risky. Rebuildability is the precondition, not a side effect, of being able to evolve RekanVault's storage strategy over time (product principle 13 and 16).
- Impact: Reprocessing must be idempotent (SDLC plan section 9's chunk-ID stability, section 11's active-version filters). P10 exit gate requires demonstrating both PostgreSQL backup/restore and full Qdrant rebuild from a clean state. Any future addition (e.g. Apache AGE materialized graph views) must be designed rebuildable from day one, not retrofitted.
- Reversal trigger: None anticipated — this is a durability guarantee underpinning multiple other ADRs, not an isolated tradeoff.
- Related ADR/tests: RV-DEC-0009 (Qdrant), RV-DEC-0008 (Apache AGE escalation path depends on this holding true), P4-GATE, P10-GATE (Scenario H, index loss).
