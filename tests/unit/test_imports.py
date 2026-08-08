"""Import-isolation coverage for the lightweight package root."""

from __future__ import annotations

import subprocess  # ruff: ignore[suspicious-subprocess-import]
import sys

import pytest


@pytest.mark.parametrize("lazy_export", ["BinData", "BinDataStore"])
def test_root_import_defers_database_stack_until_lazy_export_is_requested(lazy_export: str) -> None:
    """Importing metadata and result types must not initialize the ORM stack."""
    check = f"""
import sys
import card_bin_data

heavy_modules = ("advanced_alchemy", "aiosqlite", "asyncpg", "sqlalchemy")
assert all(module not in sys.modules for module in heavy_modules)
assert card_bin_data.LookupResult is not None
assert getattr(card_bin_data, {lazy_export!r}) is not None
assert "sqlalchemy" in sys.modules
try:
    card_bin_data.missing_export
except AttributeError:
    pass
else:
    raise AssertionError("unknown root exports must raise AttributeError")
"""

    subprocess.run([sys.executable, "-I", "-c", check], check=True)  # ruff: ignore[subprocess-without-shell-equals-true]
