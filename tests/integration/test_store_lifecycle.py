"""Integration coverage for BinDataStore lifecycle on every supported backend."""
# ruff: noqa: S101

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from sqlalchemy import inspect, text

from card_bin_data.db.session import SQLITE_BUSY_TIMEOUT_SECONDS

if TYPE_CHECKING:
    from card_bin_data import BinDataStore


@pytest.mark.asyncio(loop_scope="session")
async def test_store_init_creates_required_schema(store: BinDataStore) -> None:
    """Store initialization creates the required card_bin_data schema on each backend."""
    await store.init()

    async with store.engine.connect() as connection:
        table_names = await connection.run_sync(
            lambda sync_connection: set(inspect(sync_connection).get_table_names()),
        )

    assert table_names >= {"data_sources", "bin_records", "bin_record_sources"}


@pytest.mark.asyncio(loop_scope="session")
async def test_store_close_is_idempotent(store: BinDataStore) -> None:
    """Store lifecycle can be closed repeatedly without leaking state."""
    await store.init()
    await store.close()
    await store.close()
    await store.close()

    assert store.drivername in {"sqlite+aiosqlite", "postgresql+asyncpg"}


@pytest.mark.asyncio(loop_scope="session")
async def test_sqlite_connections_use_configured_busy_timeout(store: BinDataStore) -> None:
    """SQLite connections wait for short-lived concurrent writers (SQLite-only)."""
    if store.drivername != "sqlite+aiosqlite":
        pytest.skip("busy_timeout pragma is SQLite-specific")

    async with store.engine.connect() as connection:
        busy_timeout = await connection.scalar(text("PRAGMA busy_timeout"))

    assert busy_timeout == int(SQLITE_BUSY_TIMEOUT_SECONDS * 1000)
