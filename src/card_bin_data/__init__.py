"""Public API for card_bin_data."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .exceptions import CardBinDataError, CardBinDataStoreConfigurationError
from .results import LookupResult
from .types import (
    BinInfo,
    LookupQuery,
    LookupStatus,
    NormalizedSourceRecord,
    SourceAttribution,
    SourceMetadata,
)

if TYPE_CHECKING:
    from .client import BinData
    from .store import BinDataStore

__version__ = "0.3.0"

__all__ = [
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
]


def __getattr__(name: str) -> object:
    """Load database-backed public APIs only when consumers request them.

    Returns:
        Requested public API object.

    Raises:
        AttributeError: If ``name`` is not a supported lazy export.
    """
    if name == "BinData":
        from .client import BinData  # ruff: ignore[import-outside-top-level]

        value = BinData
    elif name == "BinDataStore":
        from .store import BinDataStore  # ruff: ignore[import-outside-top-level]

        value = BinDataStore
    else:
        msg = f"module {__name__!r} has no attribute {name!r}"
        raise AttributeError(msg)

    globals()[name] = value
    return value
