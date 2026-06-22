# ruff: noqa: INP001, T201
"""Run a small SQLite card_bin_data import and lookup example."""

from __future__ import annotations

import asyncio
from pathlib import Path
from tempfile import TemporaryDirectory

from card_bin_data import BinData, BinDataStore, LookupStatus
from card_bin_data.sources import BinlistDataAdapter, MarlonlpBinlistDataAdapter, VenelinkochevBinListDataAdapter

type SampleSourcePaths = tuple[Path, Path, Path]


async def main() -> None:
    """Create a temporary SQLite store, import sample CSV rows, and look up one IIN.

    Raises:
        RuntimeError: If the imported sample row cannot be looked up.
    """
    with TemporaryDirectory(prefix="card_bin_data-sqlite-example-") as temp_dir:
        workspace = Path(temp_dir)
        primary_path, enrichment_path, fallback_path = _write_sample_sources(workspace)
        database_path = workspace / "card_bin_data.sqlite3"
        store = BinDataStore.from_url(f"sqlite+aiosqlite:///{database_path}")

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
