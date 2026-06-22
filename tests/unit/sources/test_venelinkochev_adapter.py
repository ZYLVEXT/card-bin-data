"""Tests for the venelinkochev/bin-list-data CSV adapter."""
# ruff: noqa: S101

from __future__ import annotations

from pathlib import Path

import pytest

from card_bin_data.sources import SourceAdapter, VenelinkochevBinListDataAdapter

FIXTURE_PATH = Path("tests/fixtures/sources/venelinkochev.csv")
EXPECTED_RECORD_COUNT = 2


@pytest.mark.asyncio
async def test_venelinkochev_adapter_maps_enrichment_fields() -> None:
    """Enrichment source Brand maps to normalized scheme while preserving row payload."""
    adapter = VenelinkochevBinListDataAdapter(local_path=FIXTURE_PATH)

    records = [record async for record in adapter.iter_records()]

    assert isinstance(adapter, SourceAdapter)
    assert adapter.metadata.source_id == "venelinkochev/bin-list-data"
    assert adapter.metadata.license == "CC BY 4.0"
    assert len(records) == EXPECTED_RECORD_COUNT
    assert records[0].row_key == "venelinkochev.csv:2:002102"
    assert records[0].iin_start == "002102"
    assert records[0].scheme == "PRIVATE LABEL"
    assert records[0].type == "CREDIT"
    assert records[0].category == "STANDARD"
    assert records[0].country_alpha2 == "CN"
    assert records[0].country_alpha3 == "CHN"
    assert records[0].country_name == "CHINA"
    assert records[0].issuer_name == "CHINA MERCHANTS BANK"
    assert records[0].issuer_phone == "95555"
    assert records[0].issuer_url == "https://english.cmbchina.com"
    assert records[0].raw_payload["BIN"] == "002102"


@pytest.mark.asyncio
async def test_venelinkochev_adapter_normalizes_empty_fields_and_skips_malformed_rows() -> None:
    """Blank CSV fields become None and malformed BIN rows are skipped."""
    adapter = VenelinkochevBinListDataAdapter(local_path=FIXTURE_PATH)

    records = [record async for record in adapter.iter_records()]

    assert records[1].row_key == "venelinkochev.csv:3:002195"
    assert records[1].category is None
    assert records[1].issuer_phone is None
    assert {record.iin_start for record in records} == {"002102", "002195"}
