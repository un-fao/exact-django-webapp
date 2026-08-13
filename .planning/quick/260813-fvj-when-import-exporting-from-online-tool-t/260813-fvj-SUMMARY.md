---
quick_id: 260813-fvj
type: execute
status: complete
branch: fix/export-import-reference-data-identity
requirements: [D1, D2, D3]
completed: 2026-08-13
duration: ~3h
commits:
  - 6190429f feat(offline) build the offline reference database from fixtures
  - bf7f906d feat(api) declare reference-data natural keys and enforce uniqueness
  - 460acbdd fix(api) resolve reference-data FKs by natural key on project import
tasks: 3
files_changed: 15
actuals:
  tokens: 96000
  tasks: 3
  commits: 3
---

# Quick Task 260813-fvj: Reference-data ID mismatch on export/import

`.exactproject` files now carry a natural key beside every reference primary key
and the importer resolves by that key, so a project moved between installations
whose reference data has drifted either lands on the right rows or fails by name
instead of silently pointing at the wrong climate, soil type or GWP report. The
offline database that caused the drift can now be built from the committed
fixtures and proved equal to them.

## What landed

### Task 1: fixture-based offline bootstrap plus a parity verifier (`6190429f`)

- **`djangoexact/djangoexact/settings.py`** applies the psycopg-only `OPTIONS`
  (`connect_timeout`, `application_name`) only when the resolved engine contains
  `postgresql`. Before this, any sqlite run died with
  `TypeError: 'connect_timeout' is an invalid keyword argument for Connection()`
  before the first query. The GAE branch is untouched and commented as to why:
  its `ENGINE` is the hard `$DB_ENGINE` sed placeholder, never sqlite. Postgres
  options are provably still applied (asserted in verification).
- **`djangoexact/api/reference_parity.py`** is the pure diff: given
  `{pk: identity}` from the fixtures and from the database, it reports `changed`
  (a shared pk naming a different row, the only fatal category), `missing_in_db`
  and `extra_in_db`. No Django import, so it unit-tests with `SimpleTestCase`.
- **`verify_reference_parity`** management command walks the fixtures manifest,
  compares identity per model, prints a summary and exits 1 on drift. `--json`
  supported. Identity is the manifest's `order_by`, enriched with `name` where
  `order_by` is `("id",)` alone (most ipcc entries), which would otherwise
  compare a pk against itself; modeltranslation query rewriting is turned off so
  the comparison reads the same base column the fixture stores.
- **`scripts/build_offline_db.sh`** sequences migrate, load and the parity gate,
  refuses to reuse an existing database file, and prints elapsed time.
- **`docs/guides/offline-db-bootstrap.md`** documents the build, what the gate
  proves, the measured cost, the ordered `release/offline-tool` handoff
  checklist (explicitly not performed) and an `Unconfirmed` section.

**Unplanned but required (deviation, see below): migration 0286 was
PostgreSQL-only.** It embedded a `DO $$ ... $$` PL/pgSQL block, so a fresh
sqlite database could not be migrated at all and the whole bootstrap was
impossible. It is now vendor-dispatched; the PostgreSQL statement is unchanged.

### Task 2: natural keys with database uniqueness behind them (`bf7f906d`)

- **`djangoexact/api/natural_keys.py`** registers 32 reference models reachable
  as a Project, Activity or Module FK. Keys are `name_en` for translated models
  (never the language-sensitive `name` descriptor), `name` for untranslated ones,
  a three-part composite for `api.FuelType`, and `api.Country` carries a
  `COUNTRY_NAME_ALIASES` rename table (`Turkey`, `Bolivia`,
  `China, Hong Kong Special Administrative Region`). Registry membership is the
  gate: unregistered targets get no key and no resolution, which keeps
  `Activity.owner`, `Module.activity` and the cross-module OneToOne refs on their
  existing paths. `ipcc.GlobalWarmingPotential` is registered.
