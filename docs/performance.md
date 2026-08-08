# Performance

`card_bin_data` separates read lookup from dataset import/update. The lookup path is
designed for service traffic; the import path is a maintenance operation.

## Lookup Path

`BinData.lookup()` normalizes input, opens a store-managed async SQLAlchemy
session, and asks `BinRecordService` for the best matching normalized record.
Use `BinData.lookup_with_session(session, value, validate_luhn=...)` when a
host application already owns the `AsyncSession`.

The package root defers the database-backed `BinData` and `BinDataStore`
facades. Importing metadata, exceptions, or result types does not initialize
SQLAlchemy or either async database driver.

Lookup priority:

1. Exact 8-digit match.
2. Range match using `iin_start` and `iin_end`.
3. Exact 6-digit match.

All three priorities are expressed in one ranked SQL statement. A valid lookup,
including a not-found result, therefore uses one database round-trip while
collection eager loading returns source attribution in that same statement.
The query uses indexed database columns and never loads the full dataset into
memory.

## SQLite Target

The PRD target for local warm SQLite lookup is p95 under 1 ms. Treat that as a
target, not a published benchmark claim, until a benchmark suite is added.

For best SQLite behavior:

- Use a local file path, not a network filesystem.
- Reuse one `BinDataStore` and one `BinData` client per service process.
- Initialize and import the database before serving traffic.
- Close the store during application shutdown.

## PostgreSQL Target

PostgreSQL is intended for shared/server deployments. Lookup latency depends on
network distance, server load, and connection-pool behavior from SQLAlchemy.

Use PostgreSQL when multiple services need the same normalized dataset or when
operational backup/replication matters more than embedded deployment
simplicity.

## Import And Update Cost

Import/update is transactional and replace-style. It collects normalized source
records, merges them by `iin_start`, stores normalized records, and stores
source provenance.

The built-in CSV adapters parse on worker threads in bounded batches. The import
pipeline writes those batches to a private, temporary, on-disk SQLite staging
table, reads them back in indexed `iin_start` order, and merges only the current
prefix family in memory. Final records and provenance are inserted into the
configured backend in bounded batches. The temporary stage is closed and
removed whether the import succeeds or fails.

Expect import/update to be more expensive than lookup:

- It may take seconds on current public datasets.
- Its memory use is bounded by batch size and the active duplicate/prefix group,
  rather than by the total source dataset size.
- It writes the full imported dataset and provenance rows.

Run imports outside latency-sensitive request paths.

`BinDataStore.import_sources()` uses a replace-all import path. The store-managed
method opens one transaction and calls `import_sources_with_session(session,
adapters)`, which in turn uses `ImportedRecordsService.replace_all()`.

## Concurrency

`lookup()` is read-only and task-safe. `init()` and `import_sources()` do not
use a store-level write lock.

During an update, rollback should leave readers with the previous complete
dataset rather than a partially imported dataset. Concurrent writer behavior is
controlled by the database: SQLite stores use a 30 second busy timeout so a
second writer waits before failing, while PostgreSQL uses normal transactional
locking. Host applications should schedule single-writer imports when they need
cross-process or cross-service coordination.
