"""Adapter for the marlonlp/binlist-data CSV source."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from ..types import NormalizedSourceRecord, SourceMetadata  # noqa: TID252
from ._csv import iter_csv_records, none_if_empty, row_key

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Iterable


_REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_MARLONLP_PATH = _REPO_ROOT / "datasets" / "marlonlp_binlist_data" / "binlist-data.csv"


class MarlonlpBinlistDataAdapter:
    """Parse the fallback marlonlp/binlist-data semicolon CSV source."""

    def __init__(self, local_path: Path = DEFAULT_MARLONLP_PATH) -> None:
        """Initialize the adapter with a local binlist-data.csv path."""
        self._local_path = local_path
        self._metadata = SourceMetadata(
            source_id="marlonlp/binlist-data",
            display_name="marlonlp/binlist-data",
            upstream_url="https://github.com/marlonlp/binlist-data.git",
            license="CC BY 4.0",
            local_path=local_path,
        )

    @property
    def metadata(self) -> SourceMetadata:
        """Source metadata without reading source records."""
        return self._metadata

    async def iter_records(self) -> AsyncIterator[NormalizedSourceRecord]:
        """Yield normalized records parsed from the local semicolon-delimited CSV file.

        The CSV file is read and normalized in bounded worker-thread batches.
        """
        async for record in iter_csv_records(self._local_path, self._normalize_rows, delimiter=";"):
            yield record

    def _normalize_rows(self, rows: Iterable[dict[str, str]]) -> Iterable[NormalizedSourceRecord]:
        for line_number, row in enumerate(rows, start=2):
            iin_start = none_if_empty(row.get("bin"))
            if iin_start is None or not iin_start.isdecimal():
                continue
            yield NormalizedSourceRecord(
                source=self.metadata,
                row_key=row_key(self._local_path.name, line_number, iin_start),
                iin_start=iin_start,
                scheme=none_if_empty(row.get("brand")),
                type=none_if_empty(row.get("type")),
                category=none_if_empty(row.get("category")),
                issuer_name=none_if_empty(row.get("issuer")),
                raw_payload=row,
            )
