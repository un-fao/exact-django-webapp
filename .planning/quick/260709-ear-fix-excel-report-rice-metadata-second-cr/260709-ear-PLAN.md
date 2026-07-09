---
phase: 260709-ear
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - djangoexact/api/reports/land.py
  - djangoexact/api/tests/reports/test_flooded_rice_seasons.py
autonomous: true
requirements:
  - BUG-1-MINOR-SEASON-CULTIVATION-PERIOD
  - BUG-2-RICE-METADATA-LABELS
must_haves:
  truths:
    - "In the Excel Metadata sheet, a minor (second) rice season shows the user-entered Tier-2 cultivation period when set, not the ~113-day IPCC default."
    - "When a minor season has no Tier-2 override, its cultivation-period cell falls back to the IPCC default (efc_default.cultivation_period)."
    - "The Flooded Rice metadata block has a col-1 label on every data row, aligned like every other land activity (AnnualCropland, ForestManagement)."
    - "Stacked minor seasons are distinguishable by a 'Minor season N:' label prefix, mirroring the forest-disturbance precedent."
  artifacts:
    - djangoexact/api/reports/land.py
    - djangoexact/api/tests/reports/test_flooded_rice_seasons.py
  key_links:
    - "_flooded_rice_minor_season_metadata_writes cultivation-period write must read the season's own cultivation_period_t2_{sfx}, falling back to season_calc.efc_default.cultivation_period only when None (mirrors main-season land.py:877)."
    - "Every MetadataWrite label lives in col 1 (META_COL_LABEL); data stays in cols 2/3/4; (row_offset, col) coordinates stay unique so the renderer stacks them without collision."
    - "All 5 helper call sites (1 production + 4 test) must pass the new season_index param."
---

<objective>
Fix two Excel-report defects in the Flooded Rice activity metadata, both living in djangoexact/api/reports/land.py and consumed by ExcelRenderer._write_module_metadata:

- BUG 1: a minor (second) rice season's cultivation-period cell is hardcoded to the Tier-1 IPCC default (~113 days) and ignores the user's Tier-2 override.
- BUG 2: the Flooded Rice metadata block emits no col-1 labels and prepends an unlabeled season-count cell, so its rows do not line up under labels like every other activity.

Purpose: the Excel report must display the number the user actually entered for the second season, and the rice metadata block must be as readable and aligned as every other land activity.

Output: corrected land.py logic and updated/added unit tests in test_flooded_rice_seasons.py. No public API, serializer, or calculation-result change; this only corrects which stored field feeds the second-season cultivation-period cell and relabels/realigns metadata cells.
</objective>

<execution_context>
@$HOME/.claude/gsd-core/workflows/execute-plan.md
@$HOME/.claude/gsd-core/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md

# The file both bugs live in (helper at ~754-787, FloodedRiceReport.compute at ~844-913)
@djangoexact/api/reports/land.py

# Existing DB-free unittest suite that must be updated
@djangoexact/api/tests/reports/test_flooded_rice_seasons.py
</context>

<constraints>
- Never use em-dashes anywhere (project rule). Use commas, parentheses, or separate sentences.
- Conventional-commit messages (commitizen). Suggested scope: `reports`.
- The dev sandbox has NO Postgres/Docker; the DB-backed pytest/APITestCase suite CANNOT run locally. The local gate is `python -m py_compile` on the changed .py files, run from djangoexact/. The tests in test_flooded_rice_seasons.py are pure unittest.TestCase with Mock objects, but their in-method `from api.reports.land import ...` triggers Django app loading, so a bare `python -m pytest` / `python -m unittest` is unreliable without a configured DB. Treat inability to run them locally as EXPECTED; rely on py_compile plus careful reasoning. Do NOT claim the DB-backed suite passed. The unit tests are a CI/PR gate.
- Do NOT change public API, serializers, or calculation results. Keep existing data-cell row_offsets unchanged (tests assert stride/coords). Only add col-1 labels, add the season_index param, and correct the second-season cultivation-period source field.
</constraints>

<tasks>

<task type="auto">
  <name>Task 1: BUG 1 - minor-season cultivation period uses the Tier-2 override, plus regression tests</name>
  <files>djangoexact/api/reports/land.py, djangoexact/api/tests/reports/test_flooded_rice_seasons.py</files>
  <action>
