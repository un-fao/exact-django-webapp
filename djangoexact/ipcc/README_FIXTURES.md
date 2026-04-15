# Reference Data Fixtures

All reference data for the `api` and `ipcc` apps (Types, Countries, Regions, IPCC tables, etc.) is managed by a single unified pipeline:

- `api/fixtures_manifest.py` — the canonical list of reference models in dependency order
- `python manage.py dump_reference_data` — database → fixture files
- `python manage.py load_reference_data` — fixture files → database
- `api/tests/test_reference_bootstrap.py` — round-trip test (load then dump must match committed bytes)

The database is the source of truth. Committed JSON fixtures under `api/fixtures/` and `ipcc/fixtures/` are derived artifacts — regenerate them with `dump_reference_data` rather than editing by hand.

## Bootstrap a fresh database

```bash
python manage.py migrate
python manage.py load_reference_data --app=all
```

That's it. The manifest's ordering handles every FK dependency (api before ipcc, regions before countries, `GlobalWarmingPotential` before anything that needs it, etc.).

## Dump the current database to fixtures

```bash
# Full dump from the canonical dev DB
python manage.py dump_reference_data --app=all

# Dry run — print what would be written without touching disk
python manage.py dump_reference_data --app=all --dry-run

# Restrict to a subset
python manage.py dump_reference_data --models api.Country,api.Climate

# Just one app
python manage.py dump_reference_data --app=api
```

### PK stability guardrail

`dump_reference_data` refuses to overwrite a fixture if an existing PK now maps to a different row (e.g. pk=50 used to be `Plantation` and is now `Annual Cropland`). Renumbering existing PKs silently breaks every FK in the database, so the command stops and prints a diff.

Two ways to resolve a violation:

1. **Legitimate rename** — the row at that PK really did change name (e.g. `Turkey` → `Türkiye`). Pass `--force` to accept the new content:
   ```bash
   python manage.py dump_reference_data --app=all --force
   ```
2. **Actual PK drift** — the row *content* at that PK now belongs to a different semantic entity. Don't force. Investigate the migration or import that caused it.

The guardrail only fires when existing PKs change meaning. Adding new rows is always allowed; removing rows prints a warning but does not fail.

### Determinism

Two dumps run back-to-back against the same database must produce byte-identical output. Row order is controlled by each manifest entry's `order_by` field; M2M value lists are canonicalized to ascending PK order by the dump command. If a second dump shows a diff in `git status`, something in the pipeline is non-deterministic — file a bug.

## Load fixtures into a database

```bash
# Load all committed fixtures in manifest order
python manage.py load_reference_data --app=all

# Restrict
python manage.py load_reference_data --models api.Country,api.Climate
python manage.py load_reference_data --app=ipcc

# Dry run — print the ordered list of fixtures without hitting the DB
python manage.py load_reference_data --app=all --dry-run

# Verify round-trip after loading: dump to a temp dir and diff against committed
python manage.py load_reference_data --app=all --verify

# Keep going if one fixture fails (default is abort)
python manage.py load_reference_data --app=all --continue-on-error

# Truncate reference tables before loading (destructive, requires --yes)
python manage.py load_reference_data --app=all --clean-slate --yes
```

The command pre-flights by verifying every fixture referenced by the manifest exists on disk, so it fails fast instead of leaving a half-loaded database.

## Round-trip test

```bash
python manage.py test api.tests.test_reference_bootstrap --keepdb
```

Three assertions:

1. Every manifest entry has a committed fixture on disk.
2. Loading the fixtures produces the same row counts committed.
3. Dumping after load yields byte-identical fixtures.

Run `--keepdb` locally to avoid the ~30s cost of recreating the test DB each run. This test is the executable guarantee that a fresh clone plus `load_reference_data` is enough to boot the app.

## Adding a new reference model

1. Add an entry to `api/fixtures_manifest.py`:
   ```python
   ReferenceModelSpec(
       model="api.NewType",
       order_by=("name",),     # must produce stable ordering
       fixture_file="newtype.json",
       category="management",
       app="api",
   ),
   ```
   Position it after every model it depends on (FK parents first).
2. Run `python manage.py dump_reference_data --models api.NewType`.
3. Commit the new entry, the new fixture file, and run the round-trip test.

Pick `order_by` carefully: it must be deterministic across environments. `("name",)` is fine when `name` is unique; otherwise add a tiebreaker (`("name", "id")` or a composite key). If the model has M2M fields, they are canonicalized automatically — no extra work needed.

## The BOM duplicate runscript

`scripts/fix_bom_country_duplicates.py` — repoints FKs from BOM-prefixed `Country` duplicates onto their clean counterparts, then deletes the duplicates. Dry-run by default.

```bash
python manage.py runscript fix_bom_country_duplicates
python manage.py runscript fix_bom_country_duplicates --script-args=--apply
```

Kept around because the underlying CSV import bug can recur when bootstrapping new environments from historical data.
