"""Import pipeline for source adapters."""

from __future__ import annotations

import asyncio
import logging
import os
import sqlite3
import tempfile
from dataclasses import dataclass
from json import dumps
from pathlib import Path
from typing import TYPE_CHECKING, Self

from .db.services import ImportedRecordsService, ImportReplacement
from .merge import merge_sorted_source_records
from .types import NormalizedSourceRecord

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Mapping, Sequence

    from sqlalchemy.ext.asyncio import AsyncSession

    from .merge import MergedSourceRecord
    from .sources import SourceAdapter
    from .types import SourceMetadata


STAGING_INSERT_BATCH_SIZE = 1_000
STAGING_FETCH_BATCH_SIZE = 1_000
_STAGING_INSERT_SQL = (
    "INSERT INTO source_records (ordinal, source_id, row_key, iin_start, iin_end, number_length, luhn, scheme, "
    "product_brand, type, category, prepaid, country_alpha2, country_alpha3, country_name, issuer_name, "
    "issuer_phone, issuer_url, issuer_city, raw_payload) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, "
    "?, ?, ?, ?)"
)
_STAGING_SELECT_SQL = (
    "SELECT ordinal, source_id, row_key, iin_start, iin_end, number_length, luhn, scheme, product_brand, type, "
    "category, prepaid, country_alpha2, country_alpha3, country_name, issuer_name, issuer_phone, issuer_url, "
    "issuer_city, raw_payload FROM source_records ORDER BY iin_start, ordinal"
)


@dataclass(frozen=True, slots=True)
class ImportResult:
    """Counts from a completed source import."""

    source_record_count: int
    normalized_record_count: int
    provenance_record_count: int


@dataclass(frozen=True, slots=True)
class _StagedSourceRecord(NormalizedSourceRecord):
    """Source record restored from staging with raw payload kept as JSON text."""

    raw_payload_json: str = ""


async def import_sources(
    session: AsyncSession,
    adapters: Sequence[SourceAdapter],
    *,
    store_raw_payload: bool = True,
) -> ImportResult:
    """Import source adapters into the current transactional session.

    Source adapters are parsed once into a private on-disk SQLite staging table.
    The sorted staging stream lets merge keep only the current group and the
    active 6-digit prefix window resident before database rows are inserted in
    bounded batches.

    Returns:
        Import counts for source, normalized, and provenance rows.
    """
    logger.info("card_bin_data import starting: %d adapter(s)", len(adapters))
    stage = await _SourceRecordStage.create()
    try:
        counters = _ImportCounters(source_record_count=await _stage_source_records(stage, adapters))
        merged_records = _count_merged_records(merge_sorted_source_records(stage.iter_records()), counters)
        await ImportedRecordsService(session=session).replace_all(
            ImportReplacement(
                records=merged_records,
                source_metadata=stage.source_metadata_by_id,
                store_raw_payload=store_raw_payload,
            ),
        )
        result = _import_result(counters)
        logger.info(
            "card_bin_data import complete: sources=%d normalized=%d provenance=%d",
            result.source_record_count,
            result.normalized_record_count,
            result.provenance_record_count,
        )
        return result
    finally:
        await stage.close()


@dataclass(slots=True)
class _ImportCounters:
    source_record_count: int
    normalized_record_count: int = 0
    provenance_record_count: int = 0


