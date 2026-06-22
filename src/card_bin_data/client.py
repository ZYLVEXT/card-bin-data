"""Public lookup client for card_bin_data."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from .db.services import BinRecordService
from .input import normalize_lookup_input
from .results import LookupResult
from .types import BinInfo, LookupStatus, SourceAttribution

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from .db.models import BinRecordModel
    from .store import BinDataStore


@dataclass(frozen=True, slots=True)
class BinData:
    """Async BIN/IIN lookup client."""

    store: BinDataStore

    async def lookup(self, value: str, *, validate_luhn: bool = False) -> LookupResult:
        """Look up BIN/IIN metadata using a store-managed session.

        Args:
            value: User-supplied BIN/IIN or full PAN-like value.
            validate_luhn: Whether to validate full PAN-like input before lookup.

        Returns:
            Typed lookup result with found, not-found, or invalid status.
        """
        async with self.store.session() as session:
            return await self.lookup_with_session(session, value, validate_luhn=validate_luhn)

    @staticmethod
    async def lookup_with_session(
        session: AsyncSession,
        value: str,
        *,
        validate_luhn: bool = False,
    ) -> LookupResult:
        """Look up BIN/IIN metadata using a caller-supplied async session.

        Args:
            session: Async SQLAlchemy session owned by the caller.
            value: User-supplied BIN/IIN or full PAN-like value.
            validate_luhn: Whether to validate full PAN-like input before lookup.

        Returns:
            Typed lookup result with found, not-found, or invalid status.
        """
        normalized = normalize_lookup_input(value, validate_luhn=validate_luhn)
        if normalized.status is LookupStatus.INVALID:
            return normalized

        record = await BinRecordService(session=session).lookup_record(normalized.query)

        if record is None:
            return LookupResult(
                status=LookupStatus.NOT_FOUND,
                query=normalized.query,
                validation_warnings=normalized.validation_warnings,
            )

        return LookupResult(
            status=LookupStatus.FOUND,
            query=normalized.query,
            data=_bin_info(record),
            validation_warnings=normalized.validation_warnings,
            sources=_source_attributions(record),
        )


def _bin_info(record: BinRecordModel) -> BinInfo:
    return BinInfo(
        iin_start=record.iin_start,
        iin_end=record.iin_end,
        number_length=record.number_length,
        luhn=record.luhn,
        scheme=record.scheme,
        product_brand=record.product_brand,
        type=record.type,
        category=record.category,
        prepaid=record.prepaid,
        country_alpha2=record.country_alpha2,
        country_alpha3=record.country_alpha3,
        country_name=record.country_name,
        issuer_name=record.issuer_name,
        issuer_phone=record.issuer_phone,
        issuer_url=record.issuer_url,
        issuer_city=record.issuer_city,
    )


def _source_attributions(record: BinRecordModel) -> tuple[SourceAttribution, ...]:
    return tuple(
        SourceAttribution(
            source_id=source.data_source.source_id,
            upstream_url=source.data_source.upstream_url,
            license=source.data_source.license,
            imported_at=source.imported_at,
            source_row_key=source.source_row_key,
        )
        for source in record.sources
    )
