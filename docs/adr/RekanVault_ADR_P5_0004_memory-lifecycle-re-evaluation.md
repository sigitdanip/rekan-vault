### RV-DEC-P5-0004 — Source-Bound Memory Support Lifecycle & Re-evaluation Policy

- Phase: P5
- Status: Approved
- Owner: Sigit
- Date: 2026-08-12
- Decision required by: Phase P5 memory lifecycle management and evidence binding reconciliation
- Context: Ingested source documents change, update, or get deleted over time. Extracted memory records bound to these sources must reflect changes in evidence support without silently keeping unanchored claims as truth.
- Options:
  1. Maintain explicit `memory_evidence_bindings` junction rows linking memory items to PostgreSQL `chunk_id` locators. Upon source update, re-evaluate only memory bindings attached to changed block locators (`P5-T5`). Upon source deletion or access loss, transition memories with 0 remaining evidence anchors to `unsupported` state (`P5-T6`); memories with multiple remaining anchors retain `approved`/`valid` status with the deleted anchor binding removed.
  2. Permanently lock memory records once extracted, ignoring source updates or deletions.
- Chosen option: Option 1 — Source-bound evidence reconciliation with `unsupported` status transition on total anchor loss.
- Why: Implements core product invariant: "no unanchored memory silently claims truth." Preserves memory records for audit while transparently flagging lost evidence support.
- Impact: `rekanvault/memory/lifecycle.py` binding reconciler implemented and wired to document outbox events.
- Reversal trigger: If evidence re-evaluation causes excessive worker CPU/database load during large batch document updates.
- Related ADR/tests: P5-T5 (source edit affects only bound memories), P5-T6 (source deletion single vs multiple anchors).
