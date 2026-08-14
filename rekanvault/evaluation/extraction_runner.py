"""Golden-set extraction evaluation runner for Phase 5 Typed Memory Formation (P5-T1 / P5-T2).

Parses `docs/REKANVAULT_EXTRACTION_GOLDEN_SET.md` and evaluates extraction test
cases against Pydantic V2 schemas (`extra="forbid"`) and review queue routing.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from rekanvault.memory.models import (
    TYPED_MEMORY_MODELS,
    MemoryType,
    determine_review_status,
)

DEFAULT_EXTRACTION_GOLDEN_PATH = "docs/REKANVAULT_EXTRACTION_GOLDEN_SET.md"

_EXT_HEADER_RE = re.compile(r"^###\s+(EXT-\d+)\s+—\s+(.+)$")
_LOCATOR_RE = re.compile(r"^\-\s+\*\*Target Locator\*\*:\s+`?([^`\n]+)`?$")
_MEMORY_TYPE_RE = re.compile(r"^\-\s+\*\*Memory Type\*\*:\s+`?([^`\n]+)`?$")


def load_extraction_golden_set(
    path: str = DEFAULT_EXTRACTION_GOLDEN_PATH,
) -> list[dict[str, Any]]:
    """Parse labeled extraction golden set markdown file into structured test cases."""
    p = Path(path)
    if not p.exists():
        return []

    content = p.read_text(encoding="utf-8")
    sections = content.split("### EXT-")
    test_cases: list[dict[str, Any]] = []

    for section in sections[1:]:
        full_section = "### EXT-" + section
        lines = full_section.splitlines()
        header_match = _EXT_HEADER_RE.match(lines[0])
        if not header_match:
            continue

        ext_id = header_match.group(1)
        mem_type_str = header_match.group(2).strip()

        locator = ""
        for line in lines:
            loc_match = _LOCATOR_RE.match(line)
            if loc_match:
                locator = loc_match.group(1).strip()
                break

        # Parse Input Text code block
        input_text = ""
        in_input_block = False
        input_lines: list[str] = []
        for line in lines:
            if "**Input Text**:" in line:
                in_input_block = True
                continue
            if in_input_block:
                if line.strip().startswith("```"):
                    if input_lines:  # Closing tag
                        in_input_block = False
                        break
                    continue
                input_lines.append(line)

        input_text = "\n".join(input_lines).strip()

        # Parse Expected Memory JSON block
        expected_json: dict[str, Any] = {}
        in_json_block = False
        json_lines: list[str] = []
        for line in lines:
            if "**Expected Memory**:" in line:
                in_json_block = True
                continue
            if in_json_block:
                if line.strip().startswith("```"):
                    if json_lines:  # Closing tag
                        in_json_block = False
                        break
                    continue
                json_lines.append(line)

        raw_json = "\n".join(json_lines).strip()
        if raw_json:
            try:
                expected_json = json.loads(raw_json)
            except json.JSONDecodeError:
                expected_json = {}

        test_cases.append(
            {
                "id": ext_id,
                "memory_type": mem_type_str,
                "locator": locator,
                "input_text": input_text,
                "expected_memory": expected_json,
            }
        )

    return test_cases


class ExtractionEvaluationRunner:
    """Evaluates extraction test cases against Pydantic V2 schemas and review rules."""

    def evaluate_test_case(self, case: dict[str, Any]) -> dict[str, Any]:
        ext_id = case["id"]
        mem_type_name = case["memory_type"]
        expected = case["expected_memory"]
        locator = case["locator"]

        try:
            mem_type = MemoryType(mem_type_name)
        except ValueError:
            return {
                "id": ext_id,
                "memory_type": mem_type_name,
                "valid": False,
                "error": f"Unknown memory type: {mem_type_name}",
            }

        model_cls = TYPED_MEMORY_MODELS.get(mem_type)
        if not model_cls:
            return {
                "id": ext_id,
                "memory_type": mem_type_name,
                "valid": False,
                "error": f"No model class registered for {mem_type_name}",
            }

        # Step 1: Validate payload against Pydantic schema (extra="forbid")
        try:
            test_payload = dict(expected)
            test_payload["workspace_id"] = "00000000-0000-0000-0000-000000000001"
            if locator:
                test_payload["evidence_chunk_ids"] = [locator]

            instance = model_cls.model_validate(test_payload)
            valid = True
            schema_error = None
        except Exception as e:
            valid = False
            schema_error = str(e)
            instance = None

        # Step 2: Validate review queue routing policy
        expected_status = None
        if instance:
            expected_status = determine_review_status(
                instance.memory_type,
                instance.impact,
                instance.confidence,
            )

        return {
            "id": ext_id,
            "memory_type": mem_type_name,
            "valid": valid,
            "schema_error": schema_error,
            "review_status": expected_status.value if expected_status else None,
            "title": instance.title if instance else expected.get("title", ""),
            "has_evidence": bool(locator),
        }

    def evaluate_set(self, cases: list[dict[str, Any]]) -> dict[str, Any]:
        details: list[dict[str, Any]] = []
        valid_count = 0

        for case in cases:
            res = self.evaluate_test_case(case)
            details.append(res)
            if res["valid"]:
                valid_count += 1

        total = len(cases)
        schema_validation_rate = valid_count / total if total > 0 else 0.0

        return {
            "total_cases": total,
            "valid_cases": valid_count,
            "schema_validation_rate": schema_validation_rate,
            "details": details,
        }


__all__ = [
    "DEFAULT_EXTRACTION_GOLDEN_PATH",
    "ExtractionEvaluationRunner",
    "load_extraction_golden_set",
]


def _run_cli() -> None:
    parser = argparse.ArgumentParser(description="RekanVault extraction golden set runner")
    parser.add_argument(
        "--golden-path",
        default=DEFAULT_EXTRACTION_GOLDEN_PATH,
        help=f"Path to extraction golden set (default: {DEFAULT_EXTRACTION_GOLDEN_PATH})",
    )
    args = parser.parse_args()

    cases = load_extraction_golden_set(args.golden_path)
    if not cases:
        print(f"No test cases found in {args.golden_path}")
        return

    print(f"Loaded {len(cases)} extraction test cases from {args.golden_path}")
    runner = ExtractionEvaluationRunner()
    results = runner.evaluate_set(cases)

    print(f"\n{'='*60}")
    print(f"Extraction Benchmark Results — {results['total_cases']} cases")
    print(f"{'='*60}")
    print(f"Schema Validation Rate (extra='forbid'): {results['schema_validation_rate']*100:.1f}%")
    print(f"Valid Cases:                            {results['valid_cases']} / {results['total_cases']}")
    print("\nCase Breakdown:")
    for d in results["details"]:
        status_symbol = "✅" if d["valid"] else "❌"
        print(f"  {status_symbol} {d['id']:7s} | {d['memory_type']:15s} | Review: {d.get('review_status', 'N/A'):15s} | {d['title']}")


if __name__ == "__main__":
    _run_cli()
