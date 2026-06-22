"""Schema integration coverage for card_bin_data persistence models on every supported backend."""
# ruff: noqa: S101

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from sqlalchemy import inspect

if TYPE_CHECKING:
    from card_bin_data import BinDataStore


@pytest.mark.asyncio(loop_scope="session")
async def test_schema_creation_creates_tables_and_indexes(store: BinDataStore) -> None:
    """Schema creation succeeds on each backend and exposes required lookup indexes."""
    await store.init()

    async with store.engine.connect() as connection:
        table_names = await connection.run_sync(
            lambda sync_connection: set(inspect(sync_connection).get_table_names()),
        )
        indexes = await connection.run_sync(
            lambda sync_connection: {
                table_name: {
                    index["name"]: tuple(index["column_names"])
                    for index in inspect(sync_connection).get_indexes(table_name)
                }
                for table_name in table_names
            },
        )
        unique_constraints = await connection.run_sync(
            lambda sync_connection: {
                table_name: {
                    constraint["name"]: tuple(constraint["column_names"])
                    for constraint in inspect(sync_connection).get_unique_constraints(table_name)
                }
                for table_name in table_names
            },
        )
        columns = await connection.run_sync(
            lambda sync_connection: {
                table_name: {column["name"] for column in inspect(sync_connection).get_columns(table_name)}
                for table_name in table_names
            },
        )

    assert table_names >= {"data_sources", "bin_records", "bin_record_sources"}
    assert indexes["bin_records"]["ix_bin_records_iin_start"] == ("iin_start",)
    assert indexes["bin_records"]["ix_bin_records_range_boundaries_8"] == ("range_start_8", "range_end_8")
    assert "ix_bin_records_iin_range" not in indexes["bin_records"]
    assert indexes["bin_record_sources"]["ix_bin_record_sources_bin_record_id"] == ("bin_record_id",)
    assert "ix_data_sources_source_id" not in indexes["data_sources"]
    assert "ix_bin_record_sources_data_source_row" not in indexes["bin_record_sources"]
    assert unique_constraints["data_sources"]["uq_data_sources_source_id"] == ("source_id",)
    assert unique_constraints["bin_record_sources"]["uq_bin_record_sources_record_source_row"] == (
        "bin_record_id",
        "data_source_id",
        "source_row_key",
    )

    schema_column_names = set().union(*columns.values())
    forbidden_names = {"pan", "full_pan", "card_number", "account_number", "primary_account_number"}
    assert schema_column_names.isdisjoint(forbidden_names)
