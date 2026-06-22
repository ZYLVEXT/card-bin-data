"""Schema reset helpers for isolated integration tests."""

from sqlalchemy.ext.asyncio import AsyncEngine

from card_bin_data.db.schema import metadata


async def drop_schema(engine: AsyncEngine) -> None:
    """Drop card_bin_data tables and indexes for isolated tests."""
    async with engine.begin() as connection:
        await connection.run_sync(metadata.drop_all)
