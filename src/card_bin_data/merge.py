"""Deterministic merge rules for normalized source records."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, AsyncIterator, Iterable, Iterator

    from .types import NormalizedSourceRecord


PRIMARY_SOURCE_ID = "binlist/data"
ENRICHMENT_SOURCE_ID = "venelinkochev/bin-list-data"
FALLBACK_SOURCE_ID = "marlonlp/binlist-data"
SIX_DIGIT_PREFIX_LENGTH = 6
EIGHT_DIGIT_PREFIX_LENGTH = 8

FIELD_PRIORITY: dict[str, tuple[str, ...]] = {
    "iin_end": (PRIMARY_SOURCE_ID,),
    "number_length": (PRIMARY_SOURCE_ID,),
    "luhn": (PRIMARY_SOURCE_ID,),
    "scheme": (PRIMARY_SOURCE_ID, ENRICHMENT_SOURCE_ID, FALLBACK_SOURCE_ID),
    "product_brand": (PRIMARY_SOURCE_ID,),
    "type": (PRIMARY_SOURCE_ID, ENRICHMENT_SOURCE_ID, FALLBACK_SOURCE_ID),
    "category": (ENRICHMENT_SOURCE_ID, FALLBACK_SOURCE_ID),
    "prepaid": (PRIMARY_SOURCE_ID,),
    "country_alpha2": (ENRICHMENT_SOURCE_ID, PRIMARY_SOURCE_ID),
    "country_alpha3": (ENRICHMENT_SOURCE_ID,),
    "country_name": (ENRICHMENT_SOURCE_ID,),
    "issuer_name": (ENRICHMENT_SOURCE_ID, PRIMARY_SOURCE_ID, FALLBACK_SOURCE_ID),
    "issuer_phone": (ENRICHMENT_SOURCE_ID, PRIMARY_SOURCE_ID),
    "issuer_url": (ENRICHMENT_SOURCE_ID, PRIMARY_SOURCE_ID),
    "issuer_city": (PRIMARY_SOURCE_ID,),
}

MERGED_FIELD_NAMES = tuple(FIELD_PRIORITY)
CROSS_PREFIX_FIELD_NAMES = tuple(
    field_name for field_name, source_ids in FIELD_PRIORITY.items() if PRIMARY_SOURCE_ID not in source_ids
)


@dataclass(frozen=True, slots=True)
class MergedSourceRecord:
    """One normalized record plus all source rows that contributed to it."""

    record: NormalizedSourceRecord
    sources: tuple[NormalizedSourceRecord, ...]


def merge_source_records(records: Iterable[NormalizedSourceRecord]) -> tuple[MergedSourceRecord, ...]:
    """Merge in-memory source records by BIN/IIN start using project source-priority rules.

    This convenience seam is for tests and small already-materialized inputs. Production imports use
    ``merge_sorted_source_records`` so the merge can stream from the staged on-disk sort.

    Returns:
        Deterministically ordered merged records, each carrying all contributing source rows.
    """
    grouped_records: dict[str, list[NormalizedSourceRecord]] = {}
    for record in records:
        grouped_records.setdefault(record.iin_start, []).append(record)

    return tuple(_merge_sorted_groups(sorted(grouped_records.items())))


async def merge_sorted_source_records(
    records: AsyncIterator[NormalizedSourceRecord],
) -> AsyncGenerator[MergedSourceRecord]:
    """Merge records already sorted by ``iin_start`` using a bounded prefix window.

    The import pipeline feeds this from an on-disk staging sort. Only the current
    exact group and still-relevant 6-digit prefix group are kept resident, so
    memory is bounded by duplicate rows for one prefix family rather than by the
    total source row count.

    Yields:
        Deterministically ordered merged records.
    """
    prefix_groups: dict[str, list[NormalizedSourceRecord]] = {}
    async for iin_start, group in _iter_sorted_groups(records):
        yield _merge_sorted_group(iin_start, group, prefix_groups)


def _merge_group(
    iin_start: str,
    group: list[NormalizedSourceRecord],
    prefix_group: list[NormalizedSourceRecord] | None,
) -> tuple[NormalizedSourceRecord, tuple[NormalizedSourceRecord, ...]]:
    seed = group[0]
    prefix_sources: list[NormalizedSourceRecord] = []
    merged_values = {field_name: _merged_value(field_name, group) for field_name in MERGED_FIELD_NAMES}
    if prefix_group is not None:
        for field_name in CROSS_PREFIX_FIELD_NAMES:
            if merged_values[field_name] is None:
                merged_values[field_name] = _merged_value(field_name, prefix_group, prefix_sources)

    ordered_prefix_sources = tuple(record for record in prefix_group or () if record in prefix_sources)
    return (
        replace(
            seed,
            row_key=f"merged:{iin_start}",
            iin_start=iin_start,
            raw_payload={},
            iin_end=merged_values["iin_end"],
            number_length=merged_values["number_length"],
            luhn=merged_values["luhn"],
            scheme=merged_values["scheme"],
            product_brand=merged_values["product_brand"],
            type=merged_values["type"],
            category=merged_values["category"],
            prepaid=merged_values["prepaid"],
            country_alpha2=merged_values["country_alpha2"],
            country_alpha3=merged_values["country_alpha3"],
            country_name=merged_values["country_name"],
            issuer_name=merged_values["issuer_name"],
            issuer_phone=merged_values["issuer_phone"],
            issuer_url=merged_values["issuer_url"],
            issuer_city=merged_values["issuer_city"],
        ),
        ordered_prefix_sources,
    )


def _merge_sorted_groups(groups: Iterable[tuple[str, list[NormalizedSourceRecord]]]) -> Iterator[MergedSourceRecord]:
    prefix_groups: dict[str, list[NormalizedSourceRecord]] = {}
    for iin_start, group in groups:
        yield _merge_sorted_group(iin_start, group, prefix_groups)


def _merge_sorted_group(
    iin_start: str,
    group: list[NormalizedSourceRecord],
    prefix_groups: dict[str, list[NormalizedSourceRecord]],
) -> MergedSourceRecord:
    _drop_expired_prefix_groups(prefix_groups, iin_start)
    prefix_group = _six_digit_prefix_group(iin_start, group, prefix_groups)
    merged_record, prefix_sources = _merge_group(iin_start, group, prefix_group)
    if len(iin_start) == SIX_DIGIT_PREFIX_LENGTH:
        prefix_groups[iin_start] = group
    return MergedSourceRecord(record=merged_record, sources=(*group, *prefix_sources))


async def _iter_sorted_groups(
    records: AsyncIterator[NormalizedSourceRecord],
) -> AsyncIterator[tuple[str, list[NormalizedSourceRecord]]]:
    current_iin_start: str | None = None
    group: list[NormalizedSourceRecord] = []
    async for record in records:
        if current_iin_start is None:
            current_iin_start = record.iin_start
        if record.iin_start != current_iin_start:
            yield current_iin_start, group
            current_iin_start = record.iin_start
            group = []
        group.append(record)
    if current_iin_start is not None:
        yield current_iin_start, group


def _drop_expired_prefix_groups(
    prefix_groups: dict[str, list[NormalizedSourceRecord]],
    iin_start: str,
) -> None:
    for prefix in tuple(prefix_groups):
        if not iin_start.startswith(prefix):
            del prefix_groups[prefix]


def _merged_value(
    field_name: str,
    group: list[NormalizedSourceRecord],
    source_accumulator: list[NormalizedSourceRecord] | None = None,
) -> object:
    for source_id in FIELD_PRIORITY[field_name]:
        for record in group:
            if record.source.source_id == source_id:
                value = getattr(record, field_name)
                if value is not None:
                    if source_accumulator is not None and record not in source_accumulator:
                        source_accumulator.append(record)
                    return value
    return None


def _six_digit_prefix_group(
    iin_start: str,
    group: list[NormalizedSourceRecord],
    prefix_groups: dict[str, list[NormalizedSourceRecord]],
) -> list[NormalizedSourceRecord] | None:
    if len(iin_start) != EIGHT_DIGIT_PREFIX_LENGTH:
        return None
    if not any(record.source.source_id == PRIMARY_SOURCE_ID for record in group):
        return None
    return prefix_groups.get(iin_start[:SIX_DIGIT_PREFIX_LENGTH])
