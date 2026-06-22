"""Unit coverage for card_bin_data persistence model metadata."""
# ruff: noqa: S101

from sqlalchemy import String, UniqueConstraint
from sqlalchemy.schema import Table

from card_bin_data.db import BinRecordModel, BinRecordSourceModel, DataSourceModel, metadata


def test_model_tables_are_registered() -> None:
    """Models register the three persistence tables on shared metadata."""
    assert metadata.tables.keys() >= {"data_sources", "bin_records", "bin_record_sources"}
    assert DataSourceModel.__tablename__ == "data_sources"
    assert BinRecordModel.__tablename__ == "bin_records"
    assert BinRecordSourceModel.__tablename__ == "bin_record_sources"


def test_bin_prefix_columns_are_strings_and_no_pan_columns_exist() -> None:
    """BIN/IIN values are stored as strings and no full PAN-shaped columns exist."""
    bin_table = BinRecordModel.__table__

    assert isinstance(bin_table.c.iin_start.type, String)
    assert isinstance(bin_table.c.iin_end.type, String)
    assert isinstance(bin_table.c.range_start_8.type, String)
    assert isinstance(bin_table.c.range_end_8.type, String)

    all_columns = {
        column.name
        for table in (DataSourceModel.__table__, BinRecordModel.__table__, BinRecordSourceModel.__table__)
        for column in table.columns
    }
    forbidden_names = {"pan", "full_pan", "card_number", "account_number", "primary_account_number"}
    assert all_columns.isdisjoint(forbidden_names)


def test_indexes_and_unique_constraints_cover_lookup_and_idempotency_paths() -> None:
    """Indexes and uniqueness constraints cover lookup and import idempotency paths."""
    data_source_table = DataSourceModel.__table__
    bin_record_table = BinRecordModel.__table__
    record_source_table = BinRecordSourceModel.__table__
    assert isinstance(data_source_table, Table)
    assert isinstance(bin_record_table, Table)
    assert isinstance(record_source_table, Table)

    data_source_indexes = {
        str(index.name): {column.name for column in index.columns} for index in data_source_table.indexes
    }
    bin_indexes = {str(index.name): {column.name for column in index.columns} for index in bin_record_table.indexes}
    source_indexes = {
        str(index.name): {column.name for column in index.columns} for index in record_source_table.indexes
    }
    unique_constraints = {
        str(constraint.name): {column.name for column in constraint.columns}
        for table in (data_source_table, record_source_table)
        for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint)
    }

    assert bin_indexes["ix_bin_records_iin_start"] == {"iin_start"}
    assert bin_indexes["ix_bin_records_range_boundaries_8"] == {"range_start_8", "range_end_8"}
    # Range lookup uses the normalized boundary index; the legacy (iin_start, iin_end) index is unused.
    assert "ix_bin_records_iin_range" not in bin_indexes
    assert source_indexes["ix_bin_record_sources_bin_record_id"] == {"bin_record_id"}
    assert "ix_data_sources_source_id" not in data_source_indexes
    assert "ix_bin_record_sources_data_source_row" not in source_indexes
    assert unique_constraints["uq_data_sources_source_id"] == {"source_id"}
    assert unique_constraints["uq_bin_record_sources_record_source_row"] == {
        "bin_record_id",
        "data_source_id",
        "source_row_key",
    }
