# API

## Public Package Exports

The top-level `card_bin_data` package exports the lookup client, store, typed result
models, source metadata models, and card_bin_data-specific exceptions:

- `BinData`
- `BinDataStore`
- `LookupResult`
- `LookupStatus`
- `LookupQuery`
- `BinInfo`
- `SourceMetadata`
- `SourceAttribution`
- `NormalizedSourceRecord`
- `CardBinDataError`
- `CardBinDataStoreConfigurationError`

Source adapters are exported from `card_bin_data.sources`.

## `BinData`

`BinData` is the read-only async lookup client. Its default `lookup()` method
opens a store-managed session. `lookup_with_session()` is available when the
host application already owns an `AsyncSession`.

```python
from card_bin_data import BinData, BinDataStore


store = BinDataStore.from_url("sqlite+aiosqlite:///var/lib/card_bin_data/card_bin_data.db")
client = BinData(store=store)
result = await client.lookup("12345678")

async with store.session() as session:
    result = await BinData.lookup_with_session(session, "12345678")
```

`lookup(value: str, *, validate_luhn: bool = False)` accepts:

- 6-digit BIN/IIN input.
- 8-digit BIN/IIN input.
- Full card-number-like input.
- Input containing spaces or hyphens.

`lookup()` never raises for found, not-found, or invalid-input outcomes. Those
are represented by `LookupResult.status`.

## `LookupResult`

`LookupResult` is immutable and contains only safe normalized lookup data:

- `status`: `LookupStatus.FOUND`, `LookupStatus.NOT_FOUND`, or
  `LookupStatus.INVALID`.
- `query`: safe `LookupQuery` with prefix candidates.
- `data`: `BinInfo` for found results, otherwise `None`.
- `validation_warnings`: tuple of validation warning strings.
- `sources`: source attribution for found results.

Convenience properties:

- `found`
- `not_found`
- `invalid`

```python
from card_bin_data import LookupStatus


result = await client.lookup("12345678")

if result.status is LookupStatus.FOUND and result.data is not None:
    issuer = result.data.issuer_name
elif result.invalid:
    warnings = result.validation_warnings
```

## `LookupQuery`

`LookupQuery` is the safe representation of caller input after normalization:

- `prefix`: the first lookup candidate.
- `candidates`: lookup candidates in priority order, usually 8-digit then
  6-digit for long input.
- `is_full_pan_input`: whether the original input length looked like a full
  card number.

It does not contain the original caller-provided value.

## `BinInfo`

`BinInfo` contains normalized BIN/IIN metadata:

- `iin_start`
- `iin_end`
- `number_length`
- `luhn`
- `scheme`
- `product_brand`
- `type`
- `category`
- `prepaid`
- `country_alpha2`
- `country_alpha3`
- `country_name`
- `issuer_name`
- `issuer_phone`
- `issuer_url`
- `issuer_city`

Unknown and empty source values are represented as `None`.

## `BinDataStore`

`BinDataStore` owns database configuration, schema lifecycle, source import,
and store-managed transaction helpers.

```python
store = BinDataStore.from_url("sqlite+aiosqlite:///var/lib/card_bin_data/card_bin_data.db")
await store.init()
summary = await store.import_sources(adapters, store_raw_payload=False)
await store.close()
```

Important methods and properties:

- `from_url(database_url)`: validates an explicit async SQLAlchemy URL.
- `init()`: creates card_bin_data tables.
- `import_sources(adapters, *, store_raw_payload=True)`: imports adapter
  records inside one store-managed transaction.
- `import_sources_with_session(session, adapters, *, store_raw_payload=True)`:
  imports adapter records inside the caller-supplied `AsyncSession` and
  transaction.
- `session()`: opens a store-managed async SQLAlchemy session.
- `close()`: disposes store-owned database resources.
- `database_url`: returns the configured URL string with passwords masked.

Supported URL drivers:

- `sqlite+aiosqlite`
- `postgresql+asyncpg`

## Import Summary

`import_sources()` returns `ImportResult`:

- `source_record_count`
- `normalized_record_count`
- `provenance_record_count`

The current import path replaces the imported normalized dataset in one
transaction.

`store_raw_payload=True` preserves the full raw adapter row in
`bin_record_sources.raw_payload`. Set `store_raw_payload=False` to persist `{}`
for every provenance row while still writing `source_row_key` and data-source
attribution. This avoids storing full source rows without changing normalized
records, merge behavior, or lookup results.

## Persistence Foundation And Write Contract

Persistence is implemented through Advanced Alchemy repository/service classes:

- `DataSourceService`
- `BinRecordService`
- `BinRecordSourceService`
- `ImportedRecordsService`

`DataSourceService` and `BinRecordSourceService` are intentional low-level
extension points for applications or tests that need direct CRUD access to
source metadata or provenance rows through the same caller-owned
`AsyncSession`. They are part of the `card_bin_data.db` public surface, but normal
lookup and import integrations should use `BinData`, `BinDataStore`, and source
adapters instead of composing these services directly.

The public lookup path uses `BinRecordService.lookup_record()`. The import path
uses `ImportedRecordsService.replace_all()` inside the active transaction.
Services are bound to a caller-supplied SQLAlchemy `AsyncSession`; they do not
own hidden transaction boundaries.

`BinDataStore` does not provide a store-level write lock; concurrent writer
behavior is delegated to the database.
SQLite stores are created with a 30 second busy timeout so overlapping writers
wait before failing. PostgreSQL uses normal `postgresql+asyncpg` transaction
and locking behavior. Applications that require single-writer scheduling across
processes or services should enforce it outside `card_bin_data`.

## Source Adapter Protocol

Source adapters implement `SourceAdapter`:

```python
from collections.abc import AsyncIterator
from typing import Protocol

from card_bin_data import NormalizedSourceRecord, SourceMetadata


class SourceAdapter(Protocol):
    @property
    def metadata(self) -> SourceMetadata: ...

    def iter_records(self) -> AsyncIterator[NormalizedSourceRecord]: ...
```

Bundled adapters:

- `BinlistDataAdapter`
- `VenelinkochevBinListDataAdapter`
- `MarlonlpBinlistDataAdapter`

Adapters parse one local source format and emit `NormalizedSourceRecord`
objects. They do not write to the database, resolve cross-source conflicts, or
perform network/git updates.
