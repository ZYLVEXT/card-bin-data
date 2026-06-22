"""Unit coverage for source merge priority."""
# ruff: noqa: S101

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import pytest

from card_bin_data.merge import merge_sorted_source_records, merge_source_records
from card_bin_data.types import NormalizedSourceRecord, SourceMetadata

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Iterable

PRIMARY = SourceMetadata("binlist/data", "binlist/data", "https://github.com/binlist/data.git")
ENRICHMENT = SourceMetadata(
    "venelinkochev/bin-list-data",
    "venelinkochev/bin-list-data",
    "https://github.com/venelinkochev/bin-list-data.git",
    license="CC BY 4.0",
)
FALLBACK = SourceMetadata(
    "marlonlp/binlist-data",
    "marlonlp/binlist-data",
    "https://github.com/marlonlp/binlist-data.git",
    license="CC BY 4.0",
)
PRIMARY_NUMBER_LENGTH = 16
STREAMING_LOOKAHEAD_RECORD_COUNT = 2


def test_merge_applies_primary_enrichment_and_fallback_priority() -> None:
    """Primary wins network/type/range, enrichment wins issuer/country, fallback fills gaps."""
    records = (
        NormalizedSourceRecord(
            source=FALLBACK,
            row_key="fallback-1",
            iin_start="457173",
            scheme="fallback-scheme",
            type="fallback-type",
            category="fallback-category",
            issuer_name="Fallback Bank",
            raw_payload={"bin": "457173"},
        ),
        NormalizedSourceRecord(
            source=ENRICHMENT,
            row_key="enrichment-1",
            iin_start="457173",
            scheme="enrichment-scheme",
            type="enrichment-type",
            category="enrichment-category",
            country_alpha2="US",
            country_alpha3="USA",
            country_name="United States",
            issuer_name="Enrichment Bank",
            issuer_phone="+1",
            issuer_url="https://issuer.example",
            raw_payload={"BIN": "457173"},
        ),
        NormalizedSourceRecord(
            source=PRIMARY,
            row_key="primary-1",
            iin_start="457173",
            iin_end="45717399",
            number_length=PRIMARY_NUMBER_LENGTH,
            luhn=True,
            scheme="primary-scheme",
            product_brand="Primary Product",
            type="primary-type",
            prepaid=False,
            country_alpha2="GB",
            issuer_name="Primary Bank",
            raw_payload={"iin_start": "457173"},
        ),
    )

    merged = merge_source_records(records)

    assert len(merged) == 1
    merged_record = merged[0].record
    assert merged_record.iin_start == "457173"
    assert merged_record.iin_end == "45717399"
    assert merged_record.number_length == PRIMARY_NUMBER_LENGTH
    assert merged_record.luhn is True
    assert merged_record.scheme == "primary-scheme"
    assert merged_record.product_brand == "Primary Product"
    assert merged_record.type == "primary-type"
    assert merged_record.category == "enrichment-category"
    assert merged_record.prepaid is False
    assert merged_record.country_alpha2 == "US"
    assert merged_record.country_alpha3 == "USA"
    assert merged_record.country_name == "United States"
    assert merged_record.issuer_name == "Enrichment Bank"
    assert merged_record.issuer_phone == "+1"
    assert merged_record.issuer_url == "https://issuer.example"
    assert {source.row_key for source in merged[0].sources} == {"primary-1", "enrichment-1", "fallback-1"}


def test_merge_uses_marlonlp_as_fallback_for_missing_values() -> None:
    """Fallback source fills values not provided by primary or enrichment records."""
    merged = merge_source_records(
        (
            NormalizedSourceRecord(source=PRIMARY, row_key="primary-1", iin_start="000123"),
            NormalizedSourceRecord(
                source=FALLBACK,
                row_key="fallback-1",
                iin_start="000123",
                scheme="mastercard",
                type="debit",
                category="classic",
                issuer_name="Fallback Credit Union",
            ),
        ),
    )

    assert merged[0].record.iin_start == "000123"
    assert merged[0].record.scheme == "mastercard"
    assert merged[0].record.type == "debit"
    assert merged[0].record.category == "classic"
    assert merged[0].record.issuer_name == "Fallback Credit Union"


