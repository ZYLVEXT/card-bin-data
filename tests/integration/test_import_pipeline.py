"""Integration coverage for source import and merge pipeline on every supported backend."""
# ruff: noqa: S101, SLF001

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import func, select

import card_bin_data.db.services as db_services
from card_bin_data import importer
from card_bin_data.db import BinRecordModel, BinRecordSourceModel, DataSourceModel, ImportedRecordsService
from card_bin_data.types import NormalizedSourceRecord, SourceMetadata

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Sequence
    from datetime import datetime

    from card_bin_data import BinDataStore
    from card_bin_data.merge import MergedSourceRecord
    from card_bin_data.sources import SourceAdapter

EXPECTED_SOURCE_RECORD_COUNT = 5
EXPECTED_NORMALIZED_RECORD_COUNT = 3
EXPECTED_PROVENANCE_RECORD_COUNT = 6
CHUNK_TEST_BATCH_SIZE = 2
BOUNDED_IMPORT_GROUP_COUNT = 24
BOUNDED_TEST_STAGE_BATCH_SIZE = 5
BOUNDED_TEST_INSERT_BATCH_SIZE = 4


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


@dataclass(frozen=True, slots=True)
class StaticAdapter:
    """Small source adapter for import pipeline tests."""

    metadata: SourceMetadata
    records: tuple[NormalizedSourceRecord, ...]

    async def iter_records(self) -> AsyncIterator[NormalizedSourceRecord]:
        """Yield configured normalized source rows."""
        for record in self.records:
            yield record


@dataclass(frozen=True, slots=True)
class FailingAdapter:
    """Adapter that fails after yielding a row."""

    metadata: SourceMetadata

    async def iter_records(self) -> AsyncIterator[NormalizedSourceRecord]:
        """Yield one row and then fail before import writes are attempted.

        Raises:
            RuntimeError: Always raised after the first row.
        """
        yield NormalizedSourceRecord(source=self.metadata, row_key="failing-1", iin_start="999999")
        msg = "source read failed"
        raise RuntimeError(msg)


@dataclass(slots=True)
class SinglePassAdapter:
    """Adapter that fails if the import pipeline tries to parse it twice."""

    metadata: SourceMetadata
    records: tuple[NormalizedSourceRecord, ...]
    iteration_count: int = 0

    async def iter_records(self) -> AsyncIterator[NormalizedSourceRecord]:
        """Yield configured records only on the first iteration.

        Raises:
            AssertionError: If the importer tries to re-read the source.
        """
        self.iteration_count += 1
        if self.iteration_count > 1:
            msg = "adapter was parsed more than once"
            raise AssertionError(msg)
        for record in self.records:
            yield record


@pytest.mark.asyncio(loop_scope="session")
async def test_import_pipeline_merges_sources_preserves_provenance_and_is_idempotent(store: BinDataStore) -> None:
    """Importing fixture adapters writes merged records and stable provenance rows."""
    adapters = _fixture_adapters()
    await store.init()

    first_result = await store.import_sources(adapters)
    first_counts = await _table_counts(store)
    second_result = await store.import_sources(adapters)
    second_counts = await _table_counts(store)
    third_result = await store.import_sources(adapters)
    third_counts = await _table_counts(store)
    record = await _single_record(store, "457173")
    provenance = await _provenance_rows(store, "457173")
    eight_digit_record = await _single_record(store, "45717360")
    eight_digit_provenance = await _provenance_rows(store, "45717360")

    assert first_result.source_record_count == EXPECTED_SOURCE_RECORD_COUNT
    assert first_result.normalized_record_count == EXPECTED_NORMALIZED_RECORD_COUNT
    assert first_result.provenance_record_count == EXPECTED_PROVENANCE_RECORD_COUNT
    assert second_result == first_result
    assert third_result == first_result
    assert (
        first_counts
        == second_counts
        == third_counts
        == {
            "data_sources": 3,
            "bin_records": 3,
            "bin_record_sources": 6,
        }
    )
    assert record.iin_end == "45717399"
    assert record.range_start_8 == "45717300"
    assert record.range_end_8 == "45717399"
    assert record.scheme == "visa-primary"
    assert record.type == "debit-primary"
    assert record.category == "consumer"
    assert record.country_alpha2 == "US"
    assert record.country_alpha3 == "USA"
    assert record.country_name == "United States"
    assert record.issuer_name == "Enrichment Bank"
    assert record.issuer_phone == "+1-555-0100"
    assert record.issuer_url == "https://enrichment.example"
    assert {(source_id, row_key) for source_id, row_key in provenance} == {
        ("binlist/data", "primary-457173"),
        ("venelinkochev/bin-list-data", "enrichment-457173"),
        ("marlonlp/binlist-data", "fallback-457173"),
    }
    assert eight_digit_record.iin_end == "45717360"
    assert eight_digit_record.range_start_8 == "45717360"
    assert eight_digit_record.range_end_8 == "45717360"
    assert eight_digit_record.scheme == "visa-primary-8"
    assert eight_digit_record.type == "debit-primary-8"
    assert eight_digit_record.category == "consumer"
    assert eight_digit_record.country_alpha2 == "CA"
    assert eight_digit_record.country_alpha3 == "USA"
    assert eight_digit_record.country_name == "United States"
    assert eight_digit_record.issuer_name == "Primary Eight Bank"
    assert {(source_id, row_key) for source_id, row_key in eight_digit_provenance} == {
        ("binlist/data", "primary-45717360"),
        ("venelinkochev/bin-list-data", "enrichment-457173"),
    }
    await _assert_fixture_raw_payloads(store)
    non_range_record = await _single_record(store, "000123")
    assert non_range_record.iin_end is None
    assert non_range_record.range_start_8 is None
    assert non_range_record.range_end_8 is None


