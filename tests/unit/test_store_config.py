"""Unit coverage for BinDataStore configuration behavior."""
# ruff: noqa: S101, SLF001

from typing import cast

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from card_bin_data import BinDataStore, CardBinDataStoreConfigurationError
from card_bin_data.db import session as session_module


def test_from_url_requires_explicit_database_url() -> None:
    """Missing database URLs fail with a typed configuration error."""
    with pytest.raises(CardBinDataStoreConfigurationError, match="Database URL is required"):
        BinDataStore.from_url("")

    with pytest.raises(CardBinDataStoreConfigurationError, match="Database URL is required"):
        BinDataStore.from_url("   ")


def test_from_url_rejects_invalid_database_url() -> None:
    """Malformed database URLs fail with a typed configuration error."""
    with pytest.raises(CardBinDataStoreConfigurationError, match="Database URL is invalid"):
        BinDataStore.from_url("not a url")


def test_from_url_rejects_unsupported_driver() -> None:
    """Only MVP async SQLAlchemy backends are accepted."""
    with pytest.raises(CardBinDataStoreConfigurationError, match="Unsupported database URL driver"):
        BinDataStore.from_url("sqlite:///tmp/card_bin_data.db")


def test_from_url_accepts_sqlite_async_url() -> None:
    """SQLite aiosqlite URLs are accepted."""
    store = BinDataStore.from_url("sqlite+aiosqlite:///tmp/card_bin_data.db")

    assert store.config.drivername == "sqlite+aiosqlite"
    assert store.drivername == "sqlite+aiosqlite"
    assert store.database_url == "sqlite+aiosqlite:///tmp/card_bin_data.db"
    assert store._engine is None


def test_from_url_accepts_postgresql_asyncpg_url_without_connecting() -> None:
    """PostgreSQL asyncpg URLs parse at configuration level without requiring a live database."""
    store = BinDataStore.from_url("postgresql+asyncpg://user:secret-pass@localhost/card_bin_data")

    assert store.drivername == "postgresql+asyncpg"
    assert store.database_url == "postgresql+asyncpg://user:***@localhost/card_bin_data"
    assert "secret-pass" not in store.database_url
    assert store.config._connection_string == "postgresql+asyncpg://user:secret-pass@localhost/card_bin_data"
    assert store._engine is None


def test_config_repr_masks_database_password() -> None:
    """The config repr never surfaces the database password into logs or tracebacks."""
    config = BinDataStore.from_url("postgresql+asyncpg://user:secret-pass@localhost/card_bin_data").config

    rendered = repr(config)

    assert "secret-pass" not in rendered
    assert rendered == "StoreDatabaseConfig(url='postgresql+asyncpg://user:***@localhost/card_bin_data')"


def test_make_async_engine_configures_sqlite_busy_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    """SQLite engines wait for a concurrent writer instead of failing immediately."""
    created_engine = cast("AsyncEngine", object())
    captured: dict[str, object] = {}

    def create_engine_spy(database_url: str, **kwargs: object) -> AsyncEngine:
        captured["database_url"] = database_url
        captured["kwargs"] = kwargs
        return created_engine

    monkeypatch.setattr(session_module, "create_async_engine", create_engine_spy)

    engine = session_module.make_async_engine(BinDataStore.from_url("sqlite+aiosqlite:///tmp/card_bin_data.db").config)

    assert engine is created_engine
    assert captured == {
        "database_url": "sqlite+aiosqlite:///tmp/card_bin_data.db",
        "kwargs": {"connect_args": {"timeout": session_module.SQLITE_BUSY_TIMEOUT_SECONDS}},
    }


def test_make_async_engine_leaves_postgresql_configuration_unmodified(monkeypatch: pytest.MonkeyPatch) -> None:
    """SQLite-specific timeout settings are not applied to PostgreSQL engines."""
    created_engine = cast("AsyncEngine", object())
    captured: dict[str, object] = {}

    def create_engine_spy(database_url: str, **kwargs: object) -> AsyncEngine:
        captured["database_url"] = database_url
        captured["kwargs"] = kwargs
        return created_engine

    monkeypatch.setattr(session_module, "create_async_engine", create_engine_spy)

    engine = session_module.make_async_engine(
        BinDataStore.from_url("postgresql+asyncpg://user:secret-pass@localhost/card_bin_data").config,
    )

    assert engine is created_engine
    assert captured == {
        "database_url": "postgresql+asyncpg://user:secret-pass@localhost/card_bin_data",
        "kwargs": {},
    }
