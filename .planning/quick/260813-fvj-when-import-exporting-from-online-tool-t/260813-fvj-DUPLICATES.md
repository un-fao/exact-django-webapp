# 260813-fvj: natural-key duplicate gate output

**Run:** 2026-08-13, task 2 step 2c, **before any UniqueConstraint was added**.
**Command:** `python manage.py check_reference_natural_keys`

The gate tripped. One model, `api.Unit`, fails on the shipped offline dataset.
Per the plan's hard gate, `api.Unit` received **no UniqueConstraint**, and **no
reference row was deduped, renamed, merged or deleted**. The other 18 registered
models are clean on both datasets and their constraints were applied.

## Dataset 1: the committed fixtures

Checked two ways, because ordering matters here.

**1a. Constraint-free, directly against the fixture JSON.** A standalone script
read every registered model's committed fixture and grouped rows by their
declared natural key, with no database and therefore no constraint able to mask
a duplicate. This is the strictest reading of "before the constraint exists".

```
api.Climate                        5 rows,   5 distinct keys
api.Country                      250 rows, 250 distinct keys
api.FuelType                      19 rows,  19 distinct keys
api.LandUseType                  211 rows, 211 distinct keys
api.ModuleType                    44 rows,  44 distinct keys
api.Unit                           3 rows,   3 distinct keys
ipcc.GlobalWarmingPotential        5 rows,   5 distinct keys
... (32 models total)

CLEAN: no duplicate or empty natural keys across 32 registered models
       in the committed fixtures.
exit 0
```

Note `api.LandUseType`: 211 rows, 211 distinct `name_en` values, confirming the
research finding for the fixture set (and only for the fixture set, see
"Not yet run: production" below).

**1b. Against a database built from those fixtures.**
`bash scripts/build_offline_db.sh` (migrate + `load_reference_data --app=all`)
completed in 20m 29s, and `load_reference_data` loaded all 162 fixtures with the
new UniqueConstraints already applied, which is itself proof they hold on this
data. The detector then ran clean:

```
No duplicate or empty natural keys across 32 registered model(s).
exit 0
```

`api.Unit` holds 3 rows here (`MWh/yr`, `tdm/yr`, `m3/yr`), all distinct.

## Dataset 2: shipped offline database

`git show release/offline-tool:djangoexact/db.sqlite3`, the 53 MB snapshot the
offline tool ships.

```
DUPLICATE  api.Unit (name) = 'm3/yr'  -> pks [102, 103, 104, 105, 106, 112, 113, 114, 115, 116,
                                              117, 118, 119, 120, 121, 122, 123, 124, 130, 131,
                                              132, 133, 134, 135, 136, 137, 138, 139, 140, 146,
                                              147, 148, 149, 150, 151, 152, 153, 154, 155, 156,
                                              162, 163, 164, 165, 166, 167]   (46 rows)
DUPLICATE  api.Unit (name) = 'MWh/yr' -> pks [107, 111, 125, 129, 141, 145, 157, 161]   (8 rows)
DUPLICATE  api.Unit (name) = 'tdm/yr' -> pks [108, 109, 110, 126, 127, 128, 142, 143, 144,
                                              158, 159, 160]   (12 rows)
EMPTY KEY  api.Unit (name)            -> pks [1 .. 98, 100, 101]   (100 rows, name = '')

4 finding(s).
exit 1
```

Row distribution in `api_unit` on that snapshot:

| `name` | rows |
| --- | --- |
| `''` (empty string) | 100 |
| `m3/yr` | 46 |
| `tdm/yr` | 12 |
| `MWh/yr` | 8 |
| **total** | **166** |

Against 3 rows in `api/fixtures/unit.json`. This matches the research audit
("Unit: 3 fixture rows, 166 offline rows, 163 extra offline") and is another
symptom of the same root cause: that database was seeded outside the fixture
pipeline.

All 31 other registered models are clean on this dataset too. The only findings
are the four above.

## What was done, and what was not

- **No `UniqueConstraint` on `api.Unit`.** It is excluded from
  `api/migrations/0290_reference_natural_key_constraints.py`. Applying it would
  fail against the shipped offline data, and making it pass would require
  deleting or merging 163 rows.
- **No reference data was modified.** Reference data is database-truth
  (`docs/guides/fixtures-guide.md`); deduping it silently changes what existing
  projects point at.
- **`api.Unit` stays in `NATURAL_KEY_SPECS`,** annotated as having no uniqueness
  guarantee. This is inert for export and import: `api.Unit` has exactly one
  ForeignKey in the whole model layer, `FuelType.unit` (`api/models.py:596`),
  which is reference data pointing at reference data. It is never a Project,
  Activity or Module FK, so no `.exactproject` payload ever carries a `unit__nk`
  key to resolve. Dropping the registry entry would have hidden a real data
  problem for no behavioural gain.

## Consequences and the open decision

1. `check_reference_natural_keys` exits 1 against the shipped offline snapshot
   and will keep doing so until that snapshot is replaced by a fixture-built
   database (the task 1 handoff checklist in
   `djangoexact/docs/guides/offline-db-bootstrap.md`). Use `--models` to scope
   the command when using it as a build gate in the interim.
2. `api.Unit` has no database-level uniqueness. If a future change makes `Unit`
   reachable from an exported payload, this must be revisited: an ambiguous key
   would resolve to the lowest matching pk (`_lookup_pk` in
   `api/natural_keys.py`), which is deterministic but arbitrary.
3. **Open for the data owner:** decide what those 166 offline `Unit` rows are.
   The 100 blank-named rows look like an abandoned import rather than
   intentional reference data. Resolving that is a data decision, not a code
   decision, and it was deliberately not taken here.

## Not yet run: production

The constraints in this task have been proven against the committed fixtures and
the shipped offline snapshot only. Production Postgres is unreachable from this
sandbox (research assumption A3). Before the migration is deployed:

```bash
cloud-sql-proxy <INSTANCE_CONNECTION_NAME> &
DB_ENGINE=django.db.backends.postgresql DB_HOST=127.0.0.1 DB_PORT=5432 \
DB_NAME=<db> DB_USER=<user> DB_PASSWORD=<pw> \
  python manage.py check_reference_natural_keys
```

A duplicate `name_en` in production would fail
`0290_reference_natural_key_constraints` at deploy time.
