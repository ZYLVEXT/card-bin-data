"""Shared source adapter protocol."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from card_bin_data.types import NormalizedSourceRecord, SourceMetadata


@runtime_checkable
class SourceAdapter(Protocol):
    """Protocol implemented by source parsers that emit normalized records.

    Source adapters are responsible for reading one local source format and
    preserving source row identity. Database writes, merge priority, and
    conflict resolution belong to the import/store layer.

    Runtime ``isinstance(adapter, SourceAdapter)`` checks are supported as an
    intentional contract for validating adapter-shaped objects at integration
    boundaries.
    """

    @property
    def metadata(self) -> SourceMetadata:
        """Metadata for the source, available without iterating records."""
        ...

    def iter_records(self) -> AsyncIterator[NormalizedSourceRecord]:
        """Iterate normalized source records parsed from the local source."""
        ...
