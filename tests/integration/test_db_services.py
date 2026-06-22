"""Integration coverage for Advanced Alchemy model services on every supported backend."""
# ruff: noqa: S101

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import TYPE_CHECKING, cast

import pytest

from card_bin_data.db import (
    BinRecordModel,
    BinRecordService,
    BinRecordSourceModel,
    BinRecordSourceService,
    DataSourceModel,
    DataSourceService,
    ImportedRecordsService,
)
from card_bin_data.db.services import ImportReplacement

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from sqlalchemy.ext.asyncio import AsyncSession

    from card_bin_data import BinDataStore
    from card_bin_data.merge import MergedSourceRecord


@pytest.fixture
async def session(store: BinDataStore) -> AsyncIterator[AsyncSession]:
    """Yield an isolated session with the card_bin_data schema installed, once per backend."""
    await store.init()
    async with store.session() as database_session:
        yield database_session


@pytest.mark.asyncio(loop_scope="session")
async def test_composite_import_service_can_use_caller_session(session: AsyncSession) -> None:
    """The composite import service is constructed around the caller's session boundary."""
    service = ImportedRecordsService(session=session)

    async def records() -> AsyncIterator[MergedSourceRecord]:
        await asyncio.sleep(0)
        if False:
            yield cast("MergedSourceRecord", object())

    await service.replace_all(ImportReplacement(records=records(), source_metadata={}))


@pytest.mark.asyncio(loop_scope="session")
async def test_services_round_trip_with_caller_supplied_session(session: AsyncSession) -> None:
    """Each service can create and retrieve rows using the caller's AsyncSession."""
    data_sources = DataSourceService(session=session)
    bin_records = BinRecordService(session=session)
    record_sources = BinRecordSourceService(session=session)

    data_source = await data_sources.create(
        DataSourceModel(
            source_id="binlist/data",
            display_name="binlist/data",
            upstream_url="https://github.com/binlist/data.git",
            local_path="datasets/binlist_data",
        ),
        auto_refresh=False,
    )
    bin_record = await bin_records.create(
        BinRecordModel(
            iin_start="45717360",
            iin_end="45717369",
            scheme="visa",
            type="debit",
            issuer_name="Example Bank",
        ),
        auto_refresh=False,
    )
    await session.flush()

    record_source = await record_sources.create(
        BinRecordSourceModel(
            bin_record_id=bin_record.id,
            data_source_id=data_source.id,
            source_row_key="ranges.csv:45717360",
            imported_at=datetime(2026, 6, 19, tzinfo=UTC),
            raw_payload={"iin_start": "45717360", "scheme": "visa"},
        ),
        auto_refresh=False,
    )
    await session.flush()

    assert data_source.id is not None
    assert bin_record.id is not None
    assert record_source.id is not None
    assert record_source.bin_record_id == bin_record.id
    assert record_source.data_source_id == data_source.id

    found_data_source = await data_sources.get(data_source.id)
    found_bin_record = await bin_records.get(bin_record.id)
    found_record_source = await record_sources.get(record_source.id)

    assert found_data_source.source_id == "binlist/data"
    assert found_bin_record.iin_start == "45717360"
    assert found_record_source.source_row_key == "ranges.csv:45717360"
