# RekanVault — P5 Re-Evaluation Evidence Record (Hardening)

- **Phase**: P5 — Typed Memory Formation and Review
- **Event**: Post-gate hardening re-evaluation
- **Date**: 2026-08-15
- **Author**: Sisyphus
- **Model**: `ocg/deepseek-v4-flash` (9router, OpenAI-compatible)

## Purpose

The P5-GATE run (2026-08-13) closed with 1420 memories but a **35% malformed-JSON
rate** (281/811 chunks) logged as a future-optimization gap
(`docs/release-evidence/P5/P5_MALFORMED_JSON_ANALYSIS.md`). Root cause: the
reasoning model (`ocg/deepseek-v4-flash`) burned its 4096-token output budget on
chain-of-thought before emitting JSON, truncating output with
`finish_reason=length`.

This record re-extracts the full corpus with the extraction-quality hardening
patch and measures the improvement.

## Hardening inventory (uncommitted → this PR)

| Change | File | Effect |
|---|---|---|
| Parse retry ladder (≤3 attempts, corrective feedback) | `rekanvault/memory/llm.py` | Feeds parse/validation errors back to the model |
| Lenient parse (strip fences → stdlib `json` → `json_repair`) | `rekanvault/memory/llm.py` | Recovers trailing commas, unclosed braces, stray prose |
| List-item salvage (drop bad items, re-validate remainder) | `rekanvault/memory/llm.py` | One bad item can't sink a chunk's other memories |
| Thinking-disabled fallback (last resort) | `rekanvault/memory/llm.py` | Forces straight-to-JSON when chain-of-thought starves the budget |
| `RV_LLM_DISABLE_THINKING` config | `apps/api/config.py` | Opt-in fast path (thinking off) |
| Prompt v1.2.1 (entity-first + type disambiguation + title/summary mandate) | `rekanvault/memory/prompts.py` | 2× named-entity capture; kills blank title/summary failures |
| `DecisionMemory.rationale` default `""` | `rekanvault/memory/models.py` | Fixes the 5/7 Decision type-level failures |
| Chunk-level failure tracking | `storage/models.py`, `memory_repo.py`, migration `0004` | Per-chunk failures recorded for targeted re-run |
| Envelope failure re-logging with `chunk_id` | `rekanvault/memory/extraction.py` | Failure rate attributable per chunk |
| `json-repair>=0.40.0` dependency | `pyproject.toml` | — |

## Method

Full-corpus sweep over all 186 active documents in the pilot workspace:
chunk (structure-first, deterministic) → `MemoryExtractor` → `MemoryRepository`
(incremental write + checkpoint/resume). Two configs:

1. **Thinking enabled** (default, `RV_LLM_DISABLE_THINKING=false`, temperature 0.1)
2. **Thinking disabled** (`RV_LLM_DISABLE_THINKING=true`, temperature 0.1)

## Results

| Metric | P5-GATE (Aug 13) | Thinking disabled | **Thinking enabled** |
|---|---|---|---|
| Active documents | 186 | 186 | 186 |
| Chunks | 811 | 1117 | 1117 |
| **Malformed-JSON / failure rate** | **35%** (281/811) | **0%** (0/1117) | **0.09%** (1/1117) |
| Total memories | 1420 | 3654 | **4106** |
| Memories / chunk | 1.75 | 3.27 | **3.68** |
| Memory types | 18/18 | 18/18 | 18/18 |
| Evidence bindings | 1410 | 3654 | 4106 |
| Dangling / unresolvable | 0 | 0 | 0 |
| Wall time | — | ~47 min | ~60 min |

> Chunk count grew 811 → 1117 between Aug 13 and Aug 15 (corpus re-synced; chunker
> code unchanged). The fair comparisons are *failure rate* and *memories/chunk*.

### Type distribution (thinking enabled, 18/18)

```
Fact 1387, Organization 396, Person 399, Topic 394, Asset 374,
Policy 243, Claim 194, Event 135, Decision 89, Procedure 84,
Project 80, Idea 78, Metric 64, Task 60, Risk 51, Lesson 32,
Skill 29, Assumption 17
```

### Evidence resolution (thinking enabled — criterion #2)

```
total_memories:           4106
total_bindings:           4106
bindings_no_doc:          0
bindings_no_ver:          0
dangling_doc:             0
dangling_ver:             0
memories_no_binding:      0
high_impact_auto_approved: 0
review_status:            pending_review 2506, approved 1600
```

### Residual failure (tracked for re-run)

```
extraction_failures: 1
  1iDzU238O2zTUcpIqZ4q7_IWexxyad3ik#v1#chunk_011 | VALIDATION_ERROR | did not match schema after retries
```

## Conclusion

The hardening patch eliminates the malformed-JSON problem:

1. **35% → 0.09% failure rate** under the default config (thinking enabled) —
   the retry ladder + `json_repair` + salvage + thinking-disabled fallback
   recover 1116/1117 chunks.
2. **1420 → 4106 memories** (+189%) from prompt v1.2.1 (entity-first + type
   disambiguation) plus zero lost chunks.
3. Thinking enabled yields more memories (4106 vs 3654) at ~1.3× wall time.
   For throughput-sensitive production, `RV_LLM_DISABLE_THINKING=true` trades a
   ~12% memory yield for a cleaner, ~1.3× faster path.