- **`check_reference_natural_keys`** reports duplicate keys and keys whose every
  component is NULL or blank, with model, key value and colliding pks, and exits
  1. `--json` and `--models` supported.
- **18 `UniqueConstraint`s** in `api/migrations/0290_reference_natural_key_constraints.py`
  and `ipcc/migrations/0065_gwp_natural_key_constraint.py`, all on `name_en` or
  `name`, never `unique=True` on a translated field.
- **`api/tests/test_natural_keys.py`**: 31 tests including registry integrity
  (every label resolves, every field path resolves), language independence under
  `override("fr")`, the Country alias, the composite key including its nullable
  member, and the detector driven through `call_command`.

### Task 3: formatVersion 2 dual encoding and resolve-on-import (`460acbdd`)

- **Export** emits `<field>__nk` beside every registered reference integer, from
  inside `ModuleExportSerializer`'s `_meta.get_fields()` loop (so every MTI
  subclass is covered without per-model registration), memoised per activity.
  `ProjectExportSerializer` does the same for the six project reference fields,
  taking the model from the field rather than the name. `ActivityExportSerializer`
  adds `module_types__nk`. Envelope `formatVersion` is 2; `compatibilityGroup`
  stays 1.
- **Import** resolves `<field>__nk` in `prepare_model_data` and lets an
  unresolvable key raise. It never falls back to the integer when a key is
  present. `resolve_status_id` takes the key too, because `_extract_cache_restore`
  pops `status` before `prepare_model_data` sees it; its docstring no longer
  asserts that reference PKs are stable across installations. `module_types`
  resolve before `.set()`. `UnresolvableNaturalKeyError` returns 400 with its own
  named message ahead of the blanket handler, inside `transaction.atomic`.
- **Tests**: skew both ways (integer pointing at a nonexistent row, and integer
  pointing at a *different existing* row), the hard failure with no Project left
  behind, per-field fallback, v1 regression, the Country rename, and a full
  export/import round trip asserting all six reference FKs.

## Evidence

| Check | Result |
| --- | --- |
| `py_compile` over every changed Python file | pass |
| `makemigrations --check --dry-run` | clean, exit 0 |
| sqlite connection opens without TypeError | `sqlite-connect-ok` |
| Postgres `OPTIONS` still applied when engine is postgresql | `postgres-options-preserved` |
| `bash scripts/build_offline_db.sh $SP/final.sqlite3` | **exit 0, 20m 29s, 52 MB** |
| `verify_reference_parity --app=all` on that database | **162/162 ok, exit 0** |
| `load_reference_data --app=all` with the new constraints applied | 162 fixtures loaded, 0 failures |
| `check_reference_natural_keys` on that database | clean, exit 0 |
| `check_reference_natural_keys` on the shipped offline snapshot | **exit 1, see below** |
| `test_natural_keys` + `test_reference_parity` + `ProjectImportNaturalKeyTests` | **49 tests, OK** |
| `compatibilityGroup` in version.config.json | still 1 |
| `git diff develop --stat` touching `math_model/` or `calculators.py` | none |
| `.planning/STATE.md` and `scripts/ipcc_dump.py` | still unstaged, untouched |
| branch | `fix/export-import-reference-data-identity` throughout |

The verifier independently reproduced the research finding against the shipped
`release/offline-tool:djangoexact/db.sqlite3`: **83 of 162 models differ**
(8 with fatal semantic drift, 82 with row-set differences, 79 clean), including
the `pk=50 fixture='Annual Cropland Minor Season' db='Plantation'` collision that
`fixtures-guide.md` uses as its illustration of a PK-stability violation.

## The duplicate gate tripped: `api.Unit`

Run against both datasets **before any constraint was added**. Full output in
`260813-fvj-DUPLICATES.md`.

- **Committed fixtures: clean.** Checked twice, once constraint-free directly
  against the fixture JSON (32 models, all keys distinct, `LandUseType` 211/211)
  and once against the database built from them.