In djangoexact/api/reports/land.py, inside `_flooded_rice_minor_season_metadata_writes` (the per-state `for col, is_state, sfx` loop, currently ~line 781), the cultivation-period write is `MetadataWrite(base_row + 1, col, season_calc.efc_default.cultivation_period)`. Change the value expression to mirror the main-season logic at land.py:877 so it uses the season's OWN Tier-2 override when present: use `season_calc.efc_default.cultivation_period` when `getattr(season, f"cultivation_period_t2_{sfx}")` is None, otherwise use `getattr(season, f"cultivation_period_t2_{sfx}")`. Note terminology: the `_t2_` suffix means "Tier-2 user override" (nullable), NOT "season 2"; each season carries its own `cultivation_period_t2_start/_w/_wo` (defined on the shared Rice base model at api/models.py:2065-2067, inherited by MinorSeasonFloodedRice at api/models.py:2089). Leave the other five writes (area, water before, water after, organic amendment, yield) unchanged. Do NOT add col-1 labels or the season_index param here; that is Task 2.

In djangoexact/api/tests/reports/test_flooded_rice_seasons.py, make the BUG 1 behavior testable and add regression coverage:
1. In `TestMinorSeasonMetadataStride._build_season` (~lines 86-111), explicitly set the three Tier-2 override attributes to None by default so the existing coordinate tests deterministically exercise the default-fallback path (a bare Mock would auto-create a truthy child attribute). Add: `season.cultivation_period_t2_start = None`, `season.cultivation_period_t2_w = None`, `season.cultivation_period_t2_wo = None`.
2. Add `test_minor_season_cultivation_period_falls_back_to_default_when_none`: build a season with `_build_season(0)` (t2 overrides None, `efc_default.cultivation_period == 120`), call the helper with `base_row=8, is_start=False, is_with=True, is_without=False`, index the writes by `(row_offset, col)`, and assert the value at `(9, 3)` equals `120` (the efc_default fallback).
3. Add `test_minor_season_cultivation_period_uses_tier2_override_when_set`: build `_build_season(0)`, then set `season.cultivation_period_t2_w = 99`, call the helper the same way, and assert the value at `(9, 3)` equals `99` (the Tier-2 override, NOT 120).
Write these two tests against the CURRENT helper signature (no season_index arg); Task 2 will update every call site including these.
  </action>
  <verify>
    <automated>cd djangoexact && python -m py_compile api/reports/land.py api/tests/reports/test_flooded_rice_seasons.py && echo PY_COMPILE_OK</automated>
  </verify>
  <done>
    - The minor-season helper writes the season's `cultivation_period_t2_{sfx}` at row_offset base_row+1 when that field is not None, and `season_calc.efc_default.cultivation_period` when it is None (matching main-season land.py:877 semantics).
    - `_build_season` sets `cultivation_period_t2_start/_w/_wo = None` by default.
    - Two new regression tests exist (override path and fallback path) asserting the value at coordinate (9, 3).
    - `python -m py_compile` on both files succeeds (PY_COMPILE_OK printed). No em-dashes introduced.
  </done>
</task>

<task type="auto">
  <name>Task 2: BUG 2 - add col-1 labels and season_index to align the rice metadata block, and update all call sites</name>
  <files>djangoexact/api/reports/land.py, djangoexact/api/tests/reports/test_flooded_rice_seasons.py</files>
  <action>
Follow the in-repo precedent `_forest_disturbance_metadata_writes` (land.py ~714-751), which emits its col-1 labels ONCE at the top of the helper (outside the per-state loop) then appends cols 2/3/4 data, keeping every (row_offset, col) unique.

In djangoexact/api/reports/land.py:
1. Change the signature of `_flooded_rice_minor_season_metadata_writes` to accept a new keyword-only `season_index: int` (place it before the existing `*, is_start, is_with, is_without` keyword-only block, e.g. as a positional-or-keyword param after `base_row`). At the top of the function body, before the `for col, is_state, sfx` loop, initialize `writes` with six col-1 label MetadataWrites at base_row+0..+5, each prefixed to distinguish stacked seasons using `season_index + 1`: "Minor season {n}: Hectares", "Minor season {n}: Cultivation period (days)", "Minor season {n}: Water management before cultivation", "Minor season {n}: Water management after cultivation", "Minor season {n}: Organic amendment", "Minor season {n}: Yield" (where n = season_index + 1). Keep the per-state data loop (cols 2/3/4) exactly as left by Task 1, including the Task 1 Tier-2 cultivation-period fix. Do not change any data-cell row_offset. Update the helper docstring to note the col-1 labels and season_index (referencing the forest-disturbance precedent), with no em-dashes.
2. Update the production call site at land.py ~890 (inside `FloodedRiceReport.compute`, the `for i, season in enumerate(minor_seasons)` loop) to pass `season_index=i`.
3. In `FloodedRiceReport.compute` main-season block (~865-882): add col-1 labels emitted ONCE before the `for col, is_state, sfx` state loop, so the main block reads like AnnualCropland (land.py:345-355). Keep the existing `MetadataWrite(1, 2, n_seasons)` season-count cell and pair it with a label. Set `mw = [MetadataWrite(1, 2, n_seasons), MetadataWrite(1, 1, "Number of seasons"), MetadataWrite(2, 1, "Hectares"), MetadataWrite(3, 1, "Cultivation period (days)"), MetadataWrite(4, 1, "Water management before cultivation"), MetadataWrite(5, 1, "Water management after cultivation"), MetadataWrite(6, 1, "Organic amendment"), MetadataWrite(7, 1, "Yield")]`. Leave the per-state data writes at row_offsets 2-7 (cols 2/3/4) unchanged, and leave the trailing `MetadataWrite(7, 6, m.crop_yield_t2_thread.format_comments())` comment write unchanged.

