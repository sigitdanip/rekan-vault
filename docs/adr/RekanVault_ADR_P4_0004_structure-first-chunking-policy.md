### RV-DEC-P4-0004 — Structure-first chunking policy and block locators

- Phase: P4
- Status: Approved
- Owner: Sigit
- Date: 2026-08-06
- Decision required by: Phase P4 document chunking and evidence citation engine
- Context: Evidence packets must provide exact source, version, and block locators. Fixed character chunking breaks logical document structures (headings, paragraphs, database rows).
- Options:
  1. Structure-first chunking targeting ~450 tokens, respecting block boundaries and preserving block locators (`doc_id#v<n>#chunk_<seq>`), with 80-token overlap only across continuous prose.
  2. Fixed 512-token character chunking with arbitrary 64-token overlap across block boundaries.
- Chosen option: Option 1 — Structure-first chunking.
- Why: Preserves document semantical structure, guarantees deterministic chunk IDs across reprocessing (`P4-T1`), and enables exact citation resolution back to source blocks.
- Impact: Document processor converts `NormalizedDocument` versions into structure-aware evidence chunks stored in PostgreSQL `chunks` table and indexed in Qdrant.
- Reversal trigger: If structural blocks exceed target chunk token budget or fragmentation degrades recall.
- Related ADR/tests: P4-T1 (stable chunk IDs), P4-T5 (citation resolution).
