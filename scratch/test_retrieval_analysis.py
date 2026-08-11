"""
Diagnostic script to test golden-set retrieval evaluation fixes and breakdown.
"""
import asyncio
import re
from typing import Any

from rekanvault.evaluation.runner import load_golden_questions


def fixed_is_hit(hit: dict[str, Any], target_source: str) -> bool:
    """Corrected _is_hit that handles multi-target sources and metadata matching."""
    if not target_source or target_source == "None":
        return False

    meta = hit.get("metadata") or {}
    # Split multi-target sources (e.g. "path1 & path2", "path1, path2", "path1 ; path2")
    targets = [t.strip().lower() for t in re.split(r"\s+[&;,]\s+|\s+&\s+", target_source) if t.strip()]

    # Collect metadata strings to check against
    meta_strings = []
    for k, v in meta.items():
        if v is None:
            continue
        if isinstance(v, dict):
            for sub_k, sub_v in v.items():
                if sub_v:
                    meta_strings.append(str(sub_v).lower())
        else:
            meta_strings.append(str(v).lower())

    # Check if ANY of the target paths/filenames match any metadata string (or substring)
    for target in targets:
        # Get filename part of target path
        target_filename = target.split("/")[-1]
        for m in meta_strings:
            if target in m or target_filename in m or m in target:
                return True
    return False


def analyze_golden_set():
    questions = load_golden_questions("docs/REKANVAULT_GOLDEN_SET.md")
    print(f"Total golden set questions: {len(questions)}")

    categories = {}
    multi_targets = 0
    none_targets = 0

    for q in questions:
        cat = q["category"]
        categories[cat] = categories.get(cat, 0) + 1
        target = q["target_source"]
        if target == "None":
            none_targets += 1
        elif " & " in target or ", " in target or ";" in target:
            multi_targets += 1

    print("\nCategory Distribution:")
    for cat, count in sorted(categories.items()):
        print(f"  {cat:15s}: {count}")

    print(f"\nTarget Analysis:")
    print(f"  Single target questions : {len(questions) - none_targets - multi_targets}")
    print(f"  Multi-target questions  : {multi_targets}")
    print(f"  'None' (NEGATIVE) q's   : {none_targets}")


if __name__ == "__main__":
    analyze_golden_set()
