"""Async SQLAlchemy session configuration for card_bin_data stores."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.engine import URL, make_url
from sqlalchemy.exc import ArgumentError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from ..exceptions import CardBinDataStoreConfigurationError  # noqa: TID252

SUPPORTED_DRIVER_NAMES = frozenset({"sqlite+aiosqlite", "postgresql+asyncpg"})
SQLITE_BUSY_TIMEOUT_SECONDS = 30.0


@dataclass(frozen=True, slots=True)
class StoreDatabaseConfig:
    """Validated database configuration for a card_bin_data store."""

    url: URL

    def __repr__(self) -> str:
        """Render the config with the database password masked.

        The default dataclass repr would surface ``url`` verbatim, including the
        password, into logs and tracebacks. Mask it so credentials never leak
        through incidental string conversion.

        Returns:
            Debug representation with the URL password redacted.
        """
        return f"StoreDatabaseConfig(url={self.url.render_as_string(hide_password=True)!r})"

    @property
    def drivername(self) -> str:
        """SQLAlchemy driver name for the configured backend."""
        return self.url.drivername

    @property
    def _connection_string(self) -> str:
        """String form accepted by SQLAlchemy engine creation."""
        return self.url.render_as_string(hide_password=False)


def parse_database_url(database_url: str) -> StoreDatabaseConfig:
    """Parse and validate an explicit card_bin_data database URL.

    Returns:
        Validated store database configuration.

    Raises:
        CardBinDataStoreConfigurationError: If the URL is missing, malformed, or unsupported.
    """
    if not database_url.strip():
        msg = "Database URL is required."
        raise CardBinDataStoreConfigurationError(msg)

    try:
        url = make_url(database_url)
    except ArgumentError as exc:
        msg = "Database URL is invalid."
        raise CardBinDataStoreConfigurationError(msg) from exc

    if url.drivername not in SUPPORTED_DRIVER_NAMES:
        supported = ", ".join(sorted(SUPPORTED_DRIVER_NAMES))
        msg = f"Unsupported database URL driver. Supported drivers: {supported}."
        raise CardBinDataStoreConfigurationError(msg)

    return StoreDatabaseConfig(url=url)


def make_async_engine(config: StoreDatabaseConfig) -> AsyncEngine:
    """Create an async SQLAlchemy engine for a validated store config.

    Returns:
        Async SQLAlchemy engine bound to the configured URL.
    """
    if config.drivername == "sqlite+aiosqlite":
        return create_async_engine(
            config._connection_string,  # noqa: SLF001
            connect_args={"timeout": SQLITE_BUSY_TIMEOUT_SECONDS},
        )

    return create_async_engine(config._connection_string)  # noqa: SLF001


def make_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Create the async session factory used by store-managed units of work.

    Returns:
        Async session factory with non-expiring commits.
    """
    return async_sessionmaker(engine, expire_on_commit=False)
