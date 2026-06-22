"""Tests for the binlist/data ranges CSV adapter."""
# ruff: noqa: S101

from __future__ import annotations

from pathlib import Path

import pytest

from card_bin_data.sources import BinlistDataAdapter, SourceAdapter

FIXTURE_PATH = Path("tests/fixtures/sources/binlist_ranges.csv")
EXPECTED_RECORD_COUNT = 2
EXPECTED_NUMBER_LENGTH = 16


@pytest.mark.asyncio
async def test_binlist_data_adapter_maps_primary_range_fields() -> None:
    """Primary source rows map scheme and product brand as distinct normalized fields."""
    adapter = BinlistDataAdapter(local_path=FIXTURE_PATH)

    records = [record async for record in adapter.iter_records()]

    assert isinstance(adapter, SourceAdapter)
    assert adapter.metadata.source_id == "binlist/data"
    assert adapter.metadata.local_path == FIXTURE_PATH
    assert len(records) == EXPECTED_RECORD_COUNT
    assert records[0].row_key == "binlist_ranges.csv:2:000123"
    assert records[0].iin_start == "000123"
    assert records[0].iin_end == "00012399"
    assert records[0].number_length == EXPECTED_NUMBER_LENGTH
    assert records[0].luhn is True
    assert records[0].scheme == "visa"
    assert records[0].product_brand == "Platinum"
    assert records[0].type == "credit"
    assert records[0].prepaid is False
    assert records[0].country_alpha2 == "US"
    assert records[0].issuer_name == "Example Bank"
    assert records[0].issuer_url == "https://bank.example"
    assert records[0].issuer_phone == "+1 555 0100"
    assert records[0].issuer_city == "New York"
    assert not records[0].raw_payload["bank_logo"]


@pytest.mark.asyncio
async def test_binlist_data_adapter_normalizes_empty_fields_and_skips_malformed_rows() -> None:
    """Blank CSV fields become None and rows without numeric IIN starts are skipped."""
    adapter = BinlistDataAdapter(local_path=FIXTURE_PATH)

    records = [record async for record in adapter.iter_records()]

    assert records[1].row_key == "binlist_ranges.csv:3:123456"
    assert records[1].iin_start == "123456"
    assert records[1].iin_end is None
    assert records[1].product_brand is None
    assert records[1].issuer_name is None
    assert not records[1].raw_payload["brand"]
    assert {record.iin_start for record in records} == {"000123", "123456"}