- **Shipped offline database: 4 findings, all `api.Unit`.** 46 rows named
  `m3/yr`, 12 named `tdm/yr`, 8 named `MWh/yr` and 100 with a blank name, against
  3 rows in `api/fixtures/unit.json`.

**Action taken: none on the data.** `api.Unit` received no `UniqueConstraint`, no
row was deduped, renamed, merged or deleted. `api.Unit` stays in the registry,
annotated, which is inert: its only ForeignKey anywhere in the model layer is
`FuelType.unit` (`api/models.py:596`), reference data pointing at reference data,
so no `.exactproject` payload ever carries a `unit__nk` to resolve.

**Open for the data owner:** decide what those 166 offline `Unit` rows are. The
100 blank-named ones look like an abandoned import. That is a data decision and
was deliberately not taken here.

## Deviations from plan

**1. [Rule 3 - Blocking] Migration 0286 was PostgreSQL-only.** Found during task
1's end-to-end run, which died at
`sqlite3.OperationalError: near "DO": syntax error` after 21 minutes of
migrations. `0286_historicalprocessingentry_fuel_type_thread` embedded a
`DO $$ ... $$` PL/pgSQL block, so no sqlite database could ever be migrated and
the entire fixture-based bootstrap was impossible. Replaced the single `RunSQL`
with a vendor-dispatching `RunPython`: the PostgreSQL branch executes the
original statement verbatim, other backends get the same effect through plain
SQL guarded by introspection. It is the only Postgres-only migration in the repo
(grepped). Committed with task 1.

**2. [Rule 3 - Blocking] The constraints migration also picked up unrelated
pre-existing drift.** `makemigrations` generated four `AlterField` operations on
`ef_source` for the fishery models: migration 0286 created the field as
`ef_source_t2` with `verbose_name='ef_source_t2'` and 0288 renamed the field
without touching the verbose_name. The plan requires the constraints migration to
contain only `AddConstraint`, so the generated operations were split verbatim
into `0291_alter_fishery_ef_source_verbose_name.py`. Metadata only, no SQL.
Committed with task 2.

**3. [Scope] `api.Unit` constraint withheld.** Documented above and in
`260813-fvj-DUPLICATES.md`. 18 constraints instead of the planned 19.

**4. [Rule 3 - Blocking] `whitenoise==6.12.0` installed into the local venv.**
It is pinned in the repo's own `djangoexact/requirements.txt` but was missing
locally, and its middleware is unconditional, so every API-client test raised
`ModuleNotFoundError`. Installed exactly the committed pin. No repo file changed.

**5. [Rule 3 - Blocking] The new test class disables minitool middleware.**
`minitool.middleware.DatabaseConnectionMiddleware` calls `connections.close_all()`
after every response, which destroys the transaction Django's `TestCase` wraps
each test in, so every subsequent query raises "Cannot operate on a closed
database". `ProjectImportNaturalKeyTests` is decorated with `override_settings`
excluding it. Scoped to the new class; no shared infrastructure changed.

## Pre-existing breakage found and NOT fixed

Proved against an unmodified HEAD worktree (with only the task 1 settings fix
applied, since without it HEAD cannot open a sqlite connection at all):
`api.tests.test_project_export` at HEAD runs **22 tests with 21 errors and 1
failure. Zero passing.** Three independent causes, all pre-existing:

1. **24 x `Cannot operate on a closed database`** - the minitool middleware issue
   above. Affects every `TestCase` in the repo that drives the API client.
2. **15 x `NOT NULL constraint failed: api_project.country_id`** - `ProjectFactory`
   (`api/tests/factories.py:86`) never sets `country`, which is NOT NULL on
   `Project`. The line exists but is commented out.
3. **2 x `cannot import name 'GlobalWarmingPotential' from 'api.models'`** -
   broken import in `ThreadCommentExportImportTests.setUp`.