class _SourceRecordStage:
    """Private disk-backed sort for one import run."""

    __slots__ = ("_connection", "_next_ordinal", "_path", "_source_metadata_by_id")

    def __init__(self, path: Path, connection: sqlite3.Connection) -> None:
        self._path = path
        self._connection = connection
        self._next_ordinal = 0
        self._source_metadata_by_id: dict[str, SourceMetadata] = {}

    @classmethod
    async def create(cls) -> Self:
        path = Path(await asyncio.to_thread(_make_temporary_stage_path))
        connection = await asyncio.to_thread(sqlite3.connect, path, check_same_thread=False)
        connection.row_factory = sqlite3.Row
        stage = cls(path, connection)
        await stage._initialize()
        return stage

    @property
    def source_metadata_by_id(self) -> Mapping[str, SourceMetadata]:
        return self._source_metadata_by_id

    async def insert_records(self, records: list[NormalizedSourceRecord]) -> None:
        rows = []
        for record in records:
            self._source_metadata_by_id.setdefault(record.source.source_id, record.source)
            rows.append(self._record_values(record))
        await asyncio.to_thread(self._connection.executemany, _STAGING_INSERT_SQL, rows)
        await asyncio.to_thread(self._connection.commit)

    async def iter_records(self) -> AsyncIterator[NormalizedSourceRecord]:
        cursor = await asyncio.to_thread(self._connection.execute, _STAGING_SELECT_SQL)
        try:
            while rows := await asyncio.to_thread(cursor.fetchmany, STAGING_FETCH_BATCH_SIZE):
                for row in rows:
                    yield self._record_from_row(row)
        finally:
            await asyncio.to_thread(cursor.close)

    async def close(self) -> None:
        await asyncio.to_thread(self._connection.close)
        await asyncio.to_thread(self._path.unlink, missing_ok=True)

    async def _initialize(self) -> None:
        await asyncio.to_thread(
            self._connection.executescript,
            """
            PRAGMA temp_store = FILE;
            CREATE TABLE source_records (
                ordinal INTEGER PRIMARY KEY,
                source_id TEXT NOT NULL,
                row_key TEXT NOT NULL,
                iin_start TEXT NOT NULL,
                iin_end TEXT,
                number_length INTEGER,
                luhn INTEGER,
                scheme TEXT,
                product_brand TEXT,
                type TEXT,
                category TEXT,
                prepaid INTEGER,
                country_alpha2 TEXT,
                country_alpha3 TEXT,
                country_name TEXT,
                issuer_name TEXT,
                issuer_phone TEXT,
                issuer_url TEXT,
                issuer_city TEXT,
                raw_payload TEXT NOT NULL
            );
            CREATE INDEX ix_source_records_iin_start_ordinal ON source_records (iin_start, ordinal);
            """,
        )
        await asyncio.to_thread(self._connection.commit)

    def _record_values(self, record: NormalizedSourceRecord) -> tuple[object, ...]:
        ordinal = self._next_ordinal
        self._next_ordinal += 1
        return (
            ordinal,
            record.source.source_id,
            record.row_key,
            record.iin_start,
            record.iin_end,
            record.number_length,
            None if record.luhn is None else int(record.luhn),
            record.scheme,
            record.product_brand,
            record.type,
            record.category,
            None if record.prepaid is None else int(record.prepaid),
            record.country_alpha2,
            record.country_alpha3,
            record.country_name,
            record.issuer_name,
            record.issuer_phone,
            record.issuer_url,
            record.issuer_city,
            dumps(dict(record.raw_payload), separators=(",", ":")),
        )

    def _record_from_row(self, row: sqlite3.Row) -> NormalizedSourceRecord:
        source_id = row["source_id"]
        return _StagedSourceRecord(
            source=self._source_metadata_by_id[source_id],
            row_key=row["row_key"],
            iin_start=row["iin_start"],
            iin_end=row["iin_end"],
            number_length=row["number_length"],
            luhn=None if row["luhn"] is None else bool(row["luhn"]),
            scheme=row["scheme"],
            product_brand=row["product_brand"],
            type=row["type"],
            category=row["category"],
            prepaid=None if row["prepaid"] is None else bool(row["prepaid"]),
            country_alpha2=row["country_alpha2"],
            country_alpha3=row["country_alpha3"],
            country_name=row["country_name"],
            issuer_name=row["issuer_name"],
            issuer_phone=row["issuer_phone"],
            issuer_url=row["issuer_url"],
            issuer_city=row["issuer_city"],
            raw_payload_json=row["raw_payload"],
        )


async def _stage_source_records(stage: _SourceRecordStage, adapters: Sequence[SourceAdapter]) -> int:
    batch: list[NormalizedSourceRecord] = []
    source_record_count = 0
    for adapter in adapters:
        adapter_record_count = 0
        async for record in adapter.iter_records():
            batch.append(record)
            adapter_record_count += 1
            if len(batch) == STAGING_INSERT_BATCH_SIZE:
                await stage.insert_records(batch)
                batch = []
        logger.debug("source %s: %d record(s)", adapter.metadata.source_id, adapter_record_count)
        source_record_count += adapter_record_count
    if batch:
        await stage.insert_records(batch)
    return source_record_count


async def _count_merged_records(
    records: AsyncIterator[MergedSourceRecord],
    counters: _ImportCounters,
) -> AsyncIterator[MergedSourceRecord]:
    async for record in records:
        counters.normalized_record_count += 1
        counters.provenance_record_count += len(record.sources)
        yield record


def _make_temporary_stage_path() -> str:
    descriptor, path = tempfile.mkstemp(prefix="card_bin_data-import-", suffix=".sqlite3")
    os.close(descriptor)
    return path


def _import_result(counters: _ImportCounters) -> ImportResult:
    return ImportResult(
        source_record_count=counters.source_record_count,
        normalized_record_count=counters.normalized_record_count,
        provenance_record_count=counters.provenance_record_count,
    )
