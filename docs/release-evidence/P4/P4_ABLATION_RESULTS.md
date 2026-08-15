# P4 Title-Hack Ablation — Raw Results

**Date**: 2026-08-15
**Purpose**: Diagnostic ablation — measure how much of Recall@10 comes from corpus-specific title-boost/fragment hacks vs. the core hybrid pipeline. This file records raw results only; interpretation happens separately.
**Scope**: Retrieval-time config only. No changes to chunking, embedding model, or reranker model. Default path (`ablate_title_hacks=False`) is byte-identical to prior behavior.

## Configs

| Config | Flag | Title boost (`_apply_title_boost`) | Inferred title filters (`_infer_title_filter`) |
|---|---|---|---|
| Baseline (hacks ON) | `ablate_title_hacks=False` | active | active |
| Ablated (hacks OFF) | `ablate_title_hacks=True` + `RV_ABLATE_TITLE_HACKS=1`, `RV_TITLE_FILTER_FRAGMENTS=""` | skipped | skipped |

## Overall metrics

| Golden set | Config | Recall@10 | MRR | nDCG@10 |
|---|---|---|---|---|
| GDrive (166 questions) | baseline | 0.8889 | 0.6544 | 0.7583 |
| GDrive (166 questions) | ablated | 0.8333 | 0.5418 | 0.6671 |
| Notion (42 questions) | baseline | 0.8947 | 0.7230 | 0.7213 |
| Notion (42 questions) | ablated | 0.7632 | 0.5067 | 0.5241 |

## Per-category breakdown

### GDrive golden set (166 questions)

| Category | Baseline (hits/total) | Ablated (hits/total) |
|---|---|---|
| CONFLICT | 8/12 (67%) | 9/12 (75%) |
| EN_SEMANTIC | 22/24 (92%) | 19/24 (79%) |
| EXACT | 22/22 (100%) | 20/22 (91%) |
| FILTER | 19/19 (100%) | 12/19 (63%) |
| ID_SEMANTIC | 23/24 (96%) | 20/24 (83%) |
| MULTIHOP | 10/13 (77%) | 12/13 (92%) |
| SYNTHESIS | 19/23 (83%) | 22/23 (96%) |
| TEMPORAL | 5/7 (71%) | 6/7 (86%) |

### Notion golden set (42 questions)

| Category | Baseline (hits/total) | Ablated (hits/total) |
|---|---|---|
| CONFLICT | 2/4 (50%) | 2/4 (50%) |
| EN_SEMANTIC | 5/5 (100%) | 5/5 (100%) |
| EXACT | 5/6 (83%) | 6/6 (100%) |
| FILTER | 4/4 (100%) | 3/4 (75%) |
| ID_SEMANTIC | 8/8 (100%) | 8/8 (100%) |
| MULTIHOP | 3/4 (75%) | 0/4 (0%) |
| SYNTHESIS | 4/4 (100%) | 2/4 (50%) |
| TEMPORAL | 3/3 (100%) | 3/3 (100%) |

## Full output

```
=== BASELINE (hacks ON) ===
Loaded 166 questions from docs/REKANVAULT_GOLDEN_SET.md
============================================================
Results — 166 questions
============================================================
Recall@10:  0.8889
MRR:        0.6544
nDCG@10:    0.7583
Per-category Recall@10:
  CONFLICT: 8/12 (67%)
  EN_SEMANTIC: 22/24 (92%)
  EXACT: 22/22 (100%)
  FILTER: 19/19 (100%)
  ID_SEMANTIC: 23/24 (96%)
  MULTIHOP: 10/13 (77%)
  SYNTHESIS: 19/23 (83%)
  TEMPORAL: 5/7 (71%)
Source type breakdown:
  google_drive        : 1025
  notion              : 339
  unknown             : 18

Loaded 42 questions from docs/REKANVAULT_GOLDEN_SET_NOTION.md
============================================================
Results — 42 questions
============================================================
Recall@10:  0.8947
MRR:        0.7230
nDCG@10:    0.7213
Per-category Recall@10:
  CONFLICT: 2/4 (50%)
  EN_SEMANTIC: 5/5 (100%)
  EXACT: 5/6 (83%)
  FILTER: 4/4 (100%)
  ID_SEMANTIC: 8/8 (100%)
  MULTIHOP: 3/4 (75%)
  SYNTHESIS: 4/4 (100%)
  TEMPORAL: 3/3 (100%)
Source type breakdown:
  notion              : 301
  google_drive        : 58
  unknown             : 3

=== ABLATED (hacks OFF) ===
Loaded 166 questions from docs/REKANVAULT_GOLDEN_SET.md
============================================================
Results — 166 questions
============================================================
Recall@10:  0.8333
MRR:        0.5418
nDCG@10:    0.6671
Per-category Recall@10:
  CONFLICT: 9/12 (75%)
  EN_SEMANTIC: 19/24 (79%)
  EXACT: 20/22 (91%)
  FILTER: 12/19 (63%)
  ID_SEMANTIC: 20/24 (83%)
  MULTIHOP: 12/13 (92%)
  SYNTHESIS: 22/23 (96%)
  TEMPORAL: 6/7 (86%)
Source type breakdown:
  google_drive        : 1480
  notion              : 157
  unknown             : 23

Loaded 42 questions from docs/REKANVAULT_GOLDEN_SET_NOTION.md
============================================================
Results — 42 questions
============================================================
Recall@10:  0.7632
MRR:        0.5067
nDCG@10:    0.5241
Per-category Recall@10:
  CONFLICT: 2/4 (50%)
  EN_SEMANTIC: 5/5 (100%)
  EXACT: 6/6 (100%)
  FILTER: 3/4 (75%)
  ID_SEMANTIC: 8/8 (100%)
  MULTIHOP: 0/4 (0%)
  SYNTHESIS: 2/4 (50%)
  TEMPORAL: 3/3 (100%)
Source type breakdown:
  notion              : 235
  google_drive        : 179
  unknown             : 4
```
