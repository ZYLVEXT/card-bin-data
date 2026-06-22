# ruff: noqa: INP001, T201
"""Run a small PostgreSQL card_bin_data import and lookup example."""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
from tempfile import TemporaryDirectory

from card_bin_data import BinData, BinDataStore, LookupStatus
from card_bin_data.sources import BinlistDataAdapter, MarlonlpBinlistDataAdapter, VenelinkochevBinListDataAdapter

POSTGRESQL_URL_ENV = "CARD_BIN_DATA_POSTGRESQL_EXAMPLE_DATABASE_URL"

type SampleSourcePaths = tuple[Path, Path, Path]


async def main() -> None:
    """Import sample CSV rows into a configured PostgreSQL database and look up one IIN.

    Raises:
        RuntimeError: If the imported sample row cannot be looked up.
    """
    database_url = os.environ.get(POSTGRESQL_URL_ENV, "").strip()
    if not database_url:
        print(f"Set {POSTGRESQL_URL_ENV} to run this example against a disposable PostgreSQL database.")
        return

    with TemporaryDirectory(prefix="card_bin_data-postgresql-example-") as temp_dir:
        workspace = Path(temp_dir)
        primary_path, enrichment_path, fallback_path = _write_sample_sources(workspace)
        store = BinDataStore.from_url(database_url)

        try:
            await store.init()
            import_result = await store.import_sources(
                [
                    BinlistDataAdapter(primary_path),
                    VenelinkochevBinListDataAdapter(enrichment_path),
                    MarlonlpBinlistDataAdapter(fallback_path),
                ],
            )

            client = BinData(store=store)
            lookup = await client.lookup("12345678")

            if lookup.status is not LookupStatus.FOUND or lookup.data is None:
                msg = "sample lookup did not find the imported row"
                raise RuntimeError(msg)

            print(f"normalized records: {import_result.normalized_record_count}")
            print(f"status: {lookup.status.value}")
            print(f"scheme: {lookup.data.scheme}")
            print(f"issuer: {lookup.data.issuer_name}")
            print(f"sources: {', '.join(source.source_id for source in lookup.sources)}")
        finally:
            await store.close()


def _write_sample_sources(workspace: Path) -> SampleSourcePaths:
    """Write tiny local CSV files with the same headers as the bundled adapters.

    Returns:
        Paths for the primary, enrichment, and fallback sample source files.
    """
    primary_path = workspace / "ranges.csv"
    primary_path.write_text(
        "iin_start,iin_end,number_length,number_luhn,scheme,brand,type,prepaid,country,bank_name,bank_logo,"
        "bank_url,bank_phone,bank_city\n"
        "12345678,,16,true,visa,Example Platinum,credit,false,US,Example Bank,,"
        "https://bank.example,+15550100,Example City\n",
        encoding="utf-8",
    )

    enrichment_path = workspace / "bin-list-data.csv"
    enrichment_path.write_text(
        "BIN,Brand,Type,Category,Issuer,IssuerPhone,IssuerUrl,isoCode2,isoCode3,CountryName\n"
        "12345678,VISA,CREDIT,PLATINUM,Example Bank,+15550100,https://bank.example,US,USA,"
        "United States\n",
        encoding="utf-8",
    )

    fallback_path = workspace / "binlist-data.csv"
    fallback_path.write_text(
        "bin;brand;type;category;issuer\n12345678;VISA;CREDIT;CLASSIC;Fallback Example Bank\n",
        encoding="utf-8",
    )

    return primary_path, enrichment_path, fallback_path


if __name__ == "__main__":
    asyncio.run(main())
