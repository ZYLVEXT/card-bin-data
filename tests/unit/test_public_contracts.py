"""Tests for card_bin_data public typed contracts."""
# ruff: noqa: S101

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from collections.abc import MutableMapping

import pytest

import card_bin_data
import card_bin_data.sources as card_bin_data_sources
from card_bin_data import (
    BinInfo,
    CardBinDataError,
    CardBinDataStoreConfigurationError,
    LookupQuery,
    LookupResult,
    LookupStatus,
    NormalizedSourceRecord,
    SourceAttribution,
    SourceMetadata,
)
from card_bin_data.sources import (
    BinlistDataAdapter,
    MarlonlpBinlistDataAdapter,
    VenelinkochevBinListDataAdapter,
)


def test_public_exports_are_importable() -> None:
    """Public contract symbols are importable from card_bin_data."""
    expected_exports = {
        "BinData",
        "BinDataStore",
        "BinInfo",
        "CardBinDataError",
        "CardBinDataStoreConfigurationError",
        "LookupQuery",
        "LookupResult",
        "LookupStatus",
        "NormalizedSourceRecord",
        "SourceAttribution",
        "SourceMetadata",
        "__version__",
    }

    assert set(card_bin_data.__all__) == expected_exports
    assert {name for name in expected_exports if hasattr(card_bin_data, name)} == expected_exports
    assert LookupStatus.FOUND.value == "found"
    assert issubclass(CardBinDataStoreConfigurationError, CardBinDataError)


def test_source_adapter_exports_are_importable() -> None:
    """Source adapters are exported from card_bin_data.sources."""
    expected_exports = {
        "BinlistDataAdapter",
        "MarlonlpBinlistDataAdapter",
        "SourceAdapter",
        "VenelinkochevBinListDataAdapter",
    }

    assert set(card_bin_data_sources.__all__) == expected_exports
    assert {name for name in expected_exports if hasattr(card_bin_data_sources, name)} == expected_exports


def test_bundled_source_metadata_reflects_license_attribution_state() -> None:
    """Bundled adapters expose source license metadata used for attribution."""
    assert BinlistDataAdapter().metadata.license is None
    assert VenelinkochevBinListDataAdapter().metadata.license == "CC BY 4.0"
    assert MarlonlpBinlistDataAdapter().metadata.license == "CC BY 4.0"


@pytest.mark.parametrize(
    ("result", "found", "not_found", "invalid"),
    [
        (
            LookupResult(
                status=LookupStatus.FOUND,
                query=LookupQuery(prefix="45717360", candidates=("45717360", "457173")),
                data=BinInfo(iin_start="45717360", scheme="visa", type="debit"),
            ),
            True,
            False,
            False,
        ),
        (
            LookupResult(
                status=LookupStatus.NOT_FOUND,
                query=LookupQuery(prefix="999999", candidates=("999999",)),
            ),
            False,
            True,
            False,
        ),
        (
            LookupResult(
                status=LookupStatus.INVALID,
                query=LookupQuery(prefix="", candidates=()),
                validation_warnings=("input must contain 6 or more digits",),
            ),
            False,
            False,
            True,
        ),
    ],
)
def test_lookup_result_status_helpers(
    result: LookupResult,
    *,
    found: bool,
    not_found: bool,
    invalid: bool,
) -> None:
    """Lookup result objects represent all normal outcomes without exceptions."""
    assert result.found is found
    assert result.not_found is not_found
    assert result.invalid is invalid


def test_source_attribution_preserves_metadata_without_pan_fields() -> None:
    """Source attribution preserves provenance metadata without full PAN fields."""
    imported_at = datetime(2026, 6, 19, 0, 34, 55, tzinfo=UTC)

    attribution = SourceAttribution(
        source_id="binlist-data",
        upstream_url="https://github.com/binlist/data.git",
        license="CC0",
        imported_at=imported_at,
        source_row_key="45717360-45717369",
    )

    assert attribution.source_id == "binlist-data"
    assert attribution.upstream_url == "https://github.com/binlist/data.git"
    assert attribution.license == "CC0"
    assert attribution.imported_at == imported_at
    assert attribution.source_row_key == "45717360-45717369"
    assert "pan" not in attribution.__dataclass_fields__
    assert "card_number" not in attribution.__dataclass_fields__


def test_source_record_shapes_preserve_raw_and_normalized_data() -> None:
    """Source record contracts preserve row identity, raw fields, and normalized fields."""
    source = SourceMetadata(
        source_id="venelinkochev",
        display_name="venelinkochev/bin-list-data",
        upstream_url="https://github.com/venelinkochev/bin-list-data.git",
        license="CC BY 4.0",
    )

    normalized = NormalizedSourceRecord(
        source=source,
        row_key="000123",
        iin_start="000123",
        scheme="VISA",
        issuer_name="Example Bank",
        raw_payload={"BIN": "000123", "Brand": "VISA"},
    )

    assert normalized.iin_start == "000123"
    assert normalized.scheme == "VISA"
    assert normalized.raw_payload["BIN"] == "000123"
    assert normalized.raw_payload["Brand"] == "VISA"

    with pytest.raises(TypeError):
        cast("MutableMapping[str, str]", normalized.raw_payload)["PAN"] = "4571736012345678"