@pytest.mark.asyncio(loop_scope="session")
async def test_import_pipeline_can_skip_raw_payload_storage(store: BinDataStore) -> None:
    """Importing without raw payloads keeps normalized data and source attribution."""
    await store.init()

    result = await store.import_sources(_fixture_adapters(), store_raw_payload=False)
    record = await _single_record(store, "457173")
    provenance = await _provenance_rows(store, "457173")

    assert result.source_record_count == EXPECTED_SOURCE_RECORD_COUNT
    assert result.normalized_record_count == EXPECTED_NORMALIZED_RECORD_COUNT
    assert result.provenance_record_count == EXPECTED_PROVENANCE_RECORD_COUNT
    assert await _table_counts(store) == {"data_sources": 3, "bin_records": 3, "bin_record_sources": 6}
    assert record.iin_end == "45717399"
    assert record.scheme == "visa-primary"
    assert record.category == "consumer"
    assert record.country_alpha2 == "US"
    assert record.issuer_name == "Enrichment Bank"
    assert {(source_id, row_key) for source_id, row_key in provenance} == {
        ("binlist/data", "primary-457173"),
        ("venelinkochev/bin-list-data", "enrichment-457173"),
        ("marlonlp/binlist-data", "fallback-457173"),
    }
    assert await _raw_payloads_by_source_row(store, "457173") == {
        ("binlist/data", "primary-457173"): {},
        ("venelinkochev/bin-list-data", "enrichment-457173"): {},
        ("marlonlp/binlist-data", "fallback-457173"): {},
    }
    assert await _raw_payloads_by_source_row(store, "45717360") == {
        ("binlist/data", "primary-45717360"): {},
        ("venelinkochev/bin-list-data", "enrichment-457173"): {},
    }


