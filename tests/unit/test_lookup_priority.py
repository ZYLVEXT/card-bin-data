"""Unit coverage for lookup query priority."""
# ruff: noqa: S101

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

EXACT_AND_RANGE_ATTEMPTS = 2
ALL_LOOKUP_ATTEMPTS = 3


@dataclass(slots=True)
class ScalarResultStub:
    """Small scalar result stub for lookup priority tests."""

    record: BinRecordModel | None

    def one_or_none(self) -> BinRecordModel | None:
        """Return the configured lookup row."""
        return self.record


class SessionStub:
    """Async session stub that records statement attempts and returns configured rows."""

    def __init__(self, records: tuple[BinRecordModel | None, ...]) -> None:
        """Initialize the stub with rows returned for each lookup attempt."""
        self.bind = None
        self.info: dict[str, object] = {}
        self._records = list(records)
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
        return ScalarResultStub(self._records.pop(0))


class BindStub:
    """Minimal bind stub exposing a dialect name for repository construction."""

    dialect = type("DialectStub", (), {"name": "sqlite"})()


@pytest.mark.asyncio
async def test_exact_eight_digit_match_stops_before_range_and_six_digit_lookup() -> None:
    """Exact 8-digit matches are attempted first and short-circuit later fallbacks."""
    session = SessionStub((_record("45717360"),))

    result = await BinRecordService(session=cast("AsyncSession", session)).lookup_record(
        LookupQuery(prefix="45717360", candidates=("45717360", "457173")),
    )

    assert result is not None
    assert result.iin_start == "45717360"
    assert len(session.statements) == 1


@pytest.mark.asyncio
async def test_range_match_runs_before_exact_six_digit_lookup() -> None:
    """Range matching is attempted after exact 8-digit and before exact 6-digit fallback."""
    session = SessionStub((None, _record("45717300", iin_end="45717399")))

    result = await BinRecordService(session=cast("AsyncSession", session)).lookup_record(
        LookupQuery(prefix="45717361", candidates=("45717361", "457173")),
    )

    assert result is not None
    assert result.iin_start == "45717300"
    assert len(session.statements) == EXACT_AND_RANGE_ATTEMPTS
    assert _statement_sql(session.statements[0]).count("bin_records.iin_start = '45717361'") == 1
    assert "bin_records.range_start_8 <= '45717361'" in _statement_sql(session.statements[1])
    assert "bin_records.range_end_8 >= '45717361'" in _statement_sql(session.statements[1])


@pytest.mark.asyncio
async def test_exact_six_digit_match_resolves_when_more_specific_data_is_absent() -> None:
    """Six-digit fallback is used only after exact 8-digit and range lookup miss."""
    session = SessionStub((None, None, _record("457173")))

    result = await BinRecordService(session=cast("AsyncSession", session)).lookup_record(
        LookupQuery(prefix="45717361", candidates=("45717361", "457173")),
    )

    assert result is not None
    assert result.iin_start == "457173"
    assert len(session.statements) == ALL_LOOKUP_ATTEMPTS
    assert _statement_sql(session.statements[0]).count("bin_records.iin_start = '45717361'") == 1
    assert "bin_records.range_start_8 <= '45717361'" in _statement_sql(session.statements[1])
    assert "bin_records.range_end_8 >= '45717361'" in _statement_sql(session.statements[1])
    assert _statement_sql(session.statements[2]).count("bin_records.iin_start = '457173'") == 1


def test_range_statement_uses_normalized_boundaries_and_specificity_ordering() -> None:
    """Range lookup compares normalized 8-digit boundaries and prefers more-specific ranges."""
    sql = _statement_sql(BinRecordService._range_statement("40050050"))  # noqa: SLF001

    assert "bin_records.range_start_8 <= '40050050'" in sql
    assert "bin_records.range_end_8 >= '40050050'" in sql
    assert "ORDER BY length(bin_records.iin_start) DESC, bin_records.iin_start DESC, bin_records.id" in sql


@pytest.mark.asyncio
async def test_lookup_without_supported_candidate_returns_none_without_querying() -> None:
    """Unsupported candidate lengths are ignored by the query layer."""
    session = SessionStub(())

    result = await BinRecordService(session=cast("AsyncSession", session)).lookup_record(
        LookupQuery(prefix="", candidates=()),
    )

    assert result is None
    assert session.statements == []


def _record(iin_start: str, *, iin_end: str | None = None) -> BinRecordModel:
    return BinRecordModel(iin_start=iin_start, iin_end=iin_end)


def _statement_sql(statement: Select[tuple[BinRecordModel]]) -> str:
    return str(statement.compile(compile_kwargs={"literal_binds": True}))
