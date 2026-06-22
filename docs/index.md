# card_bin_data Documentation

`card_bin_data` provides async BIN/IIN lookup for Python 3.12+ services. It imports
local public CSV datasets into a normalized SQLite or PostgreSQL database, then
serves typed lookup results through `BinData.lookup()`.

## MVP Scope

Implemented MVP surfaces:

- Typed public lookup client: `BinData`.
- Explicit store lifecycle: `BinDataStore.from_url()`, `init()`,
  `import_sources()`, and `close()`.
- SQLite via `sqlite+aiosqlite`.
- PostgreSQL via `postgresql+asyncpg`.
- Local CSV source adapters for the three bundled dataset submodules.
- Deterministic merge priority and source attribution.
- Prefix-only full card-number handling with optional Luhn validation.

Post-MVP surfaces:

- CLI commands.
- Network downloads or git update logic inside the library.
- Official card validation service behavior.
- Confidence scoring or cache layers.

## Basic Flow

```python
from pathlib import Path

from card_bin_data import BinData, BinDataStore
from card_bin_data.sources import (
    BinlistDataAdapter,
    MarlonlpBinlistDataAdapter,
    VenelinkochevBinListDataAdapter,
)


store = BinDataStore.from_url("sqlite+aiosqlite:///var/lib/card_bin_data/card_bin_data.db")
await store.init()
await store.import_sources(
    [
        BinlistDataAdapter(Path("datasets/binlist_data/ranges.csv")),
        VenelinkochevBinListDataAdapter(Path("datasets/venelinkochev_binlist_data/bin-list-data.csv")),
        MarlonlpBinlistDataAdapter(Path("datasets/marlonlp_binlist_data/binlist-data.csv")),
    ],
)

client = BinData(store=store)
result = await client.lookup("12345678")
```

The database URL is required. `card_bin_data` does not silently choose a database
file or read environment variables for you.

## Data Caveat

The bundled public datasets are unofficial community datasets. They can be
incomplete, stale, or internally inconsistent. `card_bin_data` preserves source
attribution so consumers can inspect provenance, but it does not guarantee
official issuer correctness.

## Pages

- [API](api.md)
- [Backends](backends.md)
- [Sources](sources.md)
- [Security](security.md)
- [Performance](performance.md)