@pytest.mark.asyncio(loop_scope="session")
async def test_import_pipeline_chunks_writes_without_changing_results(
    store: BinDataStore,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Chunked inserts bound in-flight rows while preserving import results."""
    bin_record_batch_sizes: list[int] = []
    record_source_batch_sizes: list[int] = []
    original_bin_record_batch = ImportedRecordsService._insert_bin_record_batch
    original_record_source_batch = ImportedRecordsService._insert_record_source_batch

    async def record_bin_record_batch(
        self: ImportedRecordsService,
        rows: list[dict[str, object]],
    ) -> dict[str, int]:
        bin_record_batch_sizes.append(len(rows))
        return await original_bin_record_batch(self, rows)

    async def record_source_batch(self: ImportedRecordsService, rows: Sequence[dict[str, object]]) -> None:
        record_source_batch_sizes.append(len(rows))
        await original_record_source_batch(self, rows)

    await store.init()
    monkeypatch.setattr(db_services, "INSERT_BATCH_SIZE", CHUNK_TEST_BATCH_SIZE)
    monkeypatch.setattr(ImportedRecordsService, "_insert_bin_record_batch", record_bin_record_batch)
    monkeypatch.setattr(ImportedRecordsService, "_insert_record_source_batch", record_source_batch)

    result = await store.import_sources(_fixture_adapters())

    assert result.source_record_count == EXPECTED_SOURCE_RECORD_COUNT
    assert result.normalized_record_count == EXPECTED_NORMALIZED_RECORD_COUNT
    assert result.provenance_record_count == EXPECTED_PROVENANCE_RECORD_COUNT
    assert await _table_counts(store) == {"data_sources": 3, "bin_records": 3, "bin_record_sources": 6}
    assert len(bin_record_batch_sizes) > 1
    assert len(record_source_batch_sizes) > 1
    assert max(bin_record_batch_sizes) <= CHUNK_TEST_BATCH_SIZE
    assert max(record_source_batch_sizes) <= CHUNK_TEST_BATCH_SIZE


@pytest.mark.asyncio(loop_scope="session")
async def test_import_pipeline_uses_single_parse_and_bounded_streaming_batches(
    store: BinDataStore,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Large distinct-group imports stay bounded while preserving cross-prefix provenance."""
    stage_batch_sizes: list[int] = []
    merged_batch_sizes: list[int] = []
    primary_adapter = SinglePassAdapter(PRIMARY, _bounded_primary_records())
    enrichment_adapter = SinglePassAdapter(ENRICHMENT, _bounded_enrichment_records())
    original_stage_insert = importer._SourceRecordStage.insert_records
    original_merged_batch = ImportedRecordsService._insert_merged_record_batch

    async def record_stage_insert(
        self: importer._SourceRecordStage,
        records: list[NormalizedSourceRecord],
    ) -> None:
        stage_batch_sizes.append(len(records))
        await original_stage_insert(self, records)

    async def record_merged_batch(
        self: ImportedRecordsService,
        records: list[MergedSourceRecord],
        data_source_ids: dict[str, int],
        imported_at: datetime,
        *,
        store_raw_payload: bool,
    ) -> None:
        merged_batch_sizes.append(len(records))
        await original_merged_batch(
            self,
            records,
            data_source_ids,
            imported_at,
            store_raw_payload=store_raw_payload,
        )

    await store.init()
    monkeypatch.setattr(importer, "STAGING_INSERT_BATCH_SIZE", BOUNDED_TEST_STAGE_BATCH_SIZE)
    monkeypatch.setattr(db_services, "INSERT_BATCH_SIZE", BOUNDED_TEST_INSERT_BATCH_SIZE)
    monkeypatch.setattr(importer._SourceRecordStage, "insert_records", record_stage_insert)
    monkeypatch.setattr(ImportedRecordsService, "_insert_merged_record_batch", record_merged_batch)

    result = await store.import_sources((primary_adapter, enrichment_adapter))
    eight_digit_record = await _single_record(store, "55555500")
    eight_digit_provenance = await _provenance_rows(store, "55555500")

    assert primary_adapter.iteration_count == 1
    assert enrichment_adapter.iteration_count == 1
    assert result.source_record_count == BOUNDED_IMPORT_GROUP_COUNT + 2
    assert result.normalized_record_count == BOUNDED_IMPORT_GROUP_COUNT + 2
    assert result.provenance_record_count == BOUNDED_IMPORT_GROUP_COUNT + 3
    assert await _table_counts(store) == {
        "data_sources": 2,
        "bin_records": BOUNDED_IMPORT_GROUP_COUNT + 2,
        "bin_record_sources": BOUNDED_IMPORT_GROUP_COUNT + 3,
    }
    assert len(stage_batch_sizes) > 1
    assert len(merged_batch_sizes) > 1
    assert max(stage_batch_sizes) <= BOUNDED_TEST_STAGE_BATCH_SIZE
    assert max(merged_batch_sizes) <= BOUNDED_TEST_INSERT_BATCH_SIZE
    assert eight_digit_record.category == "consumer"
    assert eight_digit_record.country_alpha3 == "USA"
    assert eight_digit_record.country_name == "United States"
    assert set(eight_digit_provenance) == {
        ("binlist/data", "primary-55555500"),
        ("venelinkochev/bin-list-data", "enrichment-555555"),
    }


@pytest.mark.asyncio(loop_scope="session")
async def test_import_pipeline_accepts_empty_adapter_stream(store: BinDataStore) -> None:
    """An adapter with no rows still performs an empty transactional replacement."""
    adapter = SinglePassAdapter(PRIMARY, ())
    await store.init()

    result = await store.import_sources((adapter,))

    assert adapter.iteration_count == 1
    assert result.source_record_count == 0
    assert result.normalized_record_count == 0
    assert result.provenance_record_count == 0
    assert await _table_counts(store) == {"data_sources": 0, "bin_records": 0, "bin_record_sources": 0}


@pytest.mark.asyncio(loop_scope="session")
async def test_import_sources_with_session_uses_caller_transaction(store: BinDataStore) -> None:
    """Caller-supplied sessions can drive imports without a store-owned transaction."""
    await store.init()
    async with store.session_factory.begin() as session:
        result = await store.import_sources_with_session(session, _fixture_adapters(), store_raw_payload=False)

    assert result.source_record_count == EXPECTED_SOURCE_RECORD_COUNT
    assert await _table_counts(store) == {"data_sources": 3, "bin_records": 3, "bin_record_sources": 6}
    assert await _raw_payloads_by_source_row(store, "457173") == {
        ("binlist/data", "primary-457173"): {},
        ("venelinkochev/bin-list-data", "enrichment-457173"): {},
        ("marlonlp/binlist-data", "fallback-457173"): {},
    }


@pytest.mark.asyncio(loop_scope="session")
async def test_import_failure_does_not_replace_visible_dataset(store: BinDataStore) -> None:
    """A failed import leaves the previously committed normalized dataset visible."""
    await store.init()
    await store.import_sources(_fixture_adapters())
    before_counts = await _table_counts(store)

    with pytest.raises(RuntimeError, match="source read failed"):
        await store.import_sources((FailingAdapter(PRIMARY),))

    assert await _table_counts(store) == before_counts
    assert (await _single_record(store, "457173")).issuer_name == "Enrichment Bank"


@pytest.mark.asyncio(loop_scope="session")
async def test_import_write_failure_rolls_back_replace_all(
    store: BinDataStore,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A write failure after replacement starts leaves the previous committed dataset intact."""

    async def fail_provenance_insert_batch(
        self: ImportedRecordsService,
        rows: Sequence[dict[str, object]],
    ) -> None:
        """Fail while bulk provenance rows are being inserted.

        Raises:
            RuntimeError: Always raised to force transaction rollback.
        """
        del self, rows
        await asyncio.sleep(0)
        msg = "provenance write failed"
        raise RuntimeError(msg)

    await store.init()
    await store.import_sources(_fixture_adapters())
    before_counts = await _table_counts(store)
    monkeypatch.setattr(ImportedRecordsService, "_insert_record_source_batch", fail_provenance_insert_batch)

    with pytest.raises(RuntimeError, match="provenance write failed"):
        await store.import_sources(
            (
                StaticAdapter(
                    PRIMARY,
                    (NormalizedSourceRecord(source=PRIMARY, row_key="new-222222", iin_start="222222"),),
                ),
            ),
        )

    assert await _table_counts(store) == before_counts
    assert (await _single_record(store, "457173")).issuer_name == "Enrichment Bank"
    assert await _record_count(store, "222222") == 0


def _fixture_adapters() -> tuple[SourceAdapter, ...]:
    return (
        StaticAdapter(
            PRIMARY,
            (
                NormalizedSourceRecord(
                    source=PRIMARY,
                    row_key="primary-457173",
                    iin_start="457173",
                    iin_end="45717399",
                    number_length=16,
                    luhn=True,
                    scheme="visa-primary",
                    type="debit-primary",
                    country_alpha2="GB",
                    issuer_name="Primary Bank",
                    raw_payload={"iin_start": "457173"},
                ),
                NormalizedSourceRecord(
                    source=PRIMARY,
                    row_key="primary-000123",
                    iin_start="000123",
                    scheme="mastercard-primary",
                    raw_payload={"iin_start": "000123"},
                ),
                NormalizedSourceRecord(
                    source=PRIMARY,
                    row_key="primary-45717360",
                    iin_start="45717360",
                    iin_end="45717360",
                    number_length=16,
                    luhn=True,
                    scheme="visa-primary-8",
                    type="debit-primary-8",
                    country_alpha2="CA",
                    issuer_name="Primary Eight Bank",
                    raw_payload={"iin_start": "45717360"},
                ),
            ),
        ),
        StaticAdapter(
            ENRICHMENT,
            (
                NormalizedSourceRecord(
                    source=ENRICHMENT,
                    row_key="enrichment-457173",
                    iin_start="457173",
                    scheme="visa-enrichment",
                    type="credit-enrichment",
                    category="consumer",
                    country_alpha2="US",
                    country_alpha3="USA",
                    country_name="United States",
                    issuer_name="Enrichment Bank",
                    issuer_phone="+1-555-0100",
                    issuer_url="https://enrichment.example",
                    raw_payload={"BIN": "457173"},
                ),
            ),
        ),
        StaticAdapter(
            FALLBACK,
            (
                NormalizedSourceRecord(
                    source=FALLBACK,
                    row_key="fallback-457173",
                    iin_start="457173",
                    scheme="visa-fallback",
                    type="credit-fallback",
                    category="fallback",
                    issuer_name="Fallback Bank",
                    raw_payload={"bin": "457173"},
                ),
            ),
        ),
    )


def _bounded_primary_records() -> tuple[NormalizedSourceRecord, ...]:
    return (
        NormalizedSourceRecord(
            source=PRIMARY,
            row_key="primary-55555500",
            iin_start="55555500",
            iin_end="55555500",
            scheme="visa-primary-8",
            type="debit-primary-8",
            raw_payload={"iin_start": "55555500"},
        ),
        *(
            NormalizedSourceRecord(
                source=PRIMARY,
                row_key=f"primary-6{index:05d}",
                iin_start=f"6{index:05d}",
                scheme="visa",
                raw_payload={"iin_start": f"6{index:05d}"},
            )
            for index in range(BOUNDED_IMPORT_GROUP_COUNT)
        ),
    )


def _bounded_enrichment_records() -> tuple[NormalizedSourceRecord, ...]:
    return (
        NormalizedSourceRecord(
            source=ENRICHMENT,
            row_key="enrichment-555555",
            iin_start="555555",
            category="consumer",
            country_alpha3="USA",
            country_name="United States",
            raw_payload={"BIN": "555555"},
        ),
    )


async def _table_counts(store: BinDataStore) -> dict[str, int]:
    async with store.session() as session:
        return {
            "data_sources": await session.scalar(select(func.count()).select_from(DataSourceModel)) or 0,
            "bin_records": await session.scalar(select(func.count()).select_from(BinRecordModel)) or 0,
            "bin_record_sources": await session.scalar(select(func.count()).select_from(BinRecordSourceModel)) or 0,
        }


async def _single_record(store: BinDataStore, iin_start: str) -> BinRecordModel:
    async with store.session() as session:
        return (await session.scalars(select(BinRecordModel).where(BinRecordModel.iin_start == iin_start))).one()


async def _record_count(store: BinDataStore, iin_start: str) -> int:
    async with store.session() as session:
        return (
            await session.scalar(
                select(func.count()).select_from(BinRecordModel).where(BinRecordModel.iin_start == iin_start),
            )
            or 0
        )


async def _provenance_rows(store: BinDataStore, iin_start: str) -> tuple[tuple[str, str], ...]:
    async with store.session() as session:
        rows = await session.execute(
            select(DataSourceModel.source_id, BinRecordSourceModel.source_row_key)
            .join(BinRecordSourceModel, BinRecordSourceModel.data_source_id == DataSourceModel.id)
            .join(BinRecordModel, BinRecordModel.id == BinRecordSourceModel.bin_record_id)
            .where(BinRecordModel.iin_start == iin_start),
        )
        return tuple((source_id, row_key) for source_id, row_key in rows)


async def _assert_fixture_raw_payloads(store: BinDataStore) -> None:
    assert await _raw_payloads_by_source_row(store, "457173") == {
        ("binlist/data", "primary-457173"): {"iin_start": "457173"},
        ("venelinkochev/bin-list-data", "enrichment-457173"): {"BIN": "457173"},
        ("marlonlp/binlist-data", "fallback-457173"): {"bin": "457173"},
    }
    assert await _raw_payloads_by_source_row(store, "45717360") == {
        ("binlist/data", "primary-45717360"): {"iin_start": "45717360"},
        ("venelinkochev/bin-list-data", "enrichment-457173"): {"BIN": "457173"},
    }


async def _raw_payloads_by_source_row(
    store: BinDataStore,
    iin_start: str,
) -> dict[tuple[str, str], dict[str, str]]:
    async with store.session() as session:
        rows = await session.execute(
            select(DataSourceModel.source_id, BinRecordSourceModel.source_row_key, BinRecordSourceModel.raw_payload)
            .join(BinRecordSourceModel, BinRecordSourceModel.data_source_id == DataSourceModel.id)
            .join(BinRecordModel, BinRecordModel.id == BinRecordSourceModel.bin_record_id)
            .where(BinRecordModel.iin_start == iin_start),
        )
        return {(source_id, row_key): raw_payload for source_id, row_key, raw_payload in rows}
