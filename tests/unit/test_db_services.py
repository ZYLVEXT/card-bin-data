"""Unit coverage for card_bin_data Advanced Alchemy services."""
# ruff: noqa: S101, SLF001

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING, cast

import pytest
from advanced_alchemy.repository.memory import SQLAlchemyAsyncMockRepository

import card_bin_data.db.services as db_services
from card_bin_data.db.models import BinRecordModel, BinRecordSourceModel, DataSourceModel
from card_bin_data.db.services import (
    BinRecordService,
    BinRecordSourceService,
    DataSourceService,
    ImportedRecordsService,
)
from card_bin_data.merge import MergedSourceRecord
from card_bin_data.types import NormalizedSourceRecord, SourceMetadata

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Iterator, Sequence

    from sqlalchemy.ext.asyncio import AsyncSession


class MockDataSourceService(DataSourceService):
    """Data source service backed by Advanced Alchemy's in-memory repository."""

    class Repo(SQLAlchemyAsyncMockRepository[DataSourceModel]):
        """In-memory repository for data source unit tests."""

        model_type = DataSourceModel

    repository_type = Repo


class MockBinRecordService(BinRecordService):
    """BIN record service backed by Advanced Alchemy's in-memory repository."""

    class Repo(SQLAlchemyAsyncMockRepository[BinRecordModel]):
        """In-memory repository for BIN record unit tests."""

        model_type = BinRecordModel

    repository_type = Repo


class MockBinRecordSourceService(BinRecordSourceService):
    """BIN record source service backed by Advanced Alchemy's in-memory repository."""

    class Repo(SQLAlchemyAsyncMockRepository[BinRecordSourceModel]):
        """In-memory repository for provenance unit tests."""

        model_type = BinRecordSourceModel

    repository_type = Repo


class RecordingImportedRecordsService(ImportedRecordsService):
    """Imported records service that records provenance batches instead of writing."""

    def __init__(self) -> None:
        """Create a recording service without a real database session."""
        super().__init__(session=cast("AsyncSession", object()))
        self.bin_record_batches: list[list[dict[str, object]]] = []
        self.record_source_batches: list[list[dict[str, object]]] = []
        self._next_bin_record_id = 10

    async def _insert_bin_record_batch(self, rows: list[dict[str, object]]) -> dict[str, int]:
        """Record one would-be normalized record insert batch.

        Returns:
            Synthetic database ids keyed by inserted ``iin_start`` values.
        """
        self.bin_record_batches.append(rows)
        bin_record_ids = {str(row["iin_start"]): self._next_bin_record_id + index for index, row in enumerate(rows)}
        self._next_bin_record_id += len(rows)
        return bin_record_ids

    async def _insert_record_source_batch(self, rows: Sequence[dict[str, object]]) -> None:
        """Record one would-be provenance insert batch."""
        self.record_source_batches.append(list(rows))


class RecordingSession:
    """Small AsyncSession stand-in for insert statement unit tests."""

    def __init__(self, dialect_name: str) -> None:
        """Create a recording session with a named SQLAlchemy dialect."""
        self._bind = SimpleNamespace(dialect=SimpleNamespace(name=dialect_name))
        self.executions: list[tuple[object, object]] = []

    def get_bind(self) -> object:
        """Return the fake bind used by the service."""
        return self._bind

    async def execute(self, statement: object, rows: object) -> None:
        """Record statements and parameter rows instead of executing SQL."""
        self.executions.append((statement, rows))


@pytest.fixture
def clear_mock_repositories() -> Iterator[None]:
    """Keep Advanced Alchemy mock repository state isolated between tests."""
    yield
    MockDataSourceService.Repo.__database_clear__()


@pytest.mark.asyncio
async def test_model_services_wire_advanced_alchemy_mock_repositories(
    clear_mock_repositories: Iterator[None],
) -> None:
    """Smoke-test service/repository wiring without a real database."""
    del clear_mock_repositories
    session = cast("AsyncSession", object())
    data_sources = MockDataSourceService(session=session)
    bin_records = MockBinRecordService(session=session)
    record_sources = MockBinRecordSourceService(session=session)

    data_source = await data_sources.create(
        DataSourceModel(
            id=1,
            source_id="binlist/data",
            display_name="binlist/data",
            upstream_url="https://github.com/binlist/data.git",
        ),
        auto_refresh=False,
    )
    bin_record = await bin_records.create(
        BinRecordModel(id=2, iin_start="45717360", scheme="visa", issuer_name="Example Bank"),
        auto_refresh=False,
    )
    record_source = await record_sources.create(
        BinRecordSourceModel(
            id=3,
            bin_record_id=bin_record.id,
            data_source_id=data_source.id,
            source_row_key="ranges.csv:45717360",
            imported_at=datetime(2026, 6, 19, tzinfo=UTC),
            raw_payload={"iin_start": "45717360"},
        ),
        auto_refresh=False,
    )

    assert await data_sources.get(1) is data_source
    assert await bin_records.get(2) is bin_record
    assert await record_sources.get(3) is record_source
    assert await data_sources.count() == 1
    assert await bin_records.count() == 1
    assert await record_sources.count() == 1