In djangoexact/api/tests/reports/test_flooded_rice_seasons.py, update EVERY call to `_flooded_rice_minor_season_metadata_writes` to pass the new `season_index`:
- `_collect_coords` (~line 120): pass `season_index=i` (the loop index).
- `test_stride_is_six_per_season` (~lines 155, 159): pass `season_index=0` for w0 and `season_index=1` for w1.
- `test_with_only_writes_only_with_column` (~line 173): pass `season_index=0`, and change the assertion from `self.assertEqual(cols, {3})` to `self.assertEqual(cols, {1, 3})` (col 1 now carries the labels, col 3 the with-project data).
- The two BUG 1 regression tests added in Task 1: pass `season_index=0`. Their `(9, 3)` value assertions are unaffected because labels land in col 1, not col 3.
Verify (by reasoning) that `test_two_minor_seasons_with_only_have_unique_coords`, `test_three_minor_seasons_all_three_states_have_unique_coords`, and `test_stride_is_six_per_season` still hold: the six new labels sit at col 1 on the same six row_offsets (base_row+0..+5), so the per-season row set stays [8..13] then [14..19] and label coords never collide with the col 2/3/4 data coords. Note this reasoning in the SUMMARY.
  </action>
  <verify>
    <automated>cd djangoexact && python -m py_compile api/reports/land.py api/tests/reports/test_flooded_rice_seasons.py && echo PY_COMPILE_OK</automated>
  </verify>
  <done>
    - `_flooded_rice_minor_season_metadata_writes` takes `season_index` and emits six "Minor season {n}: ..." col-1 labels at base_row+0..+5 before the data loop, with data cells unchanged.
    - `FloodedRiceReport.compute` emits main-block col-1 labels once (Number of seasons, Hectares, Cultivation period (days), Water management before cultivation, Water management after cultivation, Organic amendment, Yield); the n_seasons cell and comment cell are preserved; data row_offsets 2-7 unchanged.
    - All 5 helper call sites (1 production at land.py:890, 4 in tests) pass season_index.
    - `test_with_only_writes_only_with_column` asserts `{1, 3}`.
    - `python -m py_compile` on both files succeeds (PY_COMPILE_OK printed). No em-dashes introduced.
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| stored model field -> Excel cell | Values already-persisted rice-season fields are written into the Metadata worksheet; no new untrusted input crosses here. |

## STRIDE Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation Plan |
|-----------|----------|-----------|----------|-------------|-----------------|
| T-260709ear-01 | Tampering | Excel cell values from model fields | low | accept | Values written are IntegerField (cultivation_period), enum `.name` strings, and numeric yield/area; no new free-text or user-controlled formula string is introduced, so no new CSV/formula-injection surface. The pre-existing comment cell (`format_comments()`) is unchanged. |
| T-260709ear-02 | Tampering | npm/pip/cargo installs | low | accept | No new dependencies added; edits are pure Python within existing modules. |
</threat_model>

<verification>
- `cd djangoexact && python -m py_compile api/reports/land.py api/tests/reports/test_flooded_rice_seasons.py` succeeds for both tasks (local gate).
- Manual review confirms: minor-season cultivation-period value now mirrors main-season land.py:877; every rice metadata data row has a col-1 label; data-cell row_offsets are unchanged; all 5 helper call sites pass season_index.
- CI/PR gate (not runnable in the DB-less sandbox): `python manage.py test api.tests.reports.test_flooded_rice_seasons` including the updated `{1, 3}` assertion and the two new BUG 1 regression tests.
</verification>

<success_criteria>
- BUG 1: a minor season with a Tier-2 cultivation-period override displays that value in the Excel Metadata sheet; without an override it falls back to the IPCC default.
- BUG 2: the Flooded Rice metadata block is labeled and aligned like other activities (col-1 labels on every row, stacked minor seasons prefixed "Minor season N:").
- No public API, serializer, or calculation-result change; existing data-cell row_offsets preserved.
- Both changed files pass `python -m py_compile`.
</success_criteria>

<output>
Create `.planning/quick/260709-ear-fix-excel-report-rice-metadata-second-cr/260709-ear-SUMMARY.md` when done.
</output>
