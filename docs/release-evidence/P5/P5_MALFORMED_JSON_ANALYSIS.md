# P5 Full-Corpus Extraction — Malformed JSON Analysis

- **Run date**: 2026-08-13
- **Model**: `ocg/deepseek-v4-flash` (9router)
- **Corpus**: 186 active docs, 811 chunks processed
- **Result**: 1420 memories, 18/18 types

## Summary

| Metric | Value |
|---|---|
| Chunks processed | 811 |
| Chunks yielding malformed LLM JSON | 281 (34.6%) |
| Chunks yielding valid memories | 530 |
| Valid memories extracted | 1339 (~2.5/chunk) |

## Failure categories

The 281 "malformed JSON" chunks break down into **two distinct failure modes**:

### 1. Envelope parse failures (`llm_json_validation_failed`) — 281 events

The LLM returned text that does not parse into the `_ExtractionEnvelope`
schema (`{"memories": [...]}`). These are logged at the `LLMProvider`
layer (`llm.py`), which does **not** have the `chunk_id` in scope.

- **error_count distribution**: 280 × `error_count=1`, 1 × `error_count=2`
  (error_count = number of pydantic validation errors in the failed parse).
- **Root cause**: deepseek-v4-flash sometimes wraps the JSON in prose,
  markdown fences, or emits an array instead of an object, despite
  `response_format={"type": "json_object"}`.

### 2. Type-level validation failures (`memory_extraction_validation_failed`) — 7 events

The envelope parsed, but an individual memory item failed strict per-type
validation even after field sanitization. These ARE attributed to chunk_id.

| chunk_id | memory_type | error |
|---|---|---|
| `1mVSmQ-rd1RL_WAETeQBPPiLDbOxlWCti#v1#chunk_002` | Decision | ValidationError |
| `1TX_ZBjOCZfeXKbsilbnurc3llb8EyUm4#v1#chunk_189` | Topic | ValidationError |
| `7c0aeb252cf183dd942f81f036761c3b#v1#chunk_004` | Decision | ValidationError |
| `13faeb252cf182a4822c81a593ecea83#v1#chunk_002` | Decision | ValidationError |
| `e40aeb252cf1833b92c3013918417ca9#v1#chunk_001` | Decision | ValidationError |
| `298aeb252cf1839dbc1181b42e97f003#v1#chunk_001` | Event | ValidationError |
| `3b2aeb252cf180babe41d2058ff74d4c#v1#chunk_049` | Decision | ValidationError |

**Pattern**: 5 of 7 are `Decision` — the LLM frequently omits `rationale`
(a required field) when it misclassifies a chunk as a Decision.

### 3. Sanitization drops (`memory_extraction_dropped_unknown_fields`) — 2 events

Fields the LLM invented that don't exist in the schema, dropped before
validation:

| chunk_id | memory_type | dropped keys |
|---|---|---|
| `1TX_ZBjOCZfeXKbsilbnurc3llb8EyUm4#v1#chunk_112` | Asset | `url` |
| `1TX_ZBjOCZfeXKbsilbnurc3llb8EyUm4#v1#chunk_189` | Topic | `statement`, `verification_method` |

## Observability gap (to fix before P6)

The 281 envelope-parse failures (category 1) are logged at the `LLMProvider`
layer **without `chunk_id`**. The extractor knows the chunk_id but swallows
the exception without re-logging it. Fix: in `MemoryExtractor.extract()`,
catch the `RekanVaultError` from `extract_structured` and re-log with
`chunk_id` before re-raising. This makes the 34.6% failure rate attributable
per-chunk instead of a raw counter.

## Recommendations

1. **Retry once** on envelope-parse failure with a tightened system prompt
   ("output ONLY the JSON object, no prose, no markdown fences").
2. **Loosen `Decision.rationale`** or add a default — 5/7 type-level
   failures are missing `rationale`.
3. **Fix the observability gap** so future runs attribute failures per chunk.
