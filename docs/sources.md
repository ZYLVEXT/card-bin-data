# Sources

The MVP imports local CSV files from repository submodules. It does not download
datasets, update git submodules, or call upstream APIs.

## Source Priority

Merge priority is deterministic:

1. `binlist/data`: primary source.
2. `venelinkochev/bin-list-data`: enrichment source.
3. `marlonlp/binlist-data`: fallback source.

`binlist/data` wins for primary network, type, range, number length, Luhn, and
product-brand fields. `venelinkochev/bin-list-data` enriches issuer, country,
phone, URL, and category fields. `marlonlp/binlist-data` fills remaining missing
values as fallback.

All contributing source rows are stored as provenance and returned as
`SourceAttribution` values for found lookups.

## Bundled Adapters

### `BinlistDataAdapter`

- Source id: `binlist/data`
- Upstream: `https://github.com/binlist/data.git`
- Default file: `datasets/binlist_data/ranges.csv`
- Delimiter: comma
- Key fields: `iin_start`, `iin_end`, `number_length`, `number_luhn`,
  `scheme`, `brand`, `type`, `prepaid`, `country`, `bank_name`, `bank_url`,
  `bank_phone`, `bank_city`

Normalization notes:

- `scheme` maps to public `scheme`.
- `brand` maps to public `product_brand`.
- `country` maps to `country_alpha2`.
- Numeric range data maps to `iin_start` and `iin_end`.

### `VenelinkochevBinListDataAdapter`

- Source id: `venelinkochev/bin-list-data`
- Upstream: `https://github.com/venelinkochev/bin-list-data.git`
- Default file: `datasets/venelinkochev_binlist_data/bin-list-data.csv`
- License: CC BY 4.0 according to the upstream repository README/LICENSE.
- Delimiter: comma
- Key fields: `BIN`, `Brand`, `Type`, `Category`, `Issuer`, `IssuerPhone`,
  `IssuerUrl`, `isoCode2`, `isoCode3`, `CountryName`

Normalization notes:

- `Brand` maps to public `scheme`.
- `Issuer`, phone, URL, and country fields enrich records with the same
  `iin_start`.

### `MarlonlpBinlistDataAdapter`

- Source id: `marlonlp/binlist-data`
- Upstream: `https://github.com/marlonlp/binlist-data.git`
- Default file: `datasets/marlonlp_binlist_data/binlist-data.csv`
- License: CC BY 4.0 according to the upstream repository README/license.
- Delimiter: semicolon
- Key fields: `bin`, `brand`, `type`, `category`, `issuer`

Normalization notes:

- `brand` maps to public `scheme`.
- `issuer` fills `issuer_name` when higher-priority sources do not provide it.

## Import Example

```python
from pathlib import Path

from card_bin_data.sources import (
    BinlistDataAdapter,
    MarlonlpBinlistDataAdapter,
    VenelinkochevBinListDataAdapter,
)


adapters = [
    BinlistDataAdapter(Path("datasets/binlist_data/ranges.csv")),
    VenelinkochevBinListDataAdapter(Path("datasets/venelinkochev_binlist_data/bin-list-data.csv")),
    MarlonlpBinlistDataAdapter(Path("datasets/marlonlp_binlist_data/binlist-data.csv")),
]

summary = await store.import_sources(adapters)
```

`summary.source_record_count` is the number of normalized rows emitted by the
adapters. `summary.normalized_record_count` is the merged record count.
`summary.provenance_record_count` is the stored source-row attribution count.

## Extending Sources

To add a source, implement `SourceAdapter` and emit `NormalizedSourceRecord`
values:

```python
from collections.abc import AsyncIterator

from card_bin_data import NormalizedSourceRecord, SourceMetadata


class ExampleAdapter:
    @property
    def metadata(self) -> SourceMetadata:
        return SourceMetadata(
            source_id="example/source",
            display_name="example/source",
            upstream_url="https://example.invalid/source",
            license=None,
        )

    async def iter_records(self) -> AsyncIterator[NormalizedSourceRecord]:
        yield NormalizedSourceRecord(
            source=self.metadata,
            row_key="example:1:12345678",
            iin_start="12345678",
            scheme="visa",
        )
```

Adapter responsibilities:

- Read one local source format.
- Preserve row identity through `row_key`.
- Preserve useful raw payload data.
- Emit normalized records with empty fields converted to `None`.
- Preserve leading zeros in BIN/IIN strings.

Adapter non-responsibilities:

- Database writes.
- Cross-source conflict resolution.
- Lookup behavior.
- Network or git updates.

Adding a new source should not require changing lookup logic.

## Data Quality And Licenses

The public datasets are unofficial. They may be stale, incomplete, or
contradict each other. `card_bin_data` preserves source attribution but does not make
official correctness claims.

The final `binlist/data` license statement must be verified before public
release documentation claims are finalized. Keep attribution for CC BY 4.0
sources when publishing datasets or derived documentation.
