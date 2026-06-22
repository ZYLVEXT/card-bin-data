"""Adapter for the venelinkochev/bin-list-data CSV source."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from ..types import NormalizedSourceRecord, SourceMetadata  # noqa: TID252
from ._csv import iter_csv_records, none_if_empty, row_key

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Iterable


_REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_VENELINKOCHEV_PATH = _REPO_ROOT / "datasets" / "venelinkochev_binlist_data" / "bin-list-data.csv"


class VenelinkochevBinListDataAdapter:
    """Parse the enrichment venelinkochev/bin-list-data CSV source."""

    def __init__(self, local_path: Path = DEFAULT_VENELINKOCHEV_PATH) -> None:
        """Initialize the adapter with a local bin-list-data.csv path."""
        self._local_path = local_path
        self._metadata = SourceMetadata(
            source_id="venelinkochev/bin-list-data",
            display_name="venelinkochev/bin-list-data",
            upstream_url="https://github.com/venelinkochev/bin-list-data.git",
            license="CC BY 4.0",
            local_path=local_path,
        )

    @property
    def metadata(self) -> SourceMetadata:
        """Source metadata without reading source records."""
        return self._metadata

    async def iter_records(self) -> AsyncIterator[NormalizedSourceRecord]:
        """Yield normalized records parsed from the local bin-list-data.csv file.

        The CSV file is read and normalized in bounded worker-thread batches.
        """
        async for record in iter_csv_records(self._local_path, self._normalize_rows):
            yield record

    def _normalize_rows(self, rows: Iterable[dict[str, str]]) -> Iterable[NormalizedSourceRecord]:
        for line_number, row in enumerate(rows, start=2):
            iin_start = none_if_empty(row.get("BIN"))
            if iin_start is None or not iin_start.isdecimal():
                continue
            yield NormalizedSourceRecord(
                source=self.metadata,
                row_key=row_key(self._local_path.name, line_number, iin_start),
                iin_start=iin_start,
                scheme=none_if_empty(row.get("Brand")),
                type=none_if_empty(row.get("Type")),
                category=none_if_empty(row.get("Category")),
                country_alpha2=none_if_empty(row.get("isoCode2")),
                country_alpha3=none_if_empty(row.get("isoCode3")),
                country_name=none_if_empty(row.get("CountryName")),
                issuer_name=none_if_empty(row.get("Issuer")),
                issuer_phone=none_if_empty(row.get("IssuerPhone")),
                issuer_url=none_if_empty(row.get("IssuerUrl")),
                raw_payload=row,
            )