def test_merge_enriches_eight_digit_primary_from_six_digit_group() -> None:
    """An 8-digit primary row can inherit primary-excluded fields from its 6-digit group."""
    primary_eight = NormalizedSourceRecord(
        source=PRIMARY,
        row_key="primary-8",
        iin_start="45717360",
        iin_end="45717360",
        number_length=PRIMARY_NUMBER_LENGTH,
        luhn=True,
        scheme="primary-scheme",
        product_brand="Primary Product",
        type="primary-type",
        country_alpha2="GB",
        issuer_name="Primary Bank",
        raw_payload={"iin_start": "45717360"},
    )
    enrichment_six = NormalizedSourceRecord(
        source=ENRICHMENT,
        row_key="enrichment-6",
        iin_start="457173",
        scheme="enrichment-scheme",
        type="enrichment-type",
        country_alpha2="US",
        country_alpha3="USA",
        country_name="United States",
        issuer_name="Enrichment Bank",
        raw_payload={"BIN": "457173"},
    )
    fallback_six = NormalizedSourceRecord(
        source=FALLBACK,
        row_key="fallback-6",
        iin_start="457173",
        scheme="fallback-scheme",
        type="fallback-type",
        category="fallback-category",
        issuer_name="Fallback Bank",
        raw_payload={"bin": "457173"},
    )

    merged = merge_source_records((primary_eight, enrichment_six, fallback_six))

    assert [record.record.iin_start for record in merged] == ["457173", "45717360"]
    eight_digit = merged[1]
    assert eight_digit.record.iin_start == "45717360"
    assert eight_digit.record.iin_end == "45717360"
    assert eight_digit.record.number_length == PRIMARY_NUMBER_LENGTH
    assert eight_digit.record.luhn is True
    assert eight_digit.record.scheme == "primary-scheme"
    assert eight_digit.record.product_brand == "Primary Product"
    assert eight_digit.record.type == "primary-type"
    assert eight_digit.record.category == "fallback-category"
    assert eight_digit.record.country_alpha2 == "GB"
    assert eight_digit.record.country_alpha3 == "USA"
    assert eight_digit.record.country_name == "United States"
    assert eight_digit.record.issuer_name == "Primary Bank"
    assert eight_digit.sources == (primary_eight, enrichment_six, fallback_six)

    six_digit = merged[0]
    assert six_digit.record.category == "fallback-category"
    assert six_digit.record.country_alpha3 == "USA"
    assert six_digit.record.country_name == "United States"
    assert six_digit.sources == (enrichment_six, fallback_six)


def test_merge_leaves_unmatched_eight_digit_primary_group_unchanged() -> None:
    """An 8-digit primary row without a 6-digit group keeps today's exact-group behavior."""
    primary_eight = NormalizedSourceRecord(
        source=PRIMARY,
        row_key="primary-8",
        iin_start="55555555",
        scheme="primary-scheme",
        type="primary-type",
        raw_payload={"iin_start": "55555555"},
    )

    merged = merge_source_records((primary_eight,))

    assert len(merged) == 1
    assert merged[0].record.iin_start == "55555555"
    assert merged[0].record.scheme == "primary-scheme"
    assert merged[0].record.type == "primary-type"
    assert merged[0].record.category is None
    assert merged[0].record.country_alpha3 is None
    assert merged[0].record.country_name is None
    assert merged[0].sources == (primary_eight,)


def test_merge_keeps_exact_eight_digit_enrichment_over_six_digit_prefix() -> None:
    """Exact 8-digit enrichment values win before the 6-digit prefix fallback is considered."""
    primary_eight = NormalizedSourceRecord(source=PRIMARY, row_key="primary-8", iin_start="45717360")
    enrichment_eight = NormalizedSourceRecord(
        source=ENRICHMENT,
        row_key="enrichment-8",
        iin_start="45717360",
        category="exact-category",
        country_alpha3="CAN",
        country_name="Canada",
    )
    enrichment_six = NormalizedSourceRecord(
        source=ENRICHMENT,
        row_key="enrichment-6",
        iin_start="457173",
        category="prefix-category",
        country_alpha3="USA",
        country_name="United States",
    )

    merged = merge_source_records((primary_eight, enrichment_eight, enrichment_six))

    eight_digit = merged[1]
    assert eight_digit.record.category == "exact-category"
    assert eight_digit.record.country_alpha3 == "CAN"
    assert eight_digit.record.country_name == "Canada"
    assert eight_digit.sources == (primary_eight, enrichment_eight)


