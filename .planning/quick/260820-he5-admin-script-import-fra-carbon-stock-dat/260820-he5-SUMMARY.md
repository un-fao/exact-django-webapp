---
quick_id: 260820-he5
title: "Admin script: import FRA carbon stock data for a selected assessment year"
date: 2026-08-20
status: complete
commits:
  - cf61f8ca feat(260820-he5): add Country.iso3, ISO3 mapping data, migration 0292
  - fd0be75a feat(260820-he5): admin script to import FRA carbon stock for a chosen year
  - 9faeed81 test(260820-he5): cover ISO3 mapping, payload parsing, replace-all write, and view
---

# Summary — FRA Carbon Stock Admin Script

A staff-only page at `/api/admin-scripts/fra-carbon-stock/` lists the FRA assessment
years from the metadata endpoint with the latest pre-selected, and on POST replaces
every `ipcc.FRACarbonStock` row with data for the chosen year.

## What shipped

**Task 1 — `Country.iso3`** (`cf61f8ca`)
`api.Country.iso3` (`CharField(max_length=3, null=True, blank=True, unique=True)`),
migration `0292_country_iso3` (AddField + RunPython populate), and
`api/data/country_iso3.csv` with 248 ISO3↔name rows. Both `country.json` and
`all_reference_data.json` patched in place — the diff is 256 pure insertions each,
`iso3` lines only, no deletions.

**Task 2 — client + page** (`fd0be75a`)
`admin_scripts/fra_carbon_stock.py` holds `fetch_years` / `fetch_data` /
`parse_payload` / `replace_carbon_stock`, split out of the view so parsing and the
destructive write are testable without HTTP. View, url, template, and `SCRIPTS`
entry follow the `example_script` pattern.

**Task 3 — tests** (`9faeed81`)
`admin_scripts/tests/test_fra_carbon_stock.py`, five classes.

## Verification

| Check | Result |
|---|---|
| ISO3 mapping structure (format, uniqueness, names ⊆ fixture) | pass — 248 rows |
| All 236 FRA country names covered | pass — 0 unmapped |
| **Mapping vs. live FRA API, all 208 countries with values** | **pass — 208/208 exact match, 0 mismatch** |
| `manage.py check` | pass (5 pre-existing unrelated warnings) |
| `makemigrations api --check --dry-run` | "No changes detected" |
| `Iso3MappingTest`, `Iso3FixtureTest`, `ParsePayloadTest` (5 tests) | pass |
| `ReplaceCarbonStockTest`, `FraCarbonStockViewTest` | **NOT RUN — no local Postgres** |

The end-to-end mapping check is worth calling out: rather than relying on the
planned 15 hard-coded spot-checks, every ISO3 in the mapping that has a value was
queried live and compared against `FRACarbonStock2025.csv`. All 208 matched. A
permuted pair of codes — the one failure mode the spot-checks could not catch —
would have produced two mismatches. It produced none.

## Deviations from plan

- The three file/function-level test classes were changed from `TestCase` to
  `SimpleTestCase`. As written they needed a database purely by inheritance, which
  meant none of the offline correctness gate could run without Postgres. They now
  run anywhere, which is the point of an offline gate.

## Outstanding

1. **Two DB-backed test classes never executed.** No local Postgres
   (`connection refused :5432`), and this repo has a standing incident where bare
   `pytest` truncated the review database, so improvising a connection was not
   safe. Run `python manage.py test admin_scripts.tests.test_fra_carbon_stock`
   where a test database exists, or let CI do it.
2. **Migration `0292` has not been applied anywhere** — it has only been validated
   statically via `makemigrations --check`. The `RunPython` populate step is
   unexercised.
3. **Manual acceptance not performed** — running the page for 2025 and confirming
   `AFG → 41.08 / 10.84` with ~236 created rows still needs a real environment.
   The underlying data path was verified directly against the API, so the residual
   risk is in the Django plumbing, not the mapping or the endpoint.

## Notes for later

- `fetch_years()` hardcodes `cycleName=2025`, matching the metadata URL this was
  built against. A future FRA cycle will need that bumped.
- FRA also exposes `carbon_forest_soil`; `FRACarbonStock` has no `soc` field, so it
  is not requested. `carbon_stock_biomass_total` / `carbon_stock_total` stay null,
  as in the existing CSV importer.
- Replace-all is load-bearing, not stylistic: `api/calculators.py:7289` reads
  `FRACarbonStock.objects.filter(country=...).first()` with no year filter. If
  anyone later wants multiple years co-resident, that read must be fixed first.
