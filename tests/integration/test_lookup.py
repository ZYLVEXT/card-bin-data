"""Integration coverage for indexed lookup behavior on every supported backend."""
# ruff: noqa: S101

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import pytest

from card_bin_data import BinData
from card_bin_data.types import LookupStatus, NormalizedSourceRecord, SourceMetadata

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from card_bin_data import BinDataStore
    from card_bin_data.sources import SourceAdapter


PRIMARY = SourceMetadata("binlist/data", "binlist/data", "https://github.com/binlist/data.git")
ENRICHMENT = SourceMetadata(
    "venelinkochev/bin-list-data",
    "venelinkochev/bin-list-data",
    "https://github.com/venelinkochev/bin-list-data.git",
    license="CC BY 4.0",
)


@pytest.mark.parametrize(
    ("query", "expected_status", "expected_iin_start"),
    [
        ("40000000", LookupStatus.FOUND, "400000"),
        ("40049900", LookupStatus.FOUND, "400000"),
        ("40099900", LookupStatus.FOUND, "400000"),
        ("39999999", LookupStatus.NOT_FOUND, None),
        ("40100000", LookupStatus.NOT_FOUND, None),
    ],
)
@pytest.mark.asyncio(loop_scope="session")
async def test_six_digit_range_boundary_queries_resolve_against_normalized_boundaries(
    store: BinDataStore,
    query: str,
    expected_status: LookupStatus,
    expected_iin_start: str | None,
) -> None:
    """Six-digit range boundaries compare against fixed-width lookup prefixes."""
    client = BinData(store=store)
    await store.init()
    await store.import_sources(_lookup_fixture_adapters())

    result = await client.lookup(query)

    assert result.status is expected_status
    assert result.query.candidates == (query, query[:6])
    if expected_iin_start is None:
        assert result.data is None
        assert result.sources == ()
        return

    assert result.data is not None
    assert result.data.iin_start == expected_iin_start
    assert result.data.iin_end == "400999"
    assert result.data.scheme == "six-digit-range"


@pytest.mark.parametrize(
    ("query", "expected_status"),
    [
        ("45717300", LookupStatus.FOUND),
        ("45717350", LookupStatus.FOUND),
        ("45717399", LookupStatus.FOUND),
        ("45717299", LookupStatus.NOT_FOUND),
        ("45717400", LookupStatus.NOT_FOUND),
    ],
)
@pytest.mark.asyncio(loop_scope="session")
async def test_eight_digit_range_boundary_queries_resolve_against_normalized_boundaries(
    store: BinDataStore,
    query: str,
    expected_status: LookupStatus,
) -> None:
    """Eight-digit range boundaries compare against fixed-width lookup prefixes."""
    client = BinData(store=store)
    await store.init()
    await store.import_sources(_lookup_fixture_adapters())

    result = await client.lookup(query)

    assert result.status is expected_status
    assert result.query.candidates == (query, query[:6])
    if expected_status is LookupStatus.NOT_FOUND:
        assert result.data is None
        assert result.sources == ()
        return

    assert result.data is not None
    assert result.data.iin_start == "45717300"
    assert result.data.iin_end == "45717399"
    assert result.data.scheme == "visa-range"


@pytest.mark.asyncio(loop_scope="session")
async def test_overlapping_ranges_return_more_specific_eight_digit_range(store: BinDataStore) -> None:
    """Overlapping ranges prefer the longer IIN start."""
    client = BinData(store=store)
    await store.init()
    await store.import_sources(_lookup_fixture_adapters())

    result = await client.lookup("40050050")

    assert result.status is LookupStatus.FOUND
    assert result.data is not None
    assert result.data.iin_start == "40050000"
    assert result.data.iin_end == "40050099"
    assert result.data.scheme == "eight-digit-overlap-range"


@dataclass(frozen=True, slots=True)
class StaticAdapter:
    """Small source adapter for lookup integration tests."""

    metadata: SourceMetadata
    records: tuple[NormalizedSourceRecord, ...]

    async def iter_records(self) -> AsyncIterator[NormalizedSourceRecord]:
        """Yield configured normalized source rows."""
        for record in self.records:
            yield record