def test_imported_records_service_maps_normalized_record_to_insert_values() -> None:
    """Composite import service preserves normalized fields at the persistence boundary."""
    source_record = NormalizedSourceRecord(
        source=SourceMetadata("binlist/data", "binlist/data", "https://github.com/binlist/data.git"),
        row_key="primary-45717360",
        iin_start="45717360",
        iin_end="45717399",
        number_length=16,
        luhn=True,
        scheme="visa",
        product_brand="classic",
        type="debit",
        category="consumer",
        prepaid=False,
        country_alpha2="US",
        country_alpha3="USA",
        country_name="United States",
        issuer_name="Example Bank",
        issuer_phone="+1-555-0100",
        issuer_url="https://issuer.example",
        issuer_city="New York",
    )

    values = ImportedRecordsService._bin_record_values(source_record)

    assert values["iin_start"] == source_record.iin_start
    assert values["iin_end"] == source_record.iin_end
    assert values["range_start_8"] == "45717360"
    assert values["range_end_8"] == "45717399"
    assert values["number_length"] == source_record.number_length
    assert values["luhn"] == source_record.luhn
    assert values["scheme"] == source_record.scheme
    assert values["product_brand"] == source_record.product_brand
    assert values["type"] == source_record.type
    assert values["category"] == source_record.category
    assert values["prepaid"] == source_record.prepaid
    assert values["country_alpha2"] == source_record.country_alpha2
    assert values["country_alpha3"] == source_record.country_alpha3
    assert values["country_name"] == source_record.country_name
    assert values["issuer_name"] == source_record.issuer_name
    assert values["issuer_phone"] == source_record.issuer_phone
    assert values["issuer_url"] == source_record.issuer_url
    assert values["issuer_city"] == source_record.issuer_city


def test_imported_records_service_omits_range_boundaries_without_iin_end() -> None:
    """Non-range rows do not gain synthetic fixed-width boundaries."""
    source_record = NormalizedSourceRecord(
        source=SourceMetadata("binlist/data", "binlist/data", "https://github.com/binlist/data.git"),
        row_key="primary-000123",
        iin_start="000123",
    )

    values = ImportedRecordsService._bin_record_values(source_record)

    assert values["iin_end"] is None
    assert values["range_start_8"] is None
    assert values["range_end_8"] is None


def test_imported_records_service_maps_six_digit_range_to_fixed_width_boundaries() -> None:
    """Six-digit range boundaries expand to the min and max 8-digit members."""
    source_record = NormalizedSourceRecord(
        source=SourceMetadata("binlist/data", "binlist/data", "https://github.com/binlist/data.git"),
        row_key="primary-400000",
        iin_start="400000",
        iin_end="400999",
    )

    values = ImportedRecordsService._bin_record_values(source_record)

    assert values["range_start_8"] == "40000000"
    assert values["range_end_8"] == "40099999"


@pytest.mark.asyncio
async def test_imported_records_service_streaming_provenance_values_preserve_payload() -> None:
    """Streaming import maps merged sources to provenance insert rows."""
    service = RecordingImportedRecordsService()
    source_record = NormalizedSourceRecord(
        source=SourceMetadata("binlist/data", "binlist/data", "https://github.com/binlist/data.git"),
        row_key="primary-45717360",
        iin_start="45717360",
        raw_payload={"iin_start": "45717360"},
    )
    imported_at = datetime(2026, 6, 20, tzinfo=UTC)

    await service._insert_merged_record_batch(
        [MergedSourceRecord(record=source_record, sources=(source_record,))],
        {"binlist/data": 20},
        imported_at,
    )

    assert service.record_source_batches == [
        [
            {
                "bin_record_id": 10,
                "data_source_id": 20,
                "source_row_key": "primary-45717360",
                "imported_at": imported_at,
                "raw_payload": {"iin_start": "45717360"},
            },
        ],
    ]


