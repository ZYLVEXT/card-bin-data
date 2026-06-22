"""Database store lifecycle for card_bin_data."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Self

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Sequence

    from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

    from .importer import ImportResult
    from .sources import SourceAdapter

from .db.schema import create_schema
from .db.session import StoreDatabaseConfig, make_async_engine, make_session_factory, parse_database_url
from .importer import import_sources


class BinDataStore:
    """Own database configuration and async engine/session lifecycle."""

    __slots__ = ("_config", "_engine", "_session_factory")

    def __init__(self, config: StoreDatabaseConfig) -> None:
        """Initialize a store from validated database configuration."""
        self._config = config
        self._engine: AsyncEngine | None = None
        self._session_factory: async_sessionmaker[AsyncSession] | None = None

    @classmethod
    def from_url(cls, database_url: str) -> Self:
        """Create a store from an explicit SQLAlchemy async database URL.

        Returns:
            Store configured for the supplied database URL.
        """
        return cls(parse_database_url(database_url))

    @property
    def config(self) -> StoreDatabaseConfig:
        """Validated store database configuration."""
        return self._config

    @property
    def database_url(self) -> str:
        """Configured database URL as a masked public string."""
        return self._config.url.render_as_string()

    @property
    def drivername(self) -> str:
        """Configured SQLAlchemy driver name."""
        return self._config.drivername

    @property
    def engine(self) -> AsyncEngine:
        """Async SQLAlchemy engine, created lazily on first database use."""
        if self._engine is None:
            self._engine = make_async_engine(self._config)
        return self._engine

    @property
    def session_factory(self) -> async_sessionmaker[AsyncSession]:
        """Async session factory bound to the store engine."""
        if self._session_factory is None:
            self._session_factory = make_session_factory(self.engine)
        return self._session_factory

    async def init(self) -> None:
        """Create required card_bin_data schema."""
        await create_schema(self.engine)

    async def import_sources(
        self,
        adapters: Sequence[SourceAdapter],
        *,
        store_raw_payload: bool = True,
    ) -> ImportResult:
        """Import source adapters into the store inside one store-managed transaction.

        Args:
            adapters: Source adapters to collect and import.
            store_raw_payload: Store full raw source rows in provenance when true.

        Returns:
            Import counts for source, normalized, and provenance rows.
        """
        async with self.session_factory.begin() as session:
            return await self.import_sources_with_session(session, adapters, store_raw_payload=store_raw_payload)

    @staticmethod
    async def import_sources_with_session(
        session: AsyncSession,
        adapters: Sequence[SourceAdapter],
        *,
        store_raw_payload: bool = True,
    ) -> ImportResult:
        """Import source adapters using a caller-supplied async session.

        Args:
            session: Async SQLAlchemy session owned by the caller's transaction.
            adapters: Source adapters to collect and import.
            store_raw_payload: Store full raw source rows in provenance when true.

        Returns:
            Import counts for source, normalized, and provenance rows.
        """
        return await import_sources(session, adapters, store_raw_payload=store_raw_payload)

    @asynccontextmanager
    async def session(self) -> AsyncIterator[AsyncSession]:
        """Open a store-managed async session.

        Yields:
            Async SQLAlchemy session owned by the caller's unit of work.
        """
        async with self.session_factory() as session:
            yield session

    async def close(self) -> None:
        """Dispose store-owned database resources idempotently."""
        if self._engine is None:
            self._session_factory = None
            return

        await self._engine.dispose()
        self._engine = None
        self._session_factory = None
