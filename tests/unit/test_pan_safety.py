"""PAN safety tests for lookup input normalization."""
# ruff: noqa: S101

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pytest

from card_bin_data.input import normalize_lookup_input

FULL_PAN = "4111111111111111"
SPACED_FULL_PAN = "4111 1111 1111 1111"
HYPHENATED_FULL_PAN = "4111-1111-1111-1111"


def test_full_pan_is_not_retained_in_normalized_query_or_result_repr() -> None:
    """Full PAN values are not retained in normalized objects or repr output."""
    result = normalize_lookup_input(SPACED_FULL_PAN, validate_luhn=True)

    assert result.query.prefix == "41111111"
    assert FULL_PAN not in repr(result.query)
    assert FULL_PAN not in repr(result)
    assert SPACED_FULL_PAN not in repr(result)
    assert HYPHENATED_FULL_PAN not in repr(result)


def test_failed_luhn_result_does_not_include_full_pan_in_repr() -> None:
    """Invalid Luhn results expose only safe validation metadata."""
    unsafe_input = "4111 1111 1111 1112"
    unsafe_digits = "4111111111111112"

    result = normalize_lookup_input(unsafe_input, validate_luhn=True)

    assert unsafe_digits not in repr(result.query)
    assert unsafe_digits not in repr(result)
    assert unsafe_input not in repr(result)


def test_non_numeric_result_does_not_include_full_pan_in_repr() -> None:
    """Invalid non-numeric results do not echo sensitive input."""
    unsafe_input = "4111 1111 1111 111x"

    result = normalize_lookup_input(unsafe_input)

    assert unsafe_input not in repr(result)
    assert "411111111111" not in repr(result)


def test_normalization_does_not_log_full_pan(caplog: pytest.LogCaptureFixture) -> None:
    """Normalization does not write full PAN values to logs.

    Regression guard: ``normalize_lookup_input`` performs no logging today, so this
    asserts a security invariant for the future (it must stay silent), not current
    observable behavior.
    """
    caplog.set_level(logging.DEBUG)

    normalize_lookup_input(SPACED_FULL_PAN, validate_luhn=True)

    assert FULL_PAN not in caplog.text
    assert SPACED_FULL_PAN not in caplog.text
