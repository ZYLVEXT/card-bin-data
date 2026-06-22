# Security

`card_bin_data` is designed to look up BIN/IIN metadata without retaining full card
numbers. It is not a PCI validator, payment authorization component, or official
card-data authority.

## Full Card-Number Handling

`BinData.lookup()` accepts full card-number-like input for caller convenience.
The normalization path:

1. Removes spaces and hyphens.
2. Rejects non-numeric input.
3. Accepts 6-digit BINs, 8-digit IINs, and 12-19 digit full-card-number-like
   input.
4. Builds safe lookup candidates from prefixes only.
5. Returns a `LookupResult` that does not include the original input.

Do not log caller input before passing it into `lookup()`.

## Luhn Validation

Luhn validation is disabled by default:

```python
result = await client.lookup(card_number_from_user)
```

Enable it only when the caller is intentionally passing full-card-number-like
input:

```python
result = await client.lookup(card_number_from_user, validate_luhn=True)
```

If Luhn validation is requested for short BIN/IIN input, `lookup()` returns a
warning in `validation_warnings` instead of raising. A failed full input Luhn
check returns `LookupStatus.INVALID`.

Luhn validation is not proof that a card exists, is active, or may be charged.

## Storage

The card_bin_data schema stores normalized prefixes and source provenance:

- `iin_start`
- `iin_end`
- normalized metadata
- source ids
- source row keys
- raw source payloads

It does not have a full-card-number column.

## Results And Exceptions

Found, not-found, and invalid input are returned as typed result statuses.
Validation warnings contain generic messages and do not echo raw input.

Application code should still treat these values carefully:

- Do not log raw user input.
- Do not log credential-bearing database URLs.
- Do not include source raw payloads in user-visible responses unless your
  product has reviewed that data exposure.

## Database URLs

`BinDataStore.from_url()` requires an explicit URL. Applications may read that
URL from their own configuration system, but `card_bin_data` does not read an
environment variable implicitly.

For PostgreSQL, use your normal secret-management mechanism and pass the value
into `from_url()`. `store.database_url` masks passwords for display; application
configuration should still treat the original URL as a secret.

## Deployment Hardening

These controls live in deployment and CI configuration, not in library code:

- **Transport security.** `card_bin_data` does not force TLS on the database
  connection. For PostgreSQL, require it in the URL you pass to `from_url()`
  (for example `...?ssl=verify-full`) so credentials and query traffic are
  encrypted in transit.
- **Schema management.** `BinDataStore.init()` runs `create_all` and is intended
  for local, dev, and test databases. For production PostgreSQL, manage schema
  with reviewed migrations (Alembic) rather than runtime DDL.
- **Dependency scanning.** `pip-audit` is included as a development dependency;
  run it in CI so the build fails on a known-vulnerable dependency.
- **Source-data trust.** Adapters read whatever local CSV path they are given.
  CSV rows are streamed in bounded batches and import uses on-disk SQLite
  staging, but paths should still point only at trusted dataset files; do not
  construct adapter paths from untrusted input.

## Public Dataset Risk

The datasets are unofficial and may be stale or inaccurate. Preserve
attribution when publishing documentation or derived outputs. The
`venelinkochev` and `marlonlp` sources are documented as CC BY 4.0 by their
upstream repositories. The final `binlist/data` license statement must be
verified before public release claims are finalized.
