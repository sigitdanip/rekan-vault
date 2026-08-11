import re

file_path = "docs/REKANVAULT_GOLDEN_SET.md"

with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# Extract change discipline log
discipline_start = content.find("## Change Review Discipline (`RV-DEC-0015`)")
benchmark_cat_start = content.find("## Benchmark Question Categories")
findings_start = content.find("## Findings on Baseline Q-001–Q-100")

# Extract all question rows across the entire file
row_pattern = re.compile(r"^\|\s*`?(Q-\d+)`?\s*\|.*$", re.MULTILINE)
question_rows = []
seen_ids = set()

for line in content.splitlines():
    line_str = line.strip()
    if line_str.startswith("| `Q-") or line_str.startswith("| Q-"):
        # Match ID
        m = re.match(r"^\|\s*`?(Q-\d+)`?\s*\|", line_str)
        if m:
            q_id = m.group(1)
            if q_id not in seen_ids:
                seen_ids.add(q_id)
                question_rows.append((int(q_id.replace("Q-", "")), line_str))

# Sort by numeric ID
question_rows.sort(key=lambda x: x[0])
print(f"Extracted {len(question_rows)} unique question rows from Q-{question_rows[0][0]:03d} to Q-{question_rows[-1][0]:03d}.")

# Construct unified file content
header_text = """# RekanVault — Golden Question Set (`RV-DEC-0015`)

- **Owner**: Sigit (`RV-DEC-0015`)
- **Status**: Active / Benchmark Ready
- **Last Updated**: 2026-08-06
- **Corpus Source**: Pilot Google Drive (`1-K3v6TUw4qiKZoSXp9TbzSCC7wMcskRN`) — `gerakan-pembaru`, `mujaddid`, `rekanmu`

---

## Change Review Discipline (`RV-DEC-0015`)

Per `RV-DEC-0015`, any modification to an existing question's expected answer or evidence target MUST record a stated reason in the log below.

| Date | Q-ID | Action | Reason | Stated By |
|---|---|---|---|---|
| 2026-08-05 | Q-001–Q-100 | Initial Batch Creation | Grounded on pilot Google Drive 60-file corpus inventory scan | Sigit / Antigravity |
| 2026-08-06 | Q-101–Q-164 | Batch 2 Creation | Grounded on raw corpus scan (TEMPORAL, SYNTHESIS, MULTIHOP, CONFLICT, INSUFFICIENT categories) per RV-DEC-0015 | Sigit / Antigravity |
| 2026-08-06 | Q-165–Q-180 | Realignment Batch 3 | Realigned golden set for 2 new DOCX SOP documents in `rekanmu/original-files/` (`SOP_Presales_RekanDigital.docx` & `SOP_Eksekusi_Proyek_Development.docx`) per RV-DEC-0015 | Sigit / Antigravity |

---

## Benchmark Question Categories

1. **EXACT**: Exact phrase / title / keyword matches.
2. **ID_SEMANTIC**: Indonesian language semantic retrieval queries.
3. **EN_SEMANTIC**: English language semantic retrieval queries.
4. **NEGATIVE**: Unanswerable / out-of-corpus queries (must return `INSUFFICIENT_EVIDENCE`).
5. **FILTER**: Scope, path, or provider metadata filtering queries.
6. **TEMPORAL**: Current vs historical state queries using dated content.
7. **SYNTHESIS**: Multi-document synthesis queries requiring 2+ source citations.
8. **MULTIHOP**: Relationship and entity-traversal queries across documents.
9. **CONFLICT**: Spelling/structural conflict queries where both variants are valid.
10. **INSUFFICIENT**: Partially covered in-corpus topics identifying known facts and gaps.

---

## Golden Question Triple Set (Q-001 to Q-180)

| ID | Category | Question | Target Source / Path | Expected Answer / Evidence Key |
|---|---|---|---|---|
"""

table_body = "\n".join([row[1] for row in question_rows])

findings_text = """

---

## Findings on Baseline Q-001–Q-100

1. **Path Scheme Discrepancy**:
   - `Q-001`–`Q-020` cite raw filenames/relative paths under `gerakan-pembaru/original-files/`, `rekanmu/original-files/`, `gerakan-pembaru/member_raw_archive/`, etc.
   - `Q-021`–`Q-100` cite normalized document filenames (`0001-*.md`, `0002-*.md`) under `documents/`.
   - *Resolution*: This is recorded as an audit finding. Per `RV-DEC-0015` change review discipline, baseline `Q-001`–`Q-100` are retained without alteration to maintain baseline benchmark continuity.

2. **Wildcard & Multi-target Citations**:
   - Filter questions (`Q-091`–`Q-100`) use glob wildcards (`rekanmu/documents/*.md`, `gerakan-pembaru/documents/0007-*.md`) or comma-separated lists as target paths.
   - Evaluation harness handles wildcard expansion when scoring recall.
"""

new_full_content = header_text + table_body + findings_text

with open(file_path, "w", encoding="utf-8") as f:
    f.write(new_full_content)

print(f"Successfully rewritten {file_path} with 1 single big table containing {len(question_rows)} questions.")
