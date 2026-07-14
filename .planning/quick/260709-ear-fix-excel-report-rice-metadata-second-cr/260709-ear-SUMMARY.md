---
phase: 260709-ear
plan: 01
subsystem: reports
tags: [django, excel-report, weasyprint-adjacent, flooded-rice, metadata]

requires: []
provides:
  - "Minor (second) flooded-rice season Excel metadata cultivation-period cell honors the user's Tier-2 override, falling back to the IPCC default only when unset"
  - "Flooded Rice metadata block has a col-1 label on every data row (main season and every stacked minor season), aligned like AnnualCropland and ForestManagement"
affects: [reports, excel-metadata]

tech-stack:
  added: []
  patterns:
    - "Col-1 label emission for stacked repeatable blocks: emit all labels once, up front, before the per-state data loop, keyed to the same row_offsets as the data (mirrors _forest_disturbance_metadata_writes)"

key-files:
  created: []
  modified:
    - djangoexact/api/reports/land.py
    - djangoexact/api/tests/reports/test_flooded_rice_seasons.py

key-decisions:
  - "cultivation_period_t2_{sfx} is a Tier-2 USER OVERRIDE (nullable), never 'season 2' -- both the main Rice module and every MinorSeasonFloodedRice season carry their own independent cultivation_period_t2_start/_w/_wo fields inherited from the shared Rice base model"
  - "season_index is a new keyword-or-positional parameter (before the keyword-only *, is_start, is_with, is_without block) on _flooded_rice_minor_season_metadata_writes, following the same shape as _forest_disturbance_metadata_writes's disturbance_index"
  - "Labels are emitted unconditionally (not gated by is_start/is_with/is_without) since a single col-1 label describes the row regardless of which state columns are populated, matching the AnnualCropland and ForestManagement precedent"

patterns-established:
  - "For any per-instance repeatable metadata block, emit col-1 labels once up front (outside the per-state loop) at the same row_offsets as the data, so (row_offset, col) coordinates never collide across the label pass and the data pass"

requirements-completed:
  - BUG-1-MINOR-SEASON-CULTIVATION-PERIOD
  - BUG-2-RICE-METADATA-LABELS

coverage:
  - id: D1
    description: "Minor rice season cultivation-period cell reads the season's own Tier-2 override (cultivation_period_t2_{sfx}), falling back to season_calc.efc_default.cultivation_period only when None"
    requirement: "BUG-1-MINOR-SEASON-CULTIVATION-PERIOD"
    verification:
      - kind: unit
        ref: "djangoexact/api/tests/reports/test_flooded_rice_seasons.py#TestMinorSeasonMetadataStride.test_minor_season_cultivation_period_falls_back_to_default_when_none"
        status: unknown
      - kind: unit
        ref: "djangoexact/api/tests/reports/test_flooded_rice_seasons.py#TestMinorSeasonMetadataStride.test_minor_season_cultivation_period_uses_tier2_override_when_set"
        status: unknown
    human_judgment: true
    rationale: "The dev sandbox has no Postgres/Docker; the DB-backed Django test suite (this file's in-method import triggers Django app loading) cannot run locally. Tests were added and reasoned through, verified only via py_compile plus manual coordinate-collision analysis. A human must run `python manage.py test api.tests.reports.test_flooded_rice_seasons` in CI/PR to confirm pass status before this is trusted as proven."
  - id: D2
    description: "Flooded Rice metadata block emits a col-1 label on every data row (main season rows 1-7, and 'Minor season N: ...' labels for every stacked minor season block), matching the AnnualCropland/ForestManagement layout"
    requirement: "BUG-2-RICE-METADATA-LABELS"
    verification:
      - kind: unit
        ref: "djangoexact/api/tests/reports/test_flooded_rice_seasons.py#TestMinorSeasonMetadataStride.test_with_only_writes_only_with_column (asserts cols == {1, 3})"
        status: unknown
      - kind: unit
        ref: "djangoexact/api/tests/reports/test_flooded_rice_seasons.py#TestMinorSeasonMetadataStride.test_stride_is_six_per_season"
        status: unknown
      - kind: unit
        ref: "djangoexact/api/tests/reports/test_flooded_rice_seasons.py#TestMinorSeasonMetadataStride.test_two_minor_seasons_with_only_have_unique_coords"
        status: unknown
      - kind: unit
        ref: "djangoexact/api/tests/reports/test_flooded_rice_seasons.py#TestMinorSeasonMetadataStride.test_three_minor_seasons_all_three_states_have_unique_coords"
        status: unknown
    human_judgment: true
    rationale: "Same DB-less sandbox constraint as D1 -- tests are written and reasoned through but not executed locally. Additionally, visual alignment of the rendered Excel Metadata sheet is a genuinely visual judgment call best confirmed by a human opening a generated report, even after the CI test suite passes."

