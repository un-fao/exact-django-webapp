---
quick_id: 260820-he5
status: locked
---

# Context — FRA Carbon Stock Admin Script

Decisions below are LOCKED by the user. Do not revisit. API facts below were
verified live against fra-data.fao.org on 2026-08-20 — trust them over guesses.

## Goal

A new `/admin-scripts` script that:
1. Fetches the available FRA assessment years from the metadata endpoint.
2. Renders them as a selector with the **latest year pre-selected**.
3. On button click, replaces `ipcc.FRACarbonStock` rows with data for that year.

## Verified API contract

### Years (metadata)

```
GET https://fra-data.fao.org/api/explorer/sections/metadata
    ?assessmentName=fra&countryIso=WO&cycleName=2025&sectionNames[]=carbonStock
```

Response → `carbonStock.dimensions[].name` = `["1990","2000","2010","2015","2020","2025"]`.
Latest = max of those. Also returns `measures[]` and `tableName: "carbonStockAvg"`.

### Data

```
GET https://fra-data.fao.org/api/explorer/data
    ?assessmentName=fra
    &columns[]=<YEAR>
    &countryISOs[]=DZA&countryISOs[]=AGO&...   (repeated, one per country)
    &tableNames[]=carbonStockAvg
    &variables[]=carbon_forest_above_ground
    &variables[]=carbon_forest_below_ground
    &variables[]=carbon_forest_deadwood
    &variables[]=carbon_forest_litter
```

Response shape (verified):

```json
{"fra": {"<YEAR>": {"ITA": {"carbonStockAvg": {"<YEAR>": {
  "carbon_forest_above_ground": {"raw": "50.60"},
  "carbon_forest_below_ground": {"raw": "10.20"},
  "carbon_forest_deadwood":     {"raw": "0.80"},
  "carbon_forest_litter":       {"raw": "1.40"}
}}}}}}
```

Notes, all verified:
- `raw` is a **string or null**. Some entries also carry `"calculated": true` (e.g. BRA) — treat identically.
- **Cloudflare returns 403 without a browser `User-Agent`.** Send e.g. `Mozilla/5.0`. This is not optional.
- Values match `djangoexact/scripts/ipcc_data/FRACarbonStock2025.csv` exactly (AFG → 41.08 / 10.84), confirming the endpoint is the same source as the current CSV import.
- Omitting `cycleName`/`countryIso` selects the "last published" path — that is the correct path here.
- The country ISO list is a fixed set of ~236 FRA countries.

## Locked decision 1 — ISO mapping: add `iso3` to `api.Country`

`api.Country` (djangoexact/api/models.py:305) currently has **only** `name` — no ISO
code. FRA exposes no public ISO→name endpoint (`/api/admin/countries` requires auth).

So: add an `iso3` field to `api.Country` + migration + populate it, and match
FRA rows on `iso3`. Chosen over a vendored dict or a `pycountry` dependency
because it is reusable for future FRA/FAO imports.

- `djangoexact/api/fixtures/country.json` holds 256 countries with standard
  ISO-3166 English names, title-cased (`"Antigua And Barbuda"`). Use it to
  build/verify the ISO3→name mapping.
- `iso3` must be nullable/blank (not every row will map) and indexed/unique
  where populated — a country with no ISO3 must not collide with another.
- **Report unmapped ISOs** rather than silently dropping them; the current
  ipcc_dump prints `missing_countries` and that behaviour should be preserved.

## Locked decision 2 — write strategy: replace all

Mirror `import_fra_carbon_stock_data_2025()` exactly: delete **every**
`FRACarbonStock` row, then insert the selected year.

**Why this is required, not just convenient:** `djangoexact/api/calculators.py:7289`
reads `FRACarbonStock.objects.filter(country=self.country).first()` — no year
filter, no ordering. If two years coexist, the calculator picks a row by
arbitrary DB order and carbon results become non-deterministic. Replace-all
keeps the existing single-year invariant, so calculators.py needs no change.

Wrap the delete+insert in a single `transaction.atomic()` so a mid-import
failure cannot leave the table empty.

## Field mapping

| FRA variable                  | FRACarbonStock field |
|-------------------------------|----------------------|
| carbon_forest_above_ground    | `agb`                |
| carbon_forest_below_ground    | `bgb`                |
| carbon_forest_deadwood        | `deadwood`           |
| carbon_forest_litter          | `litter`             |

`carbon_stock_biomass_total` and `carbon_stock_total` stay **null** — the current
2025 CSV import leaves them null too, and no consumer reads them. FRA also
exposes `carbon_forest_soil`, but the model has no `soc` field, so it is not
requested. Do not invent totals.

## Conventions to follow

- App: `djangoexact/admin_scripts/`. Register in `SCRIPTS` (views.py:88), add a
  `urls.py` path, template under `templates/admin_scripts/scripts/`.
- Views use `@login_required(login_url="/admin/login/")` + `@staff_required`.
- Follow `example_script` for the simple GET-form/POST-run page shape.
- This is a destructive, network-calling admin action: it must be **POST**, CSRF
  protected, and staff-gated. Do not perform the write on GET.
- Leave one runnable check behind covering the response parsing and the
  replace-all behaviour (project uses pytest; see `djangoexact/admin_scripts/tests/`).
