"""Unit tests for MemoryExtractor type normalization (_coerce_memory_type)."""

from __future__ import annotations

from rekanvault.memory.extraction import _coerce_memory_type
from rekanvault.memory.models import MemoryType


def test_exact_match() -> None:
    assert _coerce_memory_type("Fact") == MemoryType.FACT


def test_case_insensitive_match() -> None:
    assert _coerce_memory_type("fact") == MemoryType.FACT
    assert _coerce_memory_type("PERSON") == MemoryType.PERSON
    assert _coerce_memory_type("Decision") == MemoryType.DECISION


def test_whitespace_trimmed() -> None:
    assert _coerce_memory_type("  event ") == MemoryType.EVENT


def test_unknown_type_returns_none() -> None:
    assert _coerce_memory_type("Workflow") is None
    assert _coerce_memory_type("") is None
