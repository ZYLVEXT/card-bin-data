"""Schema metadata helpers for card_bin_data persistence.

The metadata is backend-neutral SQLAlchemy metadata from Advanced Alchemy models.
PostgreSQL production deployments should use migrations rather than runtime
``create_all`` so index and constraint operations can be scheduled safely.
"""

from sqlalchemy import MetaData
from sqlalchemy.ext.asyncio import AsyncEngine

from .models import BinRecordModel

metadata: MetaData = BinRecordModel.metadata


async def create_schema(engine: AsyncEngine) -> None:
    """Create card_bin_data tables and indexes for local/dev/test databases."""
    async with engine.begin() as connection:
        await connection.run_sync(metadata.create_all)
