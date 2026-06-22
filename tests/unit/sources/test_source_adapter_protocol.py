"""Tests for source adapter protocol contracts."""
# ruff: noqa: S101

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from card_bin_data.sources import SourceAdapter
from card_bin_data.types import NormalizedSourceRecord, SourceMetadata

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from pathlib import Path


class FakeSourceAdapter:
    """Small adapter implementation used to verify the protocol boundary."""

    def __init__(self, *, local_path: Path) -> None:
        """Initialize the fake adapter with source metadata only."""
        self._metadata = SourceMetadata(
            source_id="fake-source",
            display_name="Fake Source",
            upstream_url="https://example.test/fake-source.git",
            license="CC BY 4.0",
            local_path=local_path,
        )
        self.records_iterated = 0

    @property
    def metadata(self) -> SourceMetadata:
        """Source metadata without reading source records."""
        return self._metadata

    async def iter_records(self) -> AsyncIterator[NormalizedSourceRecord]:
        """Yield normalized records with preserved source row identity."""
        self.records_iterated += 1
        yield NormalizedSourceRecord(
            source=self.metadata,
            row_key="row-000123",
            iin_start="000123",
            iin_end="00012399",
            scheme="visa",
            raw_payload={"BIN": "000123", "Brand": "visa"},
        )


def test_source_adapter_supports_intentional_runtime_protocol_checks(tmp_path: Path) -> None:
    """SourceAdapter supports runtime checks for adapter-shaped objects."""
    adapter = FakeSourceAdapter(local_path=tmp_path / "source.csv")

    assert isinstance(adapter, SourceAdapter)
    assert not isinstance(object(), SourceAdapter)
    assert adapter.records_iterated == 0


def test_adapter_metadata_is_available_without_reading_records(tmp_path: Path) -> None:
    """Adapter metadata exposes source identity and local file path eagerly."""
    adapter = FakeSourceAdapter(local_path=tmp_path / "source.csv")

    assert adapter.metadata.source_id == "fake-source"
    assert adapter.metadata.display_name == "Fake Source"
    assert adapter.metadata.upstream_url == "https://example.test/fake-source.git"
    assert adapter.metadata.license == "CC BY 4.0"
    assert adapter.metadata.local_path == tmp_path / "source.csv"
    assert adapter.records_iterated == 0


@pytest.mark.asyncio
async def test_iter_records_emits_typed_records_with_preserved_payload(tmp_path: Path) -> None:
    """Adapter iteration emits typed source records asynchronously."""
    adapter = FakeSourceAdapter(local_path=tmp_path / "source.csv")

    records = [record async for record in adapter.iter_records()]

    assert records == [
        NormalizedSourceRecord(
            source=adapter.metadata,
            row_key="row-000123",
            iin_start="000123",
            iin_end="00012399",
            scheme="visa",
            raw_payload={"BIN": "000123", "Brand": "visa"},
        ),
    ]
    assert records[0].iin_start == "000123"
    assert records[0].row_key == "row-000123"
    assert records[0].raw_payload["BIN"] == "000123"
    assert adapter.records_iterated == 1
