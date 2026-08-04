"""P2-T1: Alembic migration upgrade/downgrade idempotency.

Verifies the migration structure without a live database.
If a database URL is available, runs the full upgrade→downgrade→upgrade cycle.
"""

from __future__ import annotations

import importlib
import os
import subprocess
import sys
import types
from pathlib import Path

import pytest

from apps.api.config import settings

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MIGRATION_PATH = Path("alembic/versions/20260802_0001_p2_initial_schema.py")
REVISION_ID = "20260802_0001"
_db_url = settings.RV_DATABASE_URL
DATABASE_URL = "" if "localhost" in _db_url else _db_url

# ---------------------------------------------------------------------------
# Structural tests (no DB required)
# ---------------------------------------------------------------------------


def test_migration_file_exists() -> None:
    """P2-T1: The initial migration file must exist at the expected path."""
    assert MIGRATION_PATH.exists(), f"Migration file not found: {MIGRATION_PATH}"


def test_migration_module_importable() -> None:
    """P2-T1: The migration module must import cleanly with callable upgrade/downgrade."""
    mod = _import_migration_module()
    assert callable(getattr(mod, "upgrade", None)), "upgrade() is not callable"
    assert callable(getattr(mod, "downgrade", None)), "downgrade() is not callable"


def test_migration_is_root_revision() -> None:
    """P2-T1: The initial migration must have down_revision = None (root of chain)."""
    mod = _import_migration_module()
    assert getattr(mod, "down_revision", "__MISSING__") is None, (
        f"Expected down_revision=None for the initial migration, got {mod.down_revision!r}"
    )


def test_migration_revision_id() -> None:
    """P2-T1: The migration revision ID must match the expected value."""
    mod = _import_migration_module()
    assert getattr(mod, "revision", None) == REVISION_ID, f"Expected revision={REVISION_ID!r}, got {mod.revision!r}"


# ---------------------------------------------------------------------------
# Live DB tests (skipped when no database is available)
# ---------------------------------------------------------------------------

requires_db = pytest.mark.skipif(
    not DATABASE_URL,
    reason="Set RV_DATABASE_URL or DATABASE_URL to run live migration tests",
)


@requires_db
def test_alembic_upgrade_downgrade_idempotency() -> None:
    """P2-T1: upgrade head → downgrade -1 → upgrade head must be idempotent.

    Requires a reachable PostgreSQL database (empty or disposable).
    """

    def run_alembic(*args: str) -> subprocess.CompletedProcess[str]:
        result = subprocess.run(
            [sys.executable, "-m", "alembic", *args],
            capture_output=True,
            text=True,
            timeout=30,
            env={**os.environ, "DATABASE_URL": DATABASE_URL},
        )
        assert result.returncode == 0, (
            f"alembic {' '.join(args)} failed (rc={result.returncode}):\n"
            f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )
        return result

    run_alembic("upgrade", "head")
    run_alembic("downgrade", "-1")
    run_alembic("upgrade", "head")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _import_migration_module() -> types.ModuleType:
    """Dynamically import the migration file as a Python module."""
    mod_name = MIGRATION_PATH.stem
    spec = importlib.util.spec_from_file_location(mod_name, str(MIGRATION_PATH))
    assert spec is not None and spec.loader is not None, f"Could not load spec for {MIGRATION_PATH}"
    mod = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)
    return mod
