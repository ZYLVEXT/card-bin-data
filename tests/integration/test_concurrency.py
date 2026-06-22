"""Integration coverage for async concurrency behavior on every supported backend."""
# ruff: noqa: S101

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import delete, func, select

from card_bin_data import BinData
from card_bin_data.db import BinRecordModel, BinRecordSourceModel, DataSourceModel
from card_bin_data.db.services import ImportedRecordsService, ImportReplacement
from card_bin_data.types import LookupStatus, NormalizedSourceRecord, SourceMetadata

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from card_bin_data import BinDataStore
    from card_bin_data.sources import SourceAdapter


PRIMARY = SourceMetadata("binlist/data", "binlist/data", "https://github.com/binlist/data.git")
CONCURRENT_LOOKUP_COUNT = 60
EXPECTED_FOUND_LOOKUP_COUNT = CONCURRENT_LOOKUP_COUNT // 2
EXPECTED_NOT_FOUND_LOOKUP_COUNT = CONCURRENT_LOOKUP_COUNT // 2
CONCURRENT_IMPORT_COUNT = 4


@dataclass(frozen=True, slots=True)
class StaticAdapter:
    """Small source adapter for concurrency tests."""

    metadata: SourceMetadata
    records: tuple[NormalizedSourceRecord, ...]

    async def iter_records(self) -> AsyncIterator[NormalizedSourceRecord]:
        """Yield configured normalized source rows."""
        for record in self.records:
            yield record


@dataclass(slots=True)
class BlockingAdapter:
    """Adapter that keeps an update open until the test releases it."""

    metadata: SourceMetadata
    records: tuple[NormalizedSourceRecord, ...]
    started: asyncio.Event
    release: asyncio.Event

    async def iter_records(self) -> AsyncIterator[NormalizedSourceRecord]:
        """Signal that collection started, then wait before yielding rows.

        Yields:
            Configured normalized source rows after release.
        """
        self.started.set()
        await self.release.wait()
        for record in self.records:
            yield record


@pytest.mark.asyncio(loop_scope="session")
async def test_many_concurrent_lookups_share_one_client_safely(store: BinDataStore) -> None:
    """One BinData instance supports many concurrent read-only lookups."""
    client = BinData(store=store)
    await store.init()
    await store.import_sources(_old_adapters())

    results: list[LookupStatus] = []

    async def lookup_many(value: str) -> None:
        result = await client.lookup(value)
        results.append(result.status)

    async with asyncio.TaskGroup() as task_group:
        for index in range(CONCURRENT_LOOKUP_COUNT):
            task_group.create_task(lookup_many("45717360" if index % 2 == 0 else "000000"))

    assert results.count(LookupStatus.FOUND) == EXPECTED_FOUND_LOOKUP_COUNT
    assert results.count(LookupStatus.NOT_FOUND) == EXPECTED_NOT_FOUND_LOOKUP_COUNT


@pytest.mark.asyncio(loop_scope="session")
async def test_lookup_during_update_sees_complete_old_then_new_dataset(store: BinDataStore) -> None:
    """Lookups during an in-flight update never observe partial replacement data."""
    client = BinData(store=store)
    started = asyncio.Event()
    release = asyncio.Event()
    try:
        await store.init()
        await store.import_sources(_old_adapters())

        update_task = asyncio.create_task(
            store.import_sources((BlockingAdapter(PRIMARY, _new_records("222222", "New Bank"), started, release),)),
        )
        await asyncio.wait_for(started.wait(), timeout=1)

        old_result = await client.lookup("45717360")
        new_result = await client.lookup("222222")

        assert old_result.status is LookupStatus.FOUND
        assert old_result.data is not None
        assert old_result.data.issuer_name == "Old Bank"
        assert new_result.status is LookupStatus.NOT_FOUND

        release.set()
        await update_task

        replaced_old_result = await client.lookup("45717360")
        committed_new_result = await client.lookup("222222")

        assert replaced_old_result.status is LookupStatus.NOT_FOUND
        assert committed_new_result.status is LookupStatus.FOUND
        assert committed_new_result.data is not None
        assert committed_new_result.data.issuer_name == "New Bank"
    finally:
        release.set()


