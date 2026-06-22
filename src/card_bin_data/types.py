"""Typed public and source contracts for card_bin_data."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping
    from datetime import datetime
    from pathlib import Path


class LookupStatus(StrEnum):
    """Lookup outcome status returned as data instead of normal-control-flow exceptions."""

    FOUND = "found"
    NOT_FOUND = "not_found"
    INVALID = "invalid"


@dataclass(frozen=True, slots=True)
class SourceMetadata:
    """Metadata describing one upstream BIN/IIN data source."""

    source_id: str
    display_name: str
    upstream_url: str
    license: str | None = None
    local_path: Path | None = None


@dataclass(frozen=True, slots=True)
class SourceAttribution:
    """Provenance for source rows that contributed to a lookup result."""

    source_id: str
    upstream_url: str
    license: str | None = None
    imported_at: datetime | None = None
    source_row_key: str | None = None


@dataclass(frozen=True, slots=True)
class LookupQuery:
    """Safe representation of a lookup request after input normalization."""

    prefix: str
    candidates: tuple[str, ...] = field(default_factory=tuple)
    is_full_pan_input: bool = False


@dataclass(frozen=True, slots=True)
class BinInfo:
    """Normalized BIN/IIN information exposed to library consumers."""

    iin_start: str
    iin_end: str | None = None
    number_length: int | None = None
    luhn: bool | None = None
    scheme: str | None = None
    product_brand: str | None = None
    type: str | None = None
    category: str | None = None
    prepaid: bool | None = None
    country_alpha2: str | None = None
    country_alpha3: str | None = None
    country_name: str | None = None
    issuer_name: str | None = None
    issuer_phone: str | None = None
    issuer_url: str | None = None
    issuer_city: str | None = None


@dataclass(frozen=True, slots=True)
class NormalizedSourceRecord:
    """Normalized source row shape emitted by adapters before persistence or merging."""

    source: SourceMetadata
    row_key: str
    iin_start: str
    iin_end: str | None = None
    number_length: int | None = None
    luhn: bool | None = None
    scheme: str | None = None
    product_brand: str | None = None
    type: str | None = None
    category: str | None = None
    prepaid: bool | None = None
    country_alpha2: str | None = None
    country_alpha3: str | None = None
    country_name: str | None = None
    issuer_name: str | None = None
    issuer_phone: str | None = None
    issuer_url: str | None = None
    issuer_city: str | None = None
    raw_payload: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Freeze raw payload mapping for stable record semantics."""
        object.__setattr__(self, "raw_payload", MappingProxyType(dict(self.raw_payload)))