@pytest.mark.asyncio(loop_scope="session")
async def test_lookup_priority_statuses_attribution_and_pan_safety(store: BinDataStore) -> None:
    """Lookup returns typed statuses, specific records first, and source attribution."""
    client = BinData(store=store)
    await store.init()
    await store.import_sources(_lookup_fixture_adapters())

    exact_8 = await client.lookup("45717360")
    async with store.session() as session:
        exact_8_with_session = await client.lookup_with_session(session, "45717360")
    range_match = await client.lookup("45717361")
    range_upper_boundary = await client.lookup("45717399")
    exact_6 = await client.lookup("12345678")
    not_found = await client.lookup("999999")
    invalid = await client.lookup("12345")
    full_pan = await client.lookup("4571 7360 1234 5678")

    assert exact_8.status is LookupStatus.FOUND
    assert exact_8.data is not None
    assert exact_8.data.iin_start == "45717360"
    assert exact_8.data.scheme == "visa-exact"
    assert {source.source_id for source in exact_8.sources} == {"binlist/data", "venelinkochev/bin-list-data"}
    assert {source.source_row_key for source in exact_8.sources} == {"primary-exact-8", "enrichment-exact-8"}
    assert exact_8_with_session == exact_8

    assert range_match.status is LookupStatus.FOUND
    assert range_match.data is not None
    assert range_match.data.iin_start == "45717300"
    assert range_match.data.iin_end == "45717399"
    assert range_match.data.scheme == "visa-range"

    assert range_upper_boundary.status is LookupStatus.FOUND
    assert range_upper_boundary.data is not None
    assert range_upper_boundary.data.iin_start == "45717300"
    assert range_upper_boundary.data.iin_end == "45717399"

    assert exact_6.status is LookupStatus.FOUND
    assert exact_6.data is not None
    assert exact_6.data.iin_start == "123456"

    assert not_found.status is LookupStatus.NOT_FOUND
    assert not_found.data is None
    assert not_found.sources == ()

    assert invalid.status is LookupStatus.INVALID
    assert invalid.data is None
    assert invalid.query.candidates == ()

    assert full_pan.status is LookupStatus.FOUND
    assert full_pan.query.candidates == ("45717360", "457173")
    assert full_pan.query.is_full_pan_input is True
    assert "4571736012345678" not in repr(full_pan)
    assert "4571 7360 1234 5678" not in repr(full_pan)


def _lookup_fixture_adapters() -> tuple[SourceAdapter, ...]:
    return (
        StaticAdapter(
            PRIMARY,
            (
                NormalizedSourceRecord(
                    source=PRIMARY,
                    row_key="primary-exact-8",
                    iin_start="45717360",
                    scheme="visa-exact",
                    type="debit",
                    issuer_name="Exact Bank",
                ),
                NormalizedSourceRecord(
                    source=PRIMARY,
                    row_key="primary-range",
                    iin_start="45717300",
                    iin_end="45717399",
                    scheme="visa-range",
                    type="credit",
                    issuer_name="Range Bank",
                ),
                NormalizedSourceRecord(
                    source=PRIMARY,
                    row_key="primary-exact-6",
                    iin_start="123456",
                    scheme="mastercard-six",
                    issuer_name="Six Bank",
                ),
                NormalizedSourceRecord(
                    source=PRIMARY,
                    row_key="primary-six-digit-range",
                    iin_start="400000",
                    iin_end="400999",
                    scheme="six-digit-range",
                    issuer_name="Six Digit Range Bank",
                ),
                NormalizedSourceRecord(
                    source=PRIMARY,
                    row_key="primary-eight-digit-overlap-range",
                    iin_start="40050000",
                    iin_end="40050099",
                    scheme="eight-digit-overlap-range",
                    issuer_name="Eight Digit Range Bank",
                ),
            ),
        ),
        StaticAdapter(
            ENRICHMENT,
            (
                NormalizedSourceRecord(
                    source=ENRICHMENT,
                    row_key="enrichment-exact-8",
                    iin_start="45717360",
                    country_alpha2="US",
                    country_alpha3="USA",
                    country_name="United States",
                    issuer_name="Enrichment Bank",
                    issuer_url="https://issuer.example",
                ),
            ),
        ),
    )
