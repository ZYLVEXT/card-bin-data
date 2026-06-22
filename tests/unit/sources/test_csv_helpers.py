"""Tests for shared CSV field normalization helpers."""
# ruff: noqa: S101

from __future__ import annotations

import pytest

from card_bin_data.sources._csv import optional_int  # noqa: PLC2701


@pytest.mark.parametrize("value", ["", "   ", None])
def test_optional_int_returns_none_for_blank(value: str | None) -> None:
    """Blank or missing fields normalize to None, not an error."""
    assert optional_int(value) is None


@pytest.mark.parametrize(
    ("value", "expected"),
    [("16", 16), (" 16 ", 16), ("+16", 16), ("-16", -16)],
)
def test_optional_int_parses_signed_decimals(value: str, expected: int) -> None:
    """Plain and explicitly signed decimal fields parse to ints."""
    assert optional_int(value) == expected


@pytest.mark.parametrize("value", ["sixteen", "1.5", "16px", "0x10", "--1"])
def test_optional_int_returns_none_for_non_numeric(value: str) -> None:
    """Malformed numeric fields return None instead of raising ValueError.

    A bare int() here would abort the entire import transaction on one corrupt
    source row; the helper degrades gracefully instead.
    """
    assert optional_int(value) is None