Out of scope per the plan's scope boundary, so left alone. The consequence is
that **`test_project_export` as a whole still does not pass**, and only the new
`ProjectImportNaturalKeyTests` class within it does (9/9). The two pre-existing
causes that would have hit the new class were worked around inside that class
only. Fixing causes 1 to 3 would unblock roughly 22 existing tests and is worth
a follow-up task.

Also noted: `api/tests/factories.py` executes ORM queries at module import time,
so the whole test package requires a seeded database to import at all.

## Carried forward

**Measured cost of a sqlite bootstrap: 20m 29s** end to end on a developer
laptop (Python 3.11, no Docker), producing a 52 MB database. Essentially all of
it is `migrate`: roughly 290 migrations plus the table rebuilds that
`simple_history` and sqlite's ALTER TABLE emulation force. `load_reference_data`
and `verify_reference_parity` are seconds by comparison. Packaging owners should
budget this per build, or cache when the fixture and migration sets are unchanged.

**`release/offline-tool` handoff steps remain unperformed.** No branch was
switched. The ordered checklist lives in
`djangoexact/docs/guides/offline-db-bootstrap.md`: measure the shipped snapshot
with `verify_reference_parity` first, `git rm --cached djangoexact/db.sqlite3`,
generate at package time from the same commit as the online deployment, gate
packaging on the parity command exiting 0, and confirm the offline `.env` sets a
sqlite engine (which needs the settings.py change merged down).

**The packaging mechanism is still unconfirmed.** Verified this session on that
branch: `settings_offline.py` only strips the `minitool` and `admin_scripts`
apps, pops the `minitool` DB alias and swaps `ROOT_URLCONF`; it says nothing
about database provisioning. No `.env` is committed there. No packaging script,
Dockerfile or installer spec in the repository consumes `db.sqlite3`. Steps 3 to
5 cannot be written as concrete commands until the owner of that step describes
it. The doc is written as the request for that confirmation.

**The uniqueness migration is unvalidated against production** (research
assumption A3). `LandUseType` name uniqueness is proven for the 211 committed
fixture rows and the 77 offline rows only. Before deploying `0290`:

```bash
cloud-sql-proxy <INSTANCE_CONNECTION_NAME> &
DB_ENGINE=django.db.backends.postgresql DB_HOST=127.0.0.1 DB_PORT=5432 \
DB_NAME=<db> DB_USER=<user> DB_PASSWORD=<pw> \
  python manage.py check_reference_natural_keys
```

A duplicate `name_en` in production would fail the migration at deploy time.

**The number of `.exactproject` files already in the wild from offline builds is
still unknown** (research open question 3). Those files are `formatVersion: 1`,
carry no natural keys, and keep importing by integer pk, so they will keep
mis-resolving wherever reference data has drifted. Nothing in this change fixes
them. Only re-exporting them from a repaired offline build does.

**Note on `nulls_distinct=False`** on the `api.FuelType` composite constraint:
honoured on PostgreSQL 15+, silently ignored on sqlite, which treats NULLs as
distinct and therefore enforces less locally than in production. Django emits
`models.W047` about this on sqlite; it is a warning, not an error, and does not
affect `check --deploy`.

## Self-Check: PASSED

Files verified present:

- `djangoexact/api/reference_parity.py`, `djangoexact/api/natural_keys.py`
- `djangoexact/api/management/commands/verify_reference_parity.py`
- `djangoexact/api/management/commands/check_reference_natural_keys.py`
- `djangoexact/scripts/build_offline_db.sh` (executable)
- `djangoexact/docs/guides/offline-db-bootstrap.md`
- `djangoexact/api/migrations/0290_reference_natural_key_constraints.py`
- `djangoexact/api/migrations/0291_alter_fishery_ef_source_verbose_name.py`
- `djangoexact/ipcc/migrations/0065_gwp_natural_key_constraint.py`
- `djangoexact/api/tests/test_reference_parity.py`, `djangoexact/api/tests/test_natural_keys.py`

Commits verified in `git log`: `6190429f`, `bf7f906d`, `460acbdd`.
