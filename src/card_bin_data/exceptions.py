"""Safe exception types for card_bin_data."""

from __future__ import annotations


class CardBinDataError(Exception):
    """Base class for card_bin_data errors."""


class CardBinDataStoreConfigurationError(CardBinDataError):
    """Raised when store or database configuration is invalid."""