@pytest.mark.asyncio
async def test_imported_records_service_batches_materialized_provenance_rows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Provenance rows are inserted in bounded chunks."""
    service = RecordingImportedRecordsService()
    rows: list[dict[str, object]] = [{"source_row_key": str(index)} for index in range(3)]

    monkeypatch.setattr(db_services, "INSERT_BATCH_SIZE", 2)

    await service._insert_record_source_rows(rows)

    assert service.record_source_batches == [
        [{"source_row_key": "0"}, {"source_row_key": "1"}],
        [{"source_row_key": "2"}],
    ]


@pytest.mark.asyncio
async def test_imported_records_service_splits_mapping_and_json_text_payload_rows() -> None:
    """Staged JSON text rows use a dedicated insert while mapping rows keep the normal insert."""
    session = RecordingSession(dialect_name="postgresql")
    service = ImportedRecordsService(session=cast("AsyncSession", session))
    mapping_row: dict[str, object] = {"source_row_key": "mapping", "raw_payload": {"iin_start": "457173"}}
    json_text_row: dict[str, object] = {"source_row_key": "json-text", "raw_payload_json": '{"iin_start":"45717360"}'}

    await service._insert_record_source_batch([mapping_row, json_text_row])

    first_execution, second_execution = session.executions
    assert first_execution[1] == [mapping_row]
    assert second_execution[1] == [json_text_row]


@pytest.mark.asyncio
async def test_imported_records_service_inserts_mapping_payload_rows_without_json_text_statement() -> None:
    """Mapping-only provenance rows use the default JSON bind path."""
    session = RecordingSession(dialect_name="sqlite")
    service = ImportedRecordsService(session=cast("AsyncSession", session))
    mapping_row: dict[str, object] = {"source_row_key": "mapping", "raw_payload": {"iin_start": "457173"}}

    await service._insert_record_source_batch([mapping_row])

    (execution,) = session.executions
    assert execution[1] == [mapping_row]


@pytest.mark.asyncio
async def test_imported_records_service_streams_batched_bin_records(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Streaming normalized rows are inserted in bounded chunks."""
    service = RecordingImportedRecordsService()
    source = SourceMetadata("binlist/data", "binlist/data", "https://github.com/binlist/data.git")

    async def records() -> AsyncIterator[MergedSourceRecord]:
        for index in range(3):
            await asyncio.sleep(0)
            source_record = NormalizedSourceRecord(
                source=source,
                row_key=f"primary-{index}",
                iin_start=f"22222{index}",
            )
            yield MergedSourceRecord(record=source_record, sources=())

    monkeypatch.setattr(db_services, "INSERT_BATCH_SIZE", 2)

    await service._insert_streamed_records(records(), {}, datetime(2026, 6, 20, tzinfo=UTC))

    assert [[row["iin_start"] for row in batch] for batch in service.bin_record_batches] == [
        ["222220", "222221"],
        ["222222"],
    ]


@pytest.mark.asyncio
async def test_imported_records_service_streams_merged_records_in_bounded_batches(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Single-pass import streams normalized records and provenance in bounded batches."""
    service = RecordingImportedRecordsService()
    source = SourceMetadata("binlist/data", "binlist/data", "https://github.com/binlist/data.git")
    imported_at = datetime(2026, 6, 20, tzinfo=UTC)

    async def records() -> AsyncIterator[MergedSourceRecord]:
        for index in range(3):
            await asyncio.sleep(0)
            source_record = NormalizedSourceRecord(
                source=source,
                row_key=f"needed-{index}",
                iin_start=f"22222{index}",
                raw_payload={"iin_start": f"22222{index}"},
            )
            yield MergedSourceRecord(record=source_record, sources=(source_record,))

    monkeypatch.setattr(db_services, "INSERT_BATCH_SIZE", 2)

    await service._insert_streamed_records(records(), {"binlist/data": 20}, imported_at)

    assert [[row["iin_start"] for row in batch] for batch in service.bin_record_batches] == [
        ["222220", "222221"],
        ["222222"],
    ]
    assert service.record_source_batches == [
        [
            {
                "bin_record_id": 10,
                "data_source_id": 20,
                "source_row_key": "needed-0",
                "imported_at": imported_at,
                "raw_payload": {"iin_start": "222220"},
            },
            {
                "bin_record_id": 11,
                "data_source_id": 20,
                "source_row_key": "needed-1",
                "imported_at": imported_at,
                "raw_payload": {"iin_start": "222221"},
            },
        ],
        [
            {
                "bin_record_id": 12,
                "data_source_id": 20,
                "source_row_key": "needed-2",
                "imported_at": imported_at,
                "raw_payload": {"iin_start": "222222"},
            },
        ],
    ]


@pytest.mark.asyncio
async def test_imported_records_service_streams_empty_record_sequence() -> None:
    """An empty single-pass stream writes no normalized or provenance batches."""
    service = RecordingImportedRecordsService()

    async def records() -> AsyncIterator[MergedSourceRecord]:
        await asyncio.sleep(0)
        if False:
            yield MergedSourceRecord(
                record=NormalizedSourceRecord(
                    source=SourceMetadata("binlist/data", "binlist/data", "https://github.com/binlist/data.git"),
                    row_key="unused",
                    iin_start="000000",
                ),
                sources=(),
            )

    await service._insert_streamed_records(records(), {}, datetime(2026, 6, 20, tzinfo=UTC))

    assert service.bin_record_batches == []
    assert service.record_source_batches == []


def test_data_source_values_serializes_local_path_and_preserves_none() -> None:
    """Data source mapping converts a local Path to str and keeps absent fields as None."""
    with_path = ImportedRecordsService._data_source_values(
        SourceMetadata(
            "binlist/data",
            "binlist/data",
            "https://github.com/binlist/data.git",
            local_path=Path("/data/binlist/ranges.csv"),
        ),
    )
    assert with_path["local_path"] == "/data/binlist/ranges.csv"
    assert isinstance(with_path["local_path"], str)
    assert with_path["license"] is None

    without_path = ImportedRecordsService._data_source_values(
        SourceMetadata("marlonlp/binlist-data", "marlonlp/binlist-data", "https://example", license="CC BY 4.0"),
    )
    assert without_path["local_path"] is None
    assert without_path["license"] == "CC BY 4.0"
