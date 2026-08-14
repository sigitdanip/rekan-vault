### RV-DEC-P5-0001 — 18 Typed Memory Schemas and Review Queue Policy

- Phase: P5
- Status: Approved
- Owner: Sigit
- Date: 2026-08-12
- Decision required by: Phase P5 Typed Memory Formation and Review Engine
- Context: Generated summaries and LLM extractions must not become unverified silent truth. Knowledge items require explicit schema typing, field-level evidence anchoring, and governance over auto-commit vs mandatory human review.
- Options:
  1. Define 18 typed memory schemas (`Fact`, `Claim`, `Decision`, `Policy`, `Procedure`, `Event`, `Project`, `Task`, `Idea`, `Risk`, `Assumption`, `Lesson`, `Metric`, `Person`, `Organization`, `Topic`, `Asset`, `Skill`) using Pydantic V2 with `extra="forbid"`. Enforce mandatory human review queue (`pending_review`) for high-impact categories (`Decision`, `Policy`, `Permission`, `Risk`) and low-confidence candidates, while auto-committing low-impact deterministic metadata/entity mentions.
  2. Single generic key-value memory store with auto-committing all extracted LLM outputs.
- Chosen option: Option 1 — 18 Typed Memory Schemas with strict Pydantic V2 validation and impact-based review routing policy.
- Why: Prevents LLM hallucinations (`extra="forbid"` rejects unknown fields), guarantees exact evidence line-of-sight back to PostgreSQL `chunk_id` locators, and ensures critical decisions/policies require human sign-off before entering authoritative memory.
- Impact: `rekanvault/memory/` models defined; PostgreSQL tables for `typed_memories`, `memory_evidence_bindings`, and `memory_review_queue` created via Alembic migration `0003`.
- Reversal trigger: If schema strictness blocks valid source extractions or review queue volume exceeds human review throughput capacity.
- Related ADR/tests: P5-T1 (golden document extraction), P5-T2 (field & citation validation), P5-T7 (high-impact review routing).
