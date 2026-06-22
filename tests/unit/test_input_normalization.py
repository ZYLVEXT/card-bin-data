"""Tests for safe lookup input normalization."""
# ruff: noqa: S101

from __future__ import annotations

import pytest

from card_bin_data.input import (
    FAILED_LUHN_WARNING,
    SHORT_LUHN_WARNING,
    TOO_SHORT_WARNING,
    UNSUPPORTED_LENGTH_WARNING,
    normalize_lookup_input,
)
from card_bin_data.types import LookupStatus


@pytest.mark.parametrize(
    ("raw_input", "expected_candidates", "is_full_pan_input"),
    [
        ("457173", ("457173",), False),
        ("45717360", ("45717360", "457173"), False),
        ("4571 7360", ("45717360", "457173"), False),
        ("4571-7360", ("45717360", "457173"), False),
        ("4111 1111 1111 1111", ("41111111", "411111"), True),
        ("4111-1111-1111-1111", ("41111111", "411111"), True),
    ],
)
def test_normalize_lookup_input_accepts_supported_shapes(
    raw_input: str,
    expected_candidates: tuple[str, ...],
    *,
    is_full_pan_input: bool,
) -> None:
    """Supported inputs normalize to safe prefix candidates."""
    result = normalize_lookup_input(raw_input)

    assert result.status is LookupStatus.NOT_FOUND
    assert result.query.prefix == expected_candidates[0]
    assert result.query.candidates == expected_candidates
    assert result.query.is_full_pan_input is is_full_pan_input
    assert result.validation_warnings == ()


def test_lookup_candidates_prioritize_eight_digit_prefix_before_six_digit_prefix() -> None:
    """Eight-digit candidates are attempted before six-digit fallback candidates."""
    result = normalize_lookup_input("4571736012345678")

    assert result.query.candidates == ("45717360", "457173")


@pytest.mark.parametrize(
    ("raw_input", "expected_warning"),
    [
        ("12345", TOO_SHORT_WARNING),
        ("4571-73x0", "lookup input must contain only digits, spaces, or hyphens"),
        ("1234567", UNSUPPORTED_LENGTH_WARNING),
        ("123456789", UNSUPPORTED_LENGTH_WARNING),
    ],
)
def test_normalize_lookup_input_marks_invalid_input_as_typed_status(
    raw_input: str,
    expected_warning: str,
) -> None:
    """Invalid input returns an invalid lookup result instead of raising."""
    result = normalize_lookup_input(raw_input)

    assert result.status is LookupStatus.INVALID
    assert result.invalid is True
    assert not result.query.prefix
    assert result.query.candidates == ()
    assert result.validation_warnings == (expected_warning,)


def test_luhn_validation_defaults_to_disabled() -> None:
    """Full PAN-like input is not Luhn validated unless explicitly requested."""
    result = normalize_lookup_input("4111 1111 1111 1112")

    assert result.status is LookupStatus.NOT_FOUND
    assert result.validation_warnings == ()


def test_luhn_validation_accepts_valid_full_pan_input() -> None:
    """Luhn validation accepts valid full PAN-like input while retaining only prefixes."""
    result = normalize_lookup_input("4111 1111 1111 1111", validate_luhn=True)

    assert result.status is LookupStatus.NOT_FOUND
    assert result.query.prefix == "41111111"
    assert result.validation_warnings == ()


def test_luhn_validation_accepts_valid_full_pan_with_adjusted_double_digit() -> None:
    """Luhn validation covers doubled digits that require checksum adjustment."""
    result = normalize_lookup_input("5500 0000 0000 0004", validate_luhn=True)

    assert result.status is LookupStatus.NOT_FOUND
    assert result.query.prefix == "55000000"
    assert result.validation_warnings == ()


def test_luhn_validation_marks_invalid_full_pan_input_as_invalid_status() -> None:
    """Luhn validation returns invalid status for full PAN-like input that fails the checksum."""
    result = normalize_lookup_input("4111 1111 1111 1112", validate_luhn=True)

    assert result.status is LookupStatus.INVALID
    assert not result.query.prefix
    assert result.query.candidates == ()
    assert result.validation_warnings == (FAILED_LUHN_WARNING,)


@pytest.mark.parametrize("raw_input", ["457173", "45717360"])
def test_luhn_validation_on_short_prefix_adds_warning(raw_input: str) -> None:
    """BIN/IIN input with Luhn validation requested produces a warning, not an exception."""
    result = normalize_lookup_input(raw_input, validate_luhn=True)

    assert result.status is LookupStatus.NOT_FOUND
    assert result.validation_warnings == (SHORT_LUHN_WARNING,)