duration: 15min
completed: 2026-07-09
status: complete
---

# Quick Task 260709-ear: Fix Excel Report Rice Metadata (Second Code-Review Round) Summary

**Minor flooded-rice seasons now read their own Tier-2 cultivation-period override instead of always showing the IPCC default, and the whole Flooded Rice metadata block (main season plus every stacked minor season) now carries col-1 labels aligned like every other land activity.**

## Performance

- **Duration:** ~15 min
- **Started:** 2026-07-09T10:35:33+02:00 (plan commit)
- **Completed:** 2026-07-09T10:50:05+02:00 (Task 2 commit)
- **Tasks:** 2 completed
- **Files modified:** 2

## Accomplishments

- BUG 1 fixed: `_flooded_rice_minor_season_metadata_writes` now writes `getattr(season, f"cultivation_period_t2_{sfx}")` when not `None`, falling back to `season_calc.efc_default.cultivation_period` only when the user has not set a Tier-2 override -- mirroring the main-season logic already present at `land.py` (main `compute()`).
- BUG 2 fixed: the helper now takes a `season_index` parameter and emits six col-1 labels ("Minor season N: Hectares", "... Cultivation period (days)", etc.) once, up front, before the per-state data loop -- following the in-repo `_forest_disturbance_metadata_writes` precedent. `FloodedRiceReport.compute()`'s main-season block now emits its own seven col-1 labels (Number of seasons, Hectares, Cultivation period (days), Water management before/after cultivation, Organic amendment, Yield) once, mirroring `AnnualCropland`.
- All 5 call sites of the helper (1 production, 4 pre-existing test call sites, plus 2 new regression tests) updated to pass `season_index`.
- Two new regression tests added covering both the fallback path (no override, uses IPCC default) and the override path (Tier-2 value set, used verbatim).
- `test_with_only_writes_only_with_column` updated from asserting `cols == {3}` to `cols == {1, 3}` since col 1 now always carries labels.

## Task Commits

Each task was committed atomically:

1. **Task 1: BUG 1 - minor-season cultivation period uses the Tier-2 override, plus regression tests** - `666ad866` (fix)
2. **Task 2: BUG 2 - add col-1 labels and season_index to align the rice metadata block, and update all call sites** - `23ee2769` (fix)

_No TDD gate applies to this quick task (tasks are `type="auto"`, not `tdd="true"`)._

## Files Created/Modified

- `djangoexact/api/reports/land.py` - `_flooded_rice_minor_season_metadata_writes` now reads the season's own `cultivation_period_t2_{sfx}` (BUG 1) and takes a `season_index` param to emit six col-1 "Minor season N: ..." labels once per season (BUG 2); `FloodedRiceReport.compute()` now emits main-block col-1 labels once and passes `season_index=i` at its call site.
- `djangoexact/api/tests/reports/test_flooded_rice_seasons.py` - `_build_season` defaults the three Tier-2 override attributes to `None`; two new regression tests cover the fallback/override cultivation-period paths; all 6 helper call sites (4 pre-existing + 2 new) updated to pass `season_index`; `test_with_only_writes_only_with_column` assertion flipped from `{3}` to `{1, 3}`.

## Decisions Made

