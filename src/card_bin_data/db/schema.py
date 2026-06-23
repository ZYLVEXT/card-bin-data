"""Schema metadata helpers for card_bin_data persistence.

``metadata`` is the private, bind-scoped SQLAlchemy ``MetaData`` owning only the
card_bin_data tables (see :mod:`card_bin_data.db.base`). It is backend-neutral and
isolated from advanced_alchemy's shared ``orm_registry`` metadata, so importing
these models never injects their tables into a host application's default
metadata. A host that wants Alembic to manage these tables adds this object to
its ``target_metadata`` (see the Migrations section of the README).

PostgreSQL production deployments should use those migrations rather than runtime
``create_all`` so index and constraint operations can be scheduled safely.
"""

from sqlalchemy import MetaData
from sqlalchemy.ext.asyncio import AsyncEngine

from .base import CardBinDataBase

metadata: MetaData = CardBinDataBase.metadata


async def create_schema(engine: AsyncEngine) -> None:
    """Create card_bin_data tables and indexes for local/dev/test databases."""
    async with engine.begin() as connection:
        await connection.run_sync(metadata.create_all)