@pytest.mark.asyncio(loop_scope="session")
async def test_cancelled_update_keeps_visible_dataset_consistent(
    store: BinDataStore,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cancelling an update after uncommitted writes preserves the committed dataset."""
    client = BinData(store=store)
    release = asyncio.Event()
    uncommitted_delete_flushed = asyncio.Event()

    async def paused_replace_all(
        self: ImportedRecordsService,
        records: ImportReplacement,
    ) -> None:
        """Flush partial replacement work and pause until the test cancels the update."""
        del records
        await self._session.execute(delete(BinRecordSourceModel))
        await self._session.execute(delete(BinRecordModel))
        await self._session.execute(delete(DataSourceModel))
        await self._session.flush()
        uncommitted_delete_flushed.set()
        await release.wait()

    try:
        await store.init()
        await store.import_sources(_old_adapters())
        monkeypatch.setattr(ImportedRecordsService, "replace_all", paused_replace_all)

        update_task = asyncio.create_task(
            store.import_sources((StaticAdapter(PRIMARY, _new_records("222222", "New Bank")),)),
        )
        await asyncio.wait_for(uncommitted_delete_flushed.wait(), timeout=1)

        visible_during_update = await client.lookup("45717360")
        assert visible_during_update.status is LookupStatus.FOUND
        assert visible_during_update.data is not None
        assert visible_during_update.data.issuer_name == "Old Bank"

        update_task.cancel()

        with pytest.raises(asyncio.CancelledError):
            await update_task

        old_result = await client.lookup("45717360")
        new_result = await client.lookup("222222")

        assert old_result.status is LookupStatus.FOUND
        assert old_result.data is not None
        assert old_result.data.issuer_name == "Old Bank"
        assert new_result.status is LookupStatus.NOT_FOUND
    finally:
        release.set()


@pytest.mark.asyncio(loop_scope="session")
async def test_concurrent_imports_wait_for_active_writer(
    store: BinDataStore,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Concurrent imports wait for the active writer instead of raising a lock error."""
    if store.drivername != "sqlite+aiosqlite":
        pytest.skip(
            "validates the SQLite single-writer busy_timeout contract (PRD 4.8); "
            "PostgreSQL uses native MVCC transactions and has no 'database is locked' failure mode",
        )

    original_replace_all = ImportedRecordsService.replace_all
    start = asyncio.Event()

    async def slow_replace_all(
        self: ImportedRecordsService,
        records: ImportReplacement,
    ) -> None:
        """Hold the write transaction briefly after the replacement write."""
        await original_replace_all(self, records)
        await asyncio.sleep(0.05)

    async def import_one(index: int) -> str:
        await start.wait()
        iin_start = f"33333{index}"
        await store.import_sources((StaticAdapter(PRIMARY, _new_records(iin_start, f"Writer {index} Bank")),))
        return iin_start

    await store.init()
    monkeypatch.setattr(ImportedRecordsService, "replace_all", slow_replace_all)

    tasks = [asyncio.create_task(import_one(index)) for index in range(CONCURRENT_IMPORT_COUNT)]
    start.set()
    imported_iins = set(await asyncio.gather(*tasks))

    assert await _record_count(store) == 1
    assert await _only_iin_start(store) in imported_iins


def _old_adapters() -> tuple[SourceAdapter, ...]:
    return (StaticAdapter(PRIMARY, _new_records("45717360", "Old Bank")),)


def _new_records(iin_start: str, issuer_name: str) -> tuple[NormalizedSourceRecord, ...]:
    return (
        NormalizedSourceRecord(
            source=PRIMARY,
            row_key=f"primary-{iin_start}",
            iin_start=iin_start,
            scheme="visa",
            issuer_name=issuer_name,
        ),
    )


async def _record_count(store: BinDataStore) -> int:
    async with store.session() as session:
        return await session.scalar(select(func.count()).select_from(BinRecordModel)) or 0


async def _only_iin_start(store: BinDataStore) -> str:
    async with store.session() as session:
        return (await session.scalars(select(BinRecordModel.iin_start))).one()