- `_t2_` in `cultivation_period_t2_{sfx}` means "Tier-2 user override" (nullable), not "season 2" -- confirmed via `api/models.py` where `Rice` (the shared base for both the main `FloodedRice` module and `MinorSeasonFloodedRice`) defines `cultivation_period_t2_start/_w/_wo` once, inherited by every season instance independently. This is why the main-season fallback logic at `land.py` (`efc.cultivation_period if getattr(m, f"cultivation_period_t2_{sfx}") is None else getattr(m, f"cultivation_period_t2_{sfx}")`) needed to be mirrored per-season rather than reused directly -- each `MinorSeasonFloodedRice` instance has its own independent override, not a shared one from the main module.
- `season_index` was placed as a positional-or-keyword parameter directly after `base_row` and before the keyword-only `*` block, matching the shape of `_forest_disturbance_metadata_writes(disturbance, disturbance_index, base_row, *, is_start, ...)` (though that precedent places `disturbance_index` before `base_row`; here it was appended after `base_row` per the plan's explicit instruction, and all callers pass it by keyword, so ordering has no functional effect).
- Labels are emitted unconditionally at the top of the helper, not gated by `is_start`/`is_with`/`is_without`, since a single col-1 label describes what the row represents regardless of which of the three scenario columns happen to be populated for that project -- this matches how `AnnualCropland` and `_forest_disturbance_metadata_writes` already behave.

## Deviations from Plan

None - plan executed exactly as written. Both tasks' `<action>` blocks were followed precisely: BUG 1's fix mirrors the main-season logic at the cited line, BUG 2's labels follow the cited `_forest_disturbance_metadata_writes` precedent, and all 5 (now effectively 7, counting the two Task-1-added tests that also needed the Task 2 parameter) call sites were updated.

## Coordinate/Stride Reasoning (per plan instruction)

Verified by inspection, not by running the DB-backed suite, that adding col-1 labels does not break the existing uniqueness/stride invariants:

- **`test_stride_is_six_per_season`**: each minor season's block still occupies exactly the same six `row_offset` values (`base_row+0` .. `base_row+5`) it did before -- labels sit at col 1 on those same six offsets, they do not add new rows. Season 0's rows remain `[8, 9, 10, 11, 12, 13]` and season 1's remain `[14, 15, 16, 17, 18, 19]`, unchanged from before this fix.
- **`test_two_minor_seasons_with_only_have_unique_coords`** / **`test_three_minor_seasons_all_three_states_have_unique_coords`**: for a given season, the six label writes at `(base_row+0..5, 1)` are disjoint from the six-per-state data writes at `(base_row+0..5, 2/3/4)` (different column), and disjoint from every other season's writes (different `base_row`, since each season still gets its own contiguous 6-row block per `base_row = 8 + 6 * season_index`). No `(row_offset, col)` pair is written twice, whether across the label/data split within one season or across seasons.
- **`test_with_only_writes_only_with_column`**: previously asserted the data-only invariant `cols == {3}`, which no longer holds now that col 1 always carries the six labels regardless of state flags. Flipped to `cols == {1, 3}`, which reflects the actual (and correct) new output: label column plus the single active state column.
- **Main-season block**: the seven new labels at `(1..7, 1)` are disjoint from the pre-existing `(1, 2)` n_seasons cell, the per-state data at `(2..7, 2/3/4)`, and the comment cells at `(2..7, 6)` -- no collisions introduced.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

This is a standalone quick task fixing two report-rendering defects; it does not block or unblock any roadmap phase. The DB-backed test suite (`python manage.py test api.tests.reports.test_flooded_rice_seasons`) must be run in CI or on a Postgres-equipped machine to confirm the new/updated tests actually pass -- this is a CI/PR gate, not something verifiable in this sandbox. No other follow-up required.

---
*Quick task: 260709-ear-fix-excel-report-rice-metadata-second-cr*
*Completed: 2026-07-09*

## Self-Check: PASSED

- FOUND: djangoexact/api/reports/land.py
- FOUND: djangoexact/api/tests/reports/test_flooded_rice_seasons.py
- FOUND: .planning/quick/260709-ear-fix-excel-report-rice-metadata-second-cr/260709-ear-SUMMARY.md
- FOUND commit: 666ad866
- FOUND commit: 23ee2769
