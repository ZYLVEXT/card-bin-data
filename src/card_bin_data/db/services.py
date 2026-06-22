"""Advanced Alchemy repository services for card_bin_data persistence models."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from itertools import batched
from typing import TYPE_CHECKING, Any, cast

from advanced_alchemy.repository import SQLAlchemyAsyncRepository
from advanced_alchemy.service import SQLAlchemyAsyncRepositoryService
from sqlalchemy import JSON, bindparam, delete, desc, func, insert, select
from sqlalchemy.orm import selectinload
from sqlalchemy.sql.expression import cast as sql_cast

from .models import BinRecordModel, BinRecordSourceModel, DataSourceModel

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Iterable, Mapping, Sequence

    from sqlalchemy import Select
    from sqlalchemy.ext.asyncio import AsyncSession
    from sqlalchemy.sql.dml import Insert
    from sqlalchemy.sql.elements import ColumnElement

    from card_bin_data.merge import MergedSourceRecord
    from card_bin_data.types import LookupQuery, NormalizedSourceRecord, SourceMetadata

SIX_DIGIT_PREFIX_LENGTH = 6
EIGHT_DIGIT_PREFIX_LENGTH = 8
INSERT_BATCH_SIZE = 1_000
RECORD_SOURCE_INSERT_FIELDS = (
    "bin_record_id",
    "data_source_id",
    "source_row_key",
    "imported_at",
)

type InsertValues = dict[str, object]


@dataclass(frozen=True, slots=True)
class ImportReplacement:
    """Single-pass merged import stream plus source metadata."""

    records: AsyncIterator[MergedSourceRecord]
    source_metadata: Mapping[str, SourceMetadata]
    store_raw_payload: bool = True


class DataSourceService(SQLAlchemyAsyncRepositoryService[DataSourceModel]):
    """Repository service for upstream data source metadata."""

    class Repo(SQLAlchemyAsyncRepository[DataSourceModel]):
        """Repository for upstream data source metadata."""

        model_type = DataSourceModel

    repository_type = Repo


class BinRecordService(SQLAlchemyAsyncRepositoryService[BinRecordModel]):
    """Repository service for normalized BIN/IIN records."""

    class Repo(SQLAlchemyAsyncRepository[BinRecordModel]):
        """Repository for normalized BIN/IIN records."""

        model_type = BinRecordModel

    repository_type = Repo

    async def lookup_record(self, query: LookupQuery) -> BinRecordModel | None:
        """Return the best matching normalized record for a safe lookup query."""
        exact_8_candidate = next(
            (candidate for candidate in query.candidates if len(candidate) == EIGHT_DIGIT_PREFIX_LENGTH),
            None,
        )
        if exact_8_candidate is not None:
            exact_8 = await self._first_record(self._exact_prefix_statement(exact_8_candidate))
            if exact_8 is not None:
                return exact_8

            range_match = await self._first_record(self._range_statement(exact_8_candidate))
            if range_match is not None:
                return range_match

        exact_6_candidate = next(
            (candidate for candidate in query.candidates if len(candidate) == SIX_DIGIT_PREFIX_LENGTH),
            None,
        )
        if exact_6_candidate is None:
            return None

        return await self._first_record(self._exact_prefix_statement(exact_6_candidate))

    @classmethod
    def _exact_prefix_statement(cls, prefix: str) -> Select[tuple[BinRecordModel]]:
        return (
            cls._base_record_statement().where(BinRecordModel.iin_start == prefix).order_by(BinRecordModel.id).limit(1)
        )

    @classmethod
    def _range_statement(cls, prefix: str) -> Select[tuple[BinRecordModel]]:
        return (
            cls._base_record_statement()
            .where(
                BinRecordModel.range_start_8.is_not(None),
                BinRecordModel.range_start_8 <= prefix,
                BinRecordModel.range_end_8 >= prefix,
            )
            .order_by(desc(func.length(BinRecordModel.iin_start)), desc(BinRecordModel.iin_start), BinRecordModel.id)
            .limit(1)
        )  # fmt: skip

    @staticmethod
    def _base_record_statement() -> Select[tuple[BinRecordModel]]:
        return select(BinRecordModel).options(
            selectinload(BinRecordModel.sources).selectinload(BinRecordSourceModel.data_source),
        )

    async def _first_record(self, statement: Select[tuple[BinRecordModel]]) -> BinRecordModel | None:
        return (await self.repository.session.scalars(statement)).one_or_none()


class BinRecordSourceService(SQLAlchemyAsyncRepositoryService[BinRecordSourceModel]):
    """Repository service for BIN/IIN source attribution rows."""

    class Repo(SQLAlchemyAsyncRepository[BinRecordSourceModel]):
        """Repository for BIN/IIN source attribution rows."""

        model_type = BinRecordSourceModel

    repository_type = Repo


class ImportedRecordsService:
    """Composite service for transactional replacement of imported BIN/IIN data."""

    __slots__ = ("_session",)

    def __init__(self, session: AsyncSession) -> None:
        """Create a composite import service bound to the caller-owned session."""
        self._session = session

    async def replace_all(self, records: ImportReplacement) -> None:
        """Replace all imported records and provenance within the caller's transaction."""
        await self._session.execute(delete(BinRecordSourceModel))
        await self._session.execute(delete(BinRecordModel))
        await self._session.execute(delete(DataSourceModel))

        imported_at = datetime.now(tz=UTC)
        data_source_ids = await self._insert_data_source_metadata(records.source_metadata)
        await self._insert_streamed_records(
            records.records,
            data_source_ids,
            imported_at,
            store_raw_payload=records.store_raw_payload,
        )
        await self._session.flush()

    async def _insert_data_source_metadata(
        self,
        metadata_by_id: Mapping[str, SourceMetadata],
    ) -> dict[str, int]:
        if not metadata_by_id:
            return {}

        rows = [self._data_source_values(metadata_by_id[source_id]) for source_id in sorted(metadata_by_id)]
        result = await self._session.execute(
            insert(DataSourceModel).returning(DataSourceModel.source_id, DataSourceModel.id),
            rows,
        )
        return dict(result.tuples().all())

    async def _insert_bin_record_batch(self, rows: list[InsertValues]) -> dict[str, int]:
        result = await self._session.execute(
            insert(BinRecordModel).returning(BinRecordModel.iin_start, BinRecordModel.id),
            rows,
        )
        return dict(result.tuples().all())

    async def _insert_streamed_records(
        self,
        records: AsyncIterator[MergedSourceRecord],
        data_source_ids: dict[str, int],
        imported_at: datetime,
        *,
        store_raw_payload: bool = True,
    ) -> None:
        batch: list[MergedSourceRecord] = []
        async for record in records:
            batch.append(record)
            if len(batch) == INSERT_BATCH_SIZE:
                await self._insert_merged_record_batch(
                    batch,
                    data_source_ids,
                    imported_at,
                    store_raw_payload=store_raw_payload,
                )
                batch = []
        if batch:
            await self._insert_merged_record_batch(
                batch,
                data_source_ids,
                imported_at,
                store_raw_payload=store_raw_payload,
            )

    async def _insert_merged_record_batch(
        self,
        records: list[MergedSourceRecord],
        data_source_ids: dict[str, int],
        imported_at: datetime,
        *,
        store_raw_payload: bool = True,
    ) -> None:
        bin_record_ids = await self._insert_bin_record_batch(
            [self._bin_record_values(merged_record.record) for merged_record in records],
        )
        rows = (
            self._record_source_value(
                bin_record_ids[merged_record.record.iin_start],
                data_source_ids[source_record.source.source_id],
                source_record,
                imported_at,
                store_raw_payload=store_raw_payload,
            )
            for merged_record in records
            for source_record in merged_record.sources
        )
        await self._insert_record_source_rows(rows)

    async def _insert_record_source_rows(self, rows: Iterable[InsertValues]) -> None:
        for batch in batched(rows, INSERT_BATCH_SIZE):
            await self._insert_record_source_batch(batch)

    async def _insert_record_source_batch(self, rows: Sequence[InsertValues]) -> None:
        json_text_rows = [row for row in rows if "raw_payload_json" in row]
        mapping_rows = [row for row in rows if "raw_payload_json" not in row]
        if mapping_rows:
            await self._session.execute(insert(BinRecordSourceModel), mapping_rows)
        if json_text_rows:
            await self._session.execute(
                _record_source_json_text_insert(self._session.get_bind().dialect.name),
                cast("list[dict[str, Any]]", json_text_rows),
            )

    @staticmethod
    def _data_source_values(metadata: SourceMetadata) -> InsertValues:
        return {
            "source_id": metadata.source_id,
            "display_name": metadata.display_name,
            "upstream_url": metadata.upstream_url,
            "license": metadata.license,
            "local_path": str(metadata.local_path) if metadata.local_path is not None else None,
        }

    @staticmethod
    def _bin_record_values(record: NormalizedSourceRecord) -> InsertValues:
        range_start_8, range_end_8 = _range_boundaries_8(record)
        return {
            "iin_start": record.iin_start,
            "iin_end": record.iin_end,
            "range_start_8": range_start_8,
            "range_end_8": range_end_8,
            "number_length": record.number_length,
            "luhn": record.luhn,
            "scheme": record.scheme,
            "product_brand": record.product_brand,
            "type": record.type,
            "category": record.category,
            "prepaid": record.prepaid,
            "country_alpha2": record.country_alpha2,
            "country_alpha3": record.country_alpha3,
            "country_name": record.country_name,
            "issuer_name": record.issuer_name,
            "issuer_phone": record.issuer_phone,
            "issuer_url": record.issuer_url,
            "issuer_city": record.issuer_city,
        }

    @staticmethod
    def _record_source_value(
        bin_record_id: int,
        data_source_id: int,
        source_record: NormalizedSourceRecord,
        imported_at: datetime,
        *,
        store_raw_payload: bool = True,
    ) -> InsertValues:
        if store_raw_payload:
            raw_payload_json = getattr(source_record, "raw_payload_json", None)
            raw_payload_key = (
                {"raw_payload_json": raw_payload_json}
                if isinstance(raw_payload_json, str)
                else {"raw_payload": dict(source_record.raw_payload)}
            )
        else:
            raw_payload_key = {"raw_payload": {}}
        return {
            "bin_record_id": bin_record_id,
            "data_source_id": data_source_id,
            "source_row_key": source_record.row_key,
            "imported_at": imported_at,
            **raw_payload_key,
        }


def _range_boundaries_8(record: NormalizedSourceRecord) -> tuple[str | None, str | None]:
    if record.iin_end is None:
        return None, None
    return record.iin_start.ljust(EIGHT_DIGIT_PREFIX_LENGTH, "0"), record.iin_end.ljust(EIGHT_DIGIT_PREFIX_LENGTH, "9")


def _record_source_json_text_insert(dialect_name: str) -> Insert:
    values: dict[str, ColumnElement[object]] = {
        field_name: bindparam(field_name) for field_name in RECORD_SOURCE_INSERT_FIELDS
    }
    values["raw_payload"] = _json_text_expression(dialect_name)
    return insert(BinRecordSourceModel).values(values)


def _json_text_expression(dialect_name: str) -> ColumnElement[object]:
    raw_payload_json = bindparam("raw_payload_json")
    if dialect_name == "sqlite":
        return func.json(raw_payload_json)
    return sql_cast(raw_payload_json, JSON)


__all__ = [
    "BinRecordService",
    "BinRecordSourceService",
    "DataSourceService",
    "ImportedRecordsService",
]
