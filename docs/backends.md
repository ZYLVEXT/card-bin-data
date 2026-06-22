# Backends

`card_bin_data` supports SQLite and PostgreSQL in the MVP through async SQLAlchemy
drivers. A database URL is always explicit.

## URL Requirement

Create a store with `BinDataStore.from_url()`:

```python
from card_bin_data import BinDataStore


store = BinDataStore.from_url("sqlite+aiosqlite:///var/lib/card_bin_data/card_bin_data.db")
```

Accepted drivers:

- `sqlite+aiosqlite`
- `postgresql+asyncpg`

Missing, malformed, or unsupported database URLs raise
`CardBinDataStoreConfigurationError`.

The public API does not read environment variables implicitly. Applications may
read their own configuration and pass the value into `from_url()`.

## SQLite

SQLite is the default local deployment shape for one service or local jobs.

```python
store = BinDataStore.from_url("sqlite+aiosqlite:///var/lib/card_bin_data/card_bin_data.db")
await store.init()
```

Use an absolute file path in production so service restarts keep using the same
database. For tests or temporary examples, a path under a temporary directory is
fine.

## PostgreSQL

PostgreSQL is the server/shared backend for services that should read the same
normalized dataset.

```python
store = BinDataStore.from_url("postgresql+asyncpg://card_bin_data_user@host:5432/card_bin_data")
await store.init()
```

Do not log URLs that include credentials. The example above is a shape example,
not a recommended secret handling pattern.

PostgreSQL integration tests are gated by
`CARD_BIN_DATA_POSTGRESQL_TEST_DATABASE_URL`. When the variable is absent, tests skip
explicitly. When it is present, it must point at a disposable
`postgresql+asyncpg://` database because tests and examples may replace card_bin_data
tables in that database.

## Lifecycle

Call `init()` before the first import or lookup against a fresh database:

```python
await store.init()
await store.import_sources(adapters)
```

`import_sources()` runs a replace-all import inside one store-managed transaction
and delegates to `import_sources_with_session(session, adapters)`.

Use caller-owned sessions when `card_bin_data` work should be part of a larger
SQLAlchemy unit of work:

```python
from card_bin_data import BinData, BinDataStore


async with store.session() as session:
    result = await BinData.lookup_with_session(session, "12345678")

async with store.session_factory.begin() as session:
    summary = await BinDataStore.import_sources_with_session(session, adapters)
```

`lookup()` opens read-only sessions through the store and is safe to share
across async tasks.

## Write Safety

The store does not keep an in-process write lock. Imports are replace-all
operations protected by the active database transaction:

- SQLite connections use a 30 second busy timeout, so overlapping writers wait
  before failing with a lock timeout.
- PostgreSQL uses normal `postgresql+asyncpg` transaction and lock behavior.
- A failed import rolls back through the caller's transaction instead of
  publishing a partial dataset.

Schedule single-writer jobs in the host application when your deployment has
multiple processes, services, or maintenance workers that can import at the
same time.

Close store-owned resources during application shutdown:

```python
await store.close()
```
