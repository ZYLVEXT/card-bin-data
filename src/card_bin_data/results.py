"""Lookup result contracts for card_bin_data."""

from __future__ import annotations

from dataclasses import dataclass, field

from .types import BinInfo, LookupQuery, LookupStatus, SourceAttribution


@dataclass(frozen=True, slots=True)
class LookupResult:
    """Typed lookup result for found, not-found, and invalid outcomes."""

    status: LookupStatus
    query: LookupQuery
    data: BinInfo | None = None
    validation_warnings: tuple[str, ...] = field(default_factory=tuple)
    sources: tuple[SourceAttribution, ...] = field(default_factory=tuple)

    @property
    def found(self) -> bool:
        """Whether the lookup found normalized BIN/IIN data."""
        return self.status is LookupStatus.FOUND

    @property
    def not_found(self) -> bool:
        """Whether the lookup completed without a matching record."""
        return self.status is LookupStatus.NOT_FOUND

    @property
    def invalid(self) -> bool:
        """Whether the lookup input was invalid."""
        return self.status is LookupStatus.INVALID
