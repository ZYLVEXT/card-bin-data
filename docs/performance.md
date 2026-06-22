# Performance

`card_bin_data` separates read lookup from dataset import/update. The lookup path is
designed for service traffic; the import path is a maintenance operation.

## Lookup Path

`BinData.lookup()` normalizes input, opens a store-managed async SQLAlchemy
session, and asks `BinRecordService` for the best matching normalized record.
Use `BinData.lookup_with_session(session, value, validate_luhn=...)` when a
host application already owns the `AsyncSession`.

Lookup priority:

1. Exact 8-digit match.
2. Range match using `iin_start` and `iin_end`.
3. Exact 6-digit match.

The query path uses indexed database columns and does not load the full dataset
into memory for each request.

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

The current CSV adapter interface is async for consistency with the import
pipeline, but it is not end-to-end row streaming. Each built-in CSV adapter reads
and normalizes its local file on a worker thread, materializes that adapter's
records, then yields those records through `iter_records()`. The importer then
collects all adapter records into one tuple before merge and persistence, and
the merge step groups records by `iin_start` in memory.

Expect import/update to be more expensive than lookup:

- It may take seconds on current public datasets.
- It needs enough memory for the normalized adapter rows, merge groups, and
  provenance rows during the import step.
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
