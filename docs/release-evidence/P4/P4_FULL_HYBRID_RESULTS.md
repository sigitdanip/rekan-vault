# P4 Combined Eval - Final Results

**Date**: 2026-08-12
**Pipeline**: Lexical (tsvector) + Dense (Qdrant) + RRF (k=60, window-keyed) + Cross-Encoder + Diversity Floor
**Corpus**: 137 docs (64 GDrive + 73 Notion), 905 vectors

## Metrics

| Metric | Result | Target |
|---|---|---|
| Recall@10 | 0.8938 | >= 0.85 (PASS) |
| MRR | 0.7695 | - |
| nDCG@10 | 0.7665 | - |
| Hits | 143/160 (89.4%) | - |

## By Category

| Category | Hits | Rate |
|---|---|---|
| CONFLICT | 8/12 | 67% |
| EN_SEMANTIC | 24/26 | 92% |
| EXACT | 27/28 | 96% |
| FILTER | 19/19 | 100% |
| ID_SEMANTIC | 31/32 | 97% |
| MULTIHOP | 10/13 | 77% |
| SYNTHESIS | 19/23 | 83% |
| TEMPORAL | 5/7 | 71% |

## Journey

| Milestone | Recall@10 |
|---|---|
| Original dense-only | 0.428 |
| Original full hybrid | 0.485 |
| All pipeline fixes | 0.859 |
| RRF fusion + diversity rescue | 0.8938 |