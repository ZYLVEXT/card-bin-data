"""Safe lookup input normalization."""

from __future__ import annotations

from .results import LookupResult
from .types import LookupQuery, LookupStatus

MIN_PREFIX_LENGTH = 6
EXTENDED_PREFIX_LENGTH = 8
MIN_PAN_LENGTH = 12
MAX_PAN_LENGTH = 19
LUHN_DOUBLED_DIGIT_THRESHOLD = 9

SHORT_LUHN_WARNING = "luhn validation requires full PAN input"
NON_NUMERIC_WARNING = "lookup input must contain only digits, spaces, or hyphens"
TOO_SHORT_WARNING = "lookup input must contain at least 6 digits"
UNSUPPORTED_LENGTH_WARNING = "lookup input must be a 6-digit BIN, 8-digit IIN, or full PAN"
FAILED_LUHN_WARNING = "lookup input failed luhn validation"


def normalize_lookup_input(raw_input: str, *, validate_luhn: bool = False) -> LookupResult:
    """Normalize unsafe user lookup input into safe prefix-only lookup data.

    Args:
        raw_input: User-supplied BIN/IIN or PAN-like lookup input.
        validate_luhn: Whether to validate full PAN-like input with Luhn.

    Returns:
        A lookup result containing only safe prefix data. Valid normalized input
        uses ``LookupStatus.NOT_FOUND`` because source lookup has not happened yet.
    """
    normalized = raw_input.replace(" ", "").replace("-", "")

    if not normalized.isdecimal():
        return _invalid_result(NON_NUMERIC_WARNING)

    digit_count = len(normalized)
    if digit_count < MIN_PREFIX_LENGTH:
        return _invalid_result(TOO_SHORT_WARNING)

    if digit_count not in {MIN_PREFIX_LENGTH, EXTENDED_PREFIX_LENGTH} and not (
        MIN_PAN_LENGTH <= digit_count <= MAX_PAN_LENGTH
    ):
        return _invalid_result(UNSUPPORTED_LENGTH_WARNING)

    is_full_pan_input = digit_count >= MIN_PAN_LENGTH

    if validate_luhn and is_full_pan_input and not _passes_luhn(normalized):
        return _invalid_result(FAILED_LUHN_WARNING)

    candidates = _lookup_candidates(normalized)
    validation_warnings = (SHORT_LUHN_WARNING,) if validate_luhn and not is_full_pan_input else ()

    return LookupResult(
        status=LookupStatus.NOT_FOUND,
        query=LookupQuery(
            prefix=candidates[0],
            candidates=candidates,
            is_full_pan_input=is_full_pan_input,
        ),
        validation_warnings=validation_warnings,
    )


def _invalid_result(warning: str) -> LookupResult:
    """Build a safe invalid result without retaining raw lookup input.

    Returns:
        Invalid lookup result containing only a safe validation warning.
    """
    return LookupResult(
        status=LookupStatus.INVALID,
        query=LookupQuery(prefix="", candidates=()),
        validation_warnings=(warning,),
    )


def _lookup_candidates(normalized_digits: str) -> tuple[str, ...]:
    """Return lookup candidates in 8-digit before 6-digit priority order."""
    if len(normalized_digits) >= EXTENDED_PREFIX_LENGTH:
        return (
            normalized_digits[:EXTENDED_PREFIX_LENGTH],
            normalized_digits[:MIN_PREFIX_LENGTH],
        )
    return (normalized_digits[:MIN_PREFIX_LENGTH],)


def _passes_luhn(normalized_digits: str) -> bool:
    """Return whether digit-only input passes the Luhn checksum."""
    total = 0
    parity = len(normalized_digits) % 2

    for index, character in enumerate(normalized_digits):
        digit = int(character)
        if index % 2 == parity:
            digit *= 2
            if digit > LUHN_DOUBLED_DIGIT_THRESHOLD:
                digit -= LUHN_DOUBLED_DIGIT_THRESHOLD
        total += digit

    return total % 10 == 0