def test_merge_ignores_prefix_group_without_values_for_eight_digit_primary() -> None:
    """A matching 6-digit group with no usable enrichment values does not change provenance."""
    primary_eight = NormalizedSourceRecord(source=PRIMARY, row_key="primary-8", iin_start="11111111")
    enrichment_six = NormalizedSourceRecord(source=ENRICHMENT, row_key="enrichment-6", iin_start="111111")

    merged = merge_source_records((primary_eight, enrichment_six))

    eight_digit = merged[1]
    assert eight_digit.record.category is None
    assert eight_digit.record.country_alpha3 is None
    assert eight_digit.record.country_name is None
    assert eight_digit.sources == (primary_eight,)


def test_merge_does_not_cross_prefix_enrich_non_primary_eight_digit_group() -> None:
    """Only 8-digit primary groups use the 6-digit prefix fallback."""
    enrichment_eight = NormalizedSourceRecord(source=ENRICHMENT, row_key="enrichment-8", iin_start="22222222")
    fallback_six = NormalizedSourceRecord(
        source=FALLBACK,
        row_key="fallback-6",
        iin_start="222222",
        category="fallback-category",
    )

    merged = merge_source_records((enrichment_eight, fallback_six))

    eight_digit = merged[1]
    assert eight_digit.record.category is None
    assert eight_digit.sources == (enrichment_eight,)


@pytest.mark.asyncio
async def test_sync_merge_convenience_matches_sorted_streaming_path() -> None:
    """The retained in-memory test seam matches the production sorted stream merge."""
    records = (
        NormalizedSourceRecord(
            source=PRIMARY,
            row_key="primary-8",
            iin_start="45717360",
            scheme="primary-scheme",
            category="exact-category",
        ),
        NormalizedSourceRecord(
            source=ENRICHMENT,
            row_key="enrichment-6",
            iin_start="457173",
            country_alpha3="USA",
            country_name="United States",
        ),
        NormalizedSourceRecord(
            source=FALLBACK,
            row_key="fallback-6",
            iin_start="457173",
            category="fallback-category",
        ),
    )

    sorted_records = sorted(records, key=lambda record: record.iin_start)

    streaming_records = [record async for record in merge_sorted_source_records(_async_records(sorted_records))]

    assert merge_source_records(records) == tuple(streaming_records)


@pytest.mark.asyncio
async def test_sorted_merge_streams_without_consuming_all_groups() -> None:
    """Sorted streaming merge holds one lookahead group instead of all input rows."""
    yielded_count = 0
    records = tuple(
        NormalizedSourceRecord(source=PRIMARY, row_key=f"primary-{index}", iin_start=f"10000{index}")
        for index in range(6)
    )

    async def record_stream() -> AsyncIterator[NormalizedSourceRecord]:
        nonlocal yielded_count
        for record in records:
            await asyncio.sleep(0)
            yielded_count += 1
            yield record

    merged_stream = merge_sorted_source_records(record_stream())
    first = await anext(merged_stream)
    await merged_stream.aclose()

    assert first.record.iin_start == "100000"
    assert yielded_count == STREAMING_LOOKAHEAD_RECORD_COUNT


@pytest.mark.asyncio
async def test_sorted_merge_handles_empty_stream() -> None:
    """Sorted streaming merge accepts an empty source stream."""
    assert [record async for record in merge_sorted_source_records(_async_records(()))] == []


async def _async_records(records: Iterable[NormalizedSourceRecord]) -> AsyncIterator[NormalizedSourceRecord]:
    for record in records:
        await asyncio.sleep(0)
        yield record
