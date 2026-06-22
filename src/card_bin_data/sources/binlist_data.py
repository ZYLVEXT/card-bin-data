"""Adapter for the binlist/data ranges CSV source."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from ..types import NormalizedSourceRecord, SourceMetadata  # noqa: TID252
from ._csv import is_numeric_prefix, iter_csv_records, none_if_empty, optional_bool, optional_int, row_key

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Iterable


_REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_BINLIST_DATA_PATH = _REPO_ROOT / "datasets" / "binlist_data" / "ranges.csv"


class BinlistDataAdapter:
    """Parse the primary binlist/data ranges.csv source into normalized records."""

    def __init__(self, local_path: Path = DEFAULT_BINLIST_DATA_PATH) -> None:
        """Initialize the adapter with a local ranges.csv path."""
        self._local_path = local_path
        self._metadata = SourceMetadata(
            source_id="binlist/data",
            display_name="binlist/data",
            upstream_url="https://github.com/binlist/data.git",
            local_path=local_path,
        )

    @property
    def metadata(self) -> SourceMetadata:
        """Source metadata without reading source records."""
        return self._metadata

    async def iter_records(self) -> AsyncIterator[NormalizedSourceRecord]:
        """Yield normalized records parsed from the local ranges.csv file.

        The CSV file is read and normalized in bounded worker-thread batches.
        """
        async for record in iter_csv_records(self._local_path, self._normalize_rows):
            yield record

    def _normalize_rows(self, rows: Iterable[dict[str, str]]) -> Iterable[NormalizedSourceRecord]:
        for line_number, row in enumerate(rows, start=2):
            iin_start = none_if_empty(row.get("iin_start"))
            if iin_start is None or not iin_start.isdecimal():
                continue
            iin_end = none_if_empty(row.get("iin_end"))
            yield NormalizedSourceRecord(
                source=self.metadata,
                row_key=row_key(self._local_path.name, line_number, iin_start),
                iin_start=iin_start,
                iin_end=iin_end if is_numeric_prefix(iin_end) else None,
                number_length=optional_int(row.get("number_length")),
                luhn=optional_bool(row.get("number_luhn")),
                scheme=none_if_empty(row.get("scheme")),
                product_brand=none_if_empty(row.get("brand")),
                type=none_if_empty(row.get("type")),
                prepaid=optional_bool(row.get("prepaid")),
                country_alpha2=none_if_empty(row.get("country")),
                issuer_name=none_if_empty(row.get("bank_name")),
                issuer_url=none_if_empty(row.get("bank_url")),
                issuer_phone=none_if_empty(row.get("bank_phone")),
                issuer_city=none_if_empty(row.get("bank_city")),
                raw_payload=row,
            )
