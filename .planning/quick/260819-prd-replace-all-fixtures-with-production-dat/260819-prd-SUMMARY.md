---
quick_id: 260819-prd
slug: replace-all-fixtures-with-production-dat
date: 2026-08-19
status: complete
---

# Summary — Replace all fixtures with production data

## What changed

Regenerated 163 fixture files from production via
`python manage.py dump_reference_data --app all --force`.
82 files actually differed: **+539,146 / −1,057,948 lines**.

No new code was written. The existing `dump_reference_data` command,
driven by `api/fixtures_manifest.py`, already did exactly this.

## Row-count deltas (162 models, 134 unchanged)

Net: 86,641 → 63,869 rows (−22,772).

Largest reductions — both correct:

| Model | Fixture | Prod | Delta |
|---|---:|---:|---:|
| `ipcc.TotalBiomassAfterDefo` | 18,880 | 6,080 | −12,800 |
| `ipcc.ForestTotalBiomass` | 18,272 | 5,792 | −12,480 |

These two committed fixtures carried 79 extra `land_use_type` values that are
FAO **crop** names — "Artichokes", "Soya beans", "Cereals, primary + (Total)" —
holding forest-biomass values. That is a bad cross-join against the full
`LandUseType` table in the old fixture, not data production is missing.
Production's 41–42 genuine land-use types are correct.

Largest additions — stale fixtures catching up to production:

| Model | Fixture | Prod | Delta |
|---|---:|---:|---:|
| `ipcc.LivestockManureEF` | 27,720 | 29,974 | +2,254 |
| `api.Unit` | 3 | 166 | +163 |
| `api.FieldDefinition` | 74 | 96 | +22 |
| `api.HandInHandAssessment` | 13 | 30 | +17 |
| `api.FundingAgency` | 0 | 16 | +16 |
| `api.ExecutingAgency` | 0 | 7 | +7 |
| `api.Country` | 250 | 256 | +6 |
| `api.ForestDegradationLevel` | 0 | 6 | +6 |

## `--force` justification

The dry run reported 12 PK-stability violations. They fall into two kinds:

- **Renames in place** — `'UNFCCC - Combined Margin'` → `'Combined Margin'`,
  `'East Asia And South-East Asia'` → `'East Asia and South-East Asia'`,
  `'small_fishery_kw_tonnes'` → `'kw_tonnes'`. Same row, updated label.
- **Genuine PK reshuffles** — `api.ModuleType`, `api.FieldDefinition`,
  `api.Country`, `api.HandInHandAssessment`.

The guardrail's stated risk is broken FKs. It does not apply here because the
entire manifest was dumped from a single production snapshot, so the fixture
set is internally consistent by construction. Verified, not assumed — see below.

## Verification

| Check | Result |
|---|---|
| `verify_reference_parity` | ✅ parity verified across 162 models |
| FK/M2M integrity across the fixture set | ✅ **0 dangling** in 305,502 references |
| `check_reference_natural_keys` | ⚠ 4 advisory findings on `api.Unit` (below) |
| Non-manifest fixtures unaffected | ✅ `test_seed_data.json` holds only users/groups |

## Known issues surfaced (pre-existing in production, now visible in fixtures)

`check_reference_natural_keys` reports 4 findings on `api.Unit`, newly visible
because the fixture went from 3 rows to production's 166:

- 100 rows with an **empty** `name`
- `'m3/yr'` duplicated across 46 PKs, `'tdm/yr'` across 12, `'MWh/yr'` across 8

This is production reality, not dump corruption. The command's own guidance
applies: *"Do not dedupe reference data to silence this: reference data is
database-truth and existing projects point at these rows."* Left as-is.

## Follow-ups (not done — out of scope)

1. **`settings.py` env path bug.** [settings.py:28](../../djangoexact/djangoexact/settings.py#L28)
   resolves `.env.<APP_MODE>` to `djangoexact/djangoexact/`, but the env files
   live at the repo root. With `APP_MODE=production` set, nothing loads, and
   startup dies at [settings.py:364](../../djangoexact/djangoexact/settings.py#L364)
   with `Firebase config not found: Incorrect padding`. Worked around locally;
   the bug is still there.
2. **Server-side cursors fail through the proxy** (`InvalidCursorName`)
   mid-serialization. Needed `DISABLE_SERVER_SIDE_CURSORS` to complete the dump.
3. **`all_api_dependencies.json` is stale** — missing fr/es/ru translations and
   older country names. It is a fallback branch in `ipcc/import_ipcc_fixtures.sh:84`
   and is not manifest-managed, so the refresh does not reach it.
