### RV-DEC-P4-0003 — Reranker selection: BAAI/bge-reranker-v2-m3 for top candidate rescoring

- Phase: P4
- Status: Approved
- Owner: Sigit
- Date: 2026-08-06
- Decision required by: Phase P4 hybrid search and reciprocal-rank fusion pipeline
- Context: Dense and lexical candidate retrieval (top 20) requires cross-encoder reranking to maximize precision and ranking quality before building evidence packets.
- Options:
  1. Use `BAAI/bge-reranker-v2-m3` cross-encoder on top 20 candidate items with worker concurrency 1.
  2. Use pure Reciprocal Rank Fusion (RRF) without a cross-encoder reranker stage.
- Chosen option: Option 1 — `BAAI/bge-reranker-v2-m3` on top 20 candidates.
- Why: Significantly improves precision (Recall@10, MRR, nDCG@10) on complex multilingual queries while constraining CPU load by limiting cross-encoding to the top 20 candidates with worker concurrency 1.
- Impact: Search API pipeline executes dense + lexical candidate retrieval, applies RRF fusion, and passes top 20 candidates through `bge-reranker-v2-m3`.
- Reversal trigger: If query latency exceeds 1.5s under concurrent search traffic.
- Related ADR/tests: P4-T5, P4-T8 (resource profiling).
