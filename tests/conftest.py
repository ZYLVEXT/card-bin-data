"""Shared test fixtures, including the disposable PostgreSQL backend."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import pytest
from pytest_deadfixtures import deadfixtures_ignore

from card_bin_data import BinDataStore
from tests.support.schema import drop_schema

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from pathlib import Path

    from pytest_databases.docker.postgres import PostgresService

pytest_plugins = ["pytest_databases.docker.postgres"]

POSTGRESQL_TEST_DATABASE_URL_ENV = "CARD_BIN_DATA_POSTGRESQL_TEST_DATABASE_URL"
POSTGRESQL_DRIVER = "postgresql+asyncpg"


@pytest.fixture
@deadfixtures_ignore
def postgresql_database_url(request: pytest.FixtureRequest) -> str:
    """Return a postgresql+asyncpg URL for tests.

    Prefers an explicit external database via ``CARD_BIN_DATA_POSTGRESQL_TEST_DATABASE_URL``;
    otherwise provisions a disposable Dockerized PostgreSQL through pytest-databases.

    Returns:
        A ``postgresql+asyncpg://`` URL pointing at a usable test database.
    """
    override = os.environ.get(POSTGRESQL_TEST_DATABASE_URL_ENV)
    if override and override.strip():
        url = override.strip()
        if not url.startswith(f"{POSTGRESQL_DRIVER}://"):
            pytest.fail(f"{POSTGRESQL_TEST_DATABASE_URL_ENV} must use a {POSTGRESQL_DRIVER}:// URL.")
        return url

    service: PostgresService = request.getfixturevalue("postgres_service")
    return f"{POSTGRESQL_DRIVER}://{service.user}:{service.password}@{service.host}:{service.port}/{service.database}"


@pytest.fixture(params=["sqlite", "postgresql"])
async def store(request: pytest.FixtureRequest, tmp_path: Path) -> AsyncIterator[BinDataStore]:
    """Provide a clean, uninitialized store for every supported backend.

    Tests that accept ``store`` run once per backend (``[sqlite]`` and
    ``[postgresql]``). The SQLite branch uses a disposable temp-file database and
    never requires Docker; the PostgreSQL branch uses the shared disposable
    service and starts from a dropped schema.

    Yields:
        Store for the parametrized backend, with no schema created yet.
    """
    if request.param == "sqlite":
        store = BinDataStore.from_url(f"sqlite+aiosqlite:///{tmp_path / 'card_bin_data.db'}")
        try:
            yield store
        finally:
            await store.close()
        return

    store = BinDataStore.from_url(request.getfixturevalue("postgresql_database_url"))
    await drop_schema(store.engine)
    try:
        yield store
    finally:
        await drop_schema(store.engine)
        await store.close()
