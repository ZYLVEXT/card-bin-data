"""Unit coverage for the single-statement lookup priority."""
# ruff: file-ignore[assert]

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, cast

import pytest

from card_bin_data.db.models import BinRecordModel
from card_bin_data.db.services import BinRecordService
from card_bin_data.types import LookupQuery

if TYPE_CHECKING:
    from sqlalchemy import Select
    from sqlalchemy.ext.asyncio import AsyncSession


@dataclass(slots=True)
class ScalarResultStub:
    """Small unique scalar result stub for lookup priority tests."""

    record: BinRecordModel | None

    def unique(self) -> ScalarResultStub:
        """Mirror SQLAlchemy's collection eager-load de-duplication step.

        Returns:
            This result stub.
        """
        return self

    def one_or_none(self) -> BinRecordModel | None:
        """Return the configured lookup row."""
        return self.record


class SessionStub:
    """Async session stub that records the lookup statement and returns one row."""

    def __init__(self, record: BinRecordModel | None) -> None:
        """Initialize the stub with the ranked lookup result."""
        self.bind = None
        self.info: dict[str, object] = {}
        self._record = record
        self.statements: list[Select[tuple[BinRecordModel]]] = []

    @staticmethod
    def get_bind() -> object:
        """Return a minimal SQLAlchemy bind stub for Advanced Alchemy repository setup."""
        return BindStub()

    async def scalars(self, statement: Select[tuple[BinRecordModel]]) -> ScalarResultStub:
        """Record the statement and return the next configured row.

        Returns:
            Scalar result stub carrying the next configured record.
        """
        self.statements.append(statement)
        return ScalarResultStub(self._record)


class BindStub:
    """Minimal bind stub exposing a dialect name for repository construction."""

    dialect = type("DialectStub", (), {"name": "sqlite"})()


@pytest.mark.asyncio
async def test_eight_digit_lookup_ranks_exact_range_and_six_digit_fallback_in_one_statement() -> None:
    """A single statement ranks exact 8, range, and exact 6 matches in that order."""
    session = SessionStub(_record("45717360"))

    result = await BinRecordService(session=cast("AsyncSession", session)).lookup_record(
        LookupQuery(prefix="45717360", candidates=("45717360", "457173")),
    )

    assert result is not None
    assert result.iin_start == "45717360"
    assert len(session.statements) == 1
    sql = _statement_sql(session.statements[0])
    assert "CASE WHEN (bin_records.iin_start = '45717360') THEN 0" in sql
    assert "bin_records.range_start_8 <= '45717360'" in sql
    assert "bin_records.range_end_8 >= '45717360'" in sql
    assert "WHEN (bin_records.iin_start = '457173') THEN 2 ELSE 3 END" in sql
    assert "ORDER BY CASE" in sql
    assert "length(bin_records.iin_start) DESC, bin_records.iin_start DESC, bin_records.id" in sql


@pytest.mark.asyncio
async def test_six_digit_lookup_uses_one_exact_match_statement() -> None:
    """A six-digit-only query stays on the same one-statement path."""
    session = SessionStub(_record("457173"))

    result = await BinRecordService(session=cast("AsyncSession", session)).lookup_record(
        LookupQuery(prefix="457173", candidates=("457173",)),
    )

    assert result is not None
    assert result.iin_start == "457173"
    assert len(session.statements) == 1
    assert "bin_records.iin_start = '457173'" in _statement_sql(session.statements[0])


@pytest.mark.asyncio
async def test_eight_digit_only_candidate_uses_exact_and_range_conditions() -> None:
    """The query layer accepts a direct 8-digit candidate without a 6-digit fallback."""
    session = SessionStub(None)

    result = await BinRecordService(session=cast("AsyncSession", session)).lookup_record(
        LookupQuery(prefix="45717360", candidates=("45717360",)),
    )

    assert result is None
    assert len(session.statements) == 1
    sql = _statement_sql(session.statements[0])
    assert "bin_records.iin_start = '45717360'" in sql
    assert "bin_records.range_start_8 <= '45717360'" in sql
    assert "THEN 2" not in sql


@pytest.mark.asyncio
async def test_lookup_without_supported_candidate_returns_none_without_querying() -> None:
    """Unsupported candidate lengths are ignored by the query layer."""
    session = SessionStub(None)

    result = await BinRecordService(session=cast("AsyncSession", session)).lookup_record(
        LookupQuery(prefix="", candidates=()),
    )

    assert result is None
    assert session.statements == []


def _record(iin_start: str, *, iin_end: str | None = None) -> BinRecordModel:
    return BinRecordModel(iin_start=iin_start, iin_end=iin_end)


def _statement_sql(statement: Select[tuple[BinRecordModel]]) -> str:
    return str(statement.compile(compile_kwargs={"literal_binds": True}))
