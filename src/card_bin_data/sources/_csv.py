"""Shared CSV field normalization helpers for source adapters."""

from __future__ import annotations

import asyncio
import csv
from itertools import islice
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable, Iterable, Iterator
    from pathlib import Path
    from typing import TextIO

CSV_RECORD_BATCH_SIZE = 1_000


def none_if_empty(value: str | None) -> str | None:
    """Return a stripped string value or None for blank CSV fields."""
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def optional_int(value: str | None) -> int | None:
    """Parse an optional integer CSV field, ignoring non-numeric junk.

    Source CSVs are only semi-trusted bundled data. A bare ``int()`` raises
    ``ValueError`` on malformed input, which would abort the whole import
    transaction (an availability impact from one corrupt row). Returning None on
    non-numeric data keeps a single bad row from poisoning the dataset, matching
    the lenient None-on-blank contract used by the other helpers here.

    Returns:
        The parsed integer, or None for blank or non-numeric fields.
    """
    normalized = none_if_empty(value)
    if normalized is None:
        return None
    try:
        return int(normalized)
    except ValueError:
        return None


def optional_bool(value: str | None) -> bool | None:
    """Return a blank-aware boolean CSV field, treating unknown tokens as False."""
    normalized = none_if_empty(value)
    if normalized is None:
        return None
    return normalized.casefold() in {"1", "true", "yes", "y"}


def is_numeric_prefix(value: str | None) -> bool:
    """Return whether a source key is a usable numeric BIN/IIN prefix."""
    normalized = none_if_empty(value)
    return normalized is not None and normalized.isdecimal()


def row_key(file_name: str, line_number: int, value: str) -> str:
    """Return a stable per-row provenance key from file, line, and prefix value."""
    return f"{file_name}:{line_number}:{value}"


async def iter_csv_records[T](
    local_path: Path,
    normalize_rows: Callable[[Iterable[dict[str, str]]], Iterable[T]],
    *,
    delimiter: str = ",",
) -> AsyncIterator[T]:
    """Yield normalized CSV records without materializing the whole source file."""
    csv_file = cast("TextIO", await asyncio.to_thread(local_path.open, newline="", encoding="utf-8"))
    try:
        reader = cast("Iterable[dict[str, str]]", csv.DictReader(csv_file, delimiter=delimiter))
        records = iter(normalize_rows(reader))
        while batch := cast("list[T]", await asyncio.to_thread(next_record_batch, records)):
            for record in batch:
                yield record
    finally:
        await asyncio.to_thread(csv_file.close)


def next_record_batch[T](records: Iterator[T], batch_size: int = CSV_RECORD_BATCH_SIZE) -> list[T]:
    """Return the next bounded batch from a synchronous record iterator."""
    return list(islice(records, batch_size))
