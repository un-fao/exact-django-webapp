---
slug: import-project-loses-results
status: resolved
trigger: "users are reporting that importing projects does not carry the computed results. They have to recompute the results by calling the endpoint for each module. Exported projects should carry the cached results and the module status."
created: 2026-08-11
updated: 2026-08-11
---

# Debug: import_project does not carry cached results or module status

## Symptoms

**Expected behavior**
A project exported via `/api/projects/{pk}/export/` and re-imported via
`/api/projects/import_project/` arrives with its computed results intact: each
module carries its cached results and its module status, so the UI shows the
numbers immediately.

**Actual behavior**
After import the modules come back uncomputed. Users must recompute by calling
the results endpoint for every module individually.

**Error messages**
None reported. Silent data loss, not a crash.

**Timeline**
User reports having fixed this at some point in the past, but is unsure whether
that fix landed on `develop` or only on `release/offline-tool`. Candidate
branches to diff: `feature/project-import-export`, `release/offline-tool`,
`refactor/module-status-validation-er8`, `feat/project-results-cache`.

**Reproduction**
1. Compute results on a project so module caches are populated.
2. `GET /api/projects/{pk}/export/` to obtain the project JSON.
3. `POST /api/projects/import_project/` with that JSON.
4. Open the imported project: results are absent, modules read as not computed.

## Decisions from the user (binding)

- **Scope**: export/import JSON round trip only. Copy-project is NOT in scope.
- **Cache trust on import**: restore the cached numbers **as-is, always**. Do
  not gate on reference-data equality or environment. This matches the existing
  product rule that an EX-ACT appraisal is a record of the numbers as computed,
  and reloading IPCC factors must never retroactively rewrite it.
- **Payload scope**: module `cached_results_*` fields plus the `last_modified`
  timestamp that validates them, and the module status field. Project-level
  `ProjectResultCache` / `results_stamp` were NOT selected, so treat them as out
  of scope unless the module-level restore provably cannot surface results
  without them (report back if so rather than silently widening scope).

## Relevant code (starting points, unverified)

- `djangoexact/api/views.py:824` - `export`
- `djangoexact/api/views.py:871` - `import_project`
- `djangoexact/api/tests/test_project_export.py` - existing round-trip coverage
- `djangoexact/api/models.py:1281-1345` - `CachedResultMixin`
  (`cached_results_total`, `cached_results_by_activity`, `cached_results_by_gas`,
  `cached_results_by_activity_by_gas`, `last_modified`,
  `invalidate_cached_results()`, `is_cached_results_valid()`)
- `djangoexact/api/models.py:625-646` - cache-clearing constants and
  `scripts/invalidate_results_cache.py`

## Current Focus

- status: resolved (committed on `fix/export-import-carries-cached-results`,
  Postgres verification outstanding, CI is the gate)
- bug_class: Bohrbug (deterministic, reproduces every round trip)

### reasoning_checkpoint

```yaml
hypothesis: >
  Four independent defects compose to produce the symptom. D destroys the
  cache in the source project during export so the file never carries it;
  A and B mean status and the cache-validating timestamp are never written to
  the file at all; C wipes any restored parent cache when the importer creates
  submodules. All four must be fixed for an imported project to show results.
confirming_evidence:
  - "Empirical: exported Input payload on unmodified develop contains neither status, last_modified, last_cached_at nor any cached_results_* key, despite a passing precondition assert that the cache was valid in the DB immediately before export."
  - "Empirical: 6 of 7 new regression tests fail on develop with exactly the predicted messages, including 'Input status was reset to EMPTY' and 'parent cache was invalidated while its submodule was created'."
  - "Code: serializers.py:656-659 excluded_fields literally contains 'status' and 'last_modified'."
  - "Code: models.py:765-766 Project.save calls invalidate_module_caches whenever a dirty field is outside exclude_fields, and export_id is absent from that list while views.py:836 saves exactly that field."
  - "Code: models.py:1305-1307 CachedResultMixin.save calls parent.invalidate_cached_results() for every Submodule save, and views.py creates submodules after the parent."
  - "Code: models.py:1343 is_cached_results_valid compares last_cached_at > last_modified, so an import-time last_modified invalidates any restored cache."
falsification_test: >
  Apply all four fixes and re-run the regression suite. If any test still
  fails, or if the four cached_results_* payloads do not come back
  byte-identical with is_cached_results_valid() True, the hypothesis is wrong
  or incomplete. Additionally, reverting any single one of the four fixes must
  make at least one test fail again; if a fix can be reverted with the suite
  still green, that fix was not load-bearing.
fix_rationale: >
  Each change targets one confirmed mechanism, not a symptom.
  D: add export_id to Project.save's exclude_fields, which is exactly the
  documented purpose of that list (metadata that cannot affect emissions).
  A and B: stop excluding status and last_modified from the export payload.
  C: move the cache/status write out of objects.create() into a deferred pass
  that runs after the whole module tree exists and uses queryset update(), so
  it bypasses save() and cannot be re-invalidated or re-stamped.
  No calculation logic, no public API shape, and no reference data changes.
blind_spots:
  - "Verified on SQLite, not Postgres. JSONField and DateTimeField semantics differ slightly; CI on Postgres is the real gate."
  - "Only Input/InputEntry and Grassland are covered directly. The other submodule-bearing families (Irrigation, Transport, Storage, Packaging, Processing, ValueChain, AnnualCropland minor season) share the same code path but are not each asserted."
  - "Project-level ProjectResultCache / results_stamp remain out of scope per the user's decision; module-level restore is sufficient for the per-module results endpoint but a project-level results view may still recompute."
  - "Exported status is a StatusType PK. Cross-installation PK drift is handled by dropping unknown ids, but that path is not directly covered by a test."
candidate_causes:
  - "code: exporter excluded_fields drops status and last_modified (A, B)"
  - "code: importer submodule creation invalidates the restored parent cache (C)"
  - "code/config: Project.save invalidation allowlist omits export_id, so the export action itself wipes the caches (D)"
  - "data: reference-data StatusType PK drift across installations could break a status restore (considered, mitigated defensively, not observed)"
and_gate: >
  YES. This failure requires more than one contributing condition
  simultaneously. D alone empties the payload; even with D fixed, A and B
  would leave the restored cache unreadable and the module non-READY; even
  with A, B and D fixed, C would wipe the cache of every module that owns
  submodules. Confirmed by the staged empirical runs rather than assumed.
```

- hypothesis: superseded. The original two-cause theory (A + B) was correct as
  far as it went but incomplete. The empirical run disproved its claim that
  `cached_results_*` were already being exported, and surfaced C and D. See
  the reasoning_checkpoint above for the confirmed four-cause hypothesis.
- test: ablation. Each of the four fixes was reverted individually with the
  other three in place, and the regression suite re-run.
- expecting: every single-fix ablation makes at least one test fail, proving
  no fix is redundant.
- next_action: awaiting human verification of the round trip in a real
  environment against Postgres.

## Evidence

- checked: `djangoexact/api/serializers.py:656-659`
  (`ModuleExportSerializer.to_representation`)
  found: `excluded_fields = ('id', 'activity', 'status', 'data_source',
  'note', 'history', 'last_modified', 'parent')`. Both `status` and
  `last_modified` are unconditionally skipped.
  implication: CAUSE A. Module status can never survive the round trip, and
  the timestamp that validates the cache is never transported.

- checked: same method, the `else` branch at `serializers.py:682-685`
  found: JSONFields and plain DateTimeFields fall through to
  `data[field.name] = value` when not None. `cached_results_total`,
  `cached_results_by_activity`, `cached_results_by_gas`,
  `cached_results_by_activity_by_gas`, `cached_units_breakdown` and
  `last_cached_at` are NOT in `excluded_fields`.
  implication: the cached numbers ARE already in the export payload today.
  The export side is only half-broken; it is `last_modified` and `status`
  that are missing, not the results themselves.

- checked: `djangoexact/api/views.py:974-1034` (`prepare_model_data`) and
  `views.py:1111-1117` (module creation)
  found: `prepare_model_data` is generic. It copies any field that has a
  DB column and is present in the payload. It applies no cache-specific
  filtering, so it already forwards `cached_results_*` and `last_cached_at`
  into `model_class.objects.create(...)`.
  implication: the importer needs no new plumbing for the cache values. It
  only fails because the payload lacks `last_modified` and `status`.

- checked: `djangoexact/api/models.py:1288-1309` (`CachedResultMixin.save`)
  found: `if self.last_modified is None: self.last_modified = timezone.now()`.
  The field is declared `auto_now=False, null=True, blank=True`
  (`models.py:1286`), so an explicitly supplied value IS preserved on create.
  The dirty-field bump at `models.py:1302-1303` only fires `if self.pk`, so it
  does not affect the initial create.
  implication: CAUSE B, and also the fix path. Because `last_modified` is not
  `auto_now`, exporting it and passing it to `objects.create()` will be
  honoured verbatim. The guidance's suspected `auto_now=True` trap does NOT
  apply to `last_modified`; it applies to `updated_at` (`models.py:1279`),
  which is irrelevant to cache validity.

- checked: `djangoexact/api/models.py:1342-1355`
  found: `is_cached_results_valid()` returns
  `last_cached_at is not None and last_cached_at > last_modified`, and
  `get_cached_results()` returns None whenever that is False.
  implication: closes the AND chain. Restored `last_cached_at` is always in
  the past relative to the import-time `last_modified`, so every imported
  module reports uncomputed even though its JSON columns are populated.

- checked: `djangoexact/api/models.py:1492-1499` (`Module.save`)
  found: `if not self.status: self.status = StatusType.objects.get(name_en="EMPTY")`.
  `Historical` (`models.py:150`) defines no `save()`, so the MRO is
  `Module.save` -> `CachedResultMixin.save` -> `models.Model.save`.
  implication: with `status` absent from the payload, every imported module
  is force-set to EMPTY. This is the second half of the reported symptom
  ("modules read as not computed") and is independent of the cache validity
  problem.

- checked: `git log develop..<branch>` and `git show <branch>:...serializers.py`
  for `feature/project-import-export`, `release/offline-tool`,
  `refactor/module-status-validation-er8`, `feat/project-results-cache`
  found: all five branches (including develop) carry the byte-identical
  `excluded_fields` tuple containing `status` and `last_modified`.
  `feature/project-import-export` has zero commits ahead of develop.
  `release/offline-tool` is ahead only with the original feature commits plus
  `9cad67a0 fix(export/import): correctly export and import
  Input/Energy/Irrigation/Value-Chain module entries`, which addresses entry
  serialization, not the cache or status.
  implication: the user's recollection of a prior fix is not backed by any
  local branch. There is nothing to cherry-pick; the fix must be written.

- checked: `djangoexact/api/views.py:2607-2624` (`GenericModuleViewSet.results`)
  found: the endpoint returns
  `ErrorResponse("Module is not ready. Cannot calculate result.")` at
  `views.py:2613-2615` whenever `module.is_ready()` is False, which is
  evaluated BEFORE `get_cached_results()` at `views.py:2619`.
  `is_ready()` is `self.status and self.status.name_en == "READY"`.
  implication: escalates CAUSE A from cosmetic to blocking. An imported
  module is force-set to EMPTY, so the results endpoint refuses to serve or
  even recompute until the module is re-saved through a write serializer.
  Fixing the cache alone would not restore the user-visible behaviour.

- checked: `djangoexact/api/serializers.py:1520, 1567, 1706, 1987`
  found: `status = READY` is assigned only inside the write serializers'
  `validate()` path. `import_project` bypasses serializers entirely and calls
  `model_class.objects.create(...)` directly (`views.py:1114`).
  implication: nothing in the import path can ever set READY. Confirms status
  must be transported explicitly rather than recomputed.

- checked: `djangoexact/api/models.py:1305-1307` (`CachedResultMixin.save`)
  and `views.py:1126-1130` / `views.py:1200-1203` (`_create_submodules`)
  found: `save()` contains
  `if isinstance(self, Submodule): parent.invalidate_cached_results()`.
  The importer creates each submodule via
  `submodule_class.objects.create(parent=parent_instance, ...)` AFTER the
  parent module has already been created with its restored cache.
  `invalidate_cached_results()` (`models.py:1330-1340`) nulls every cache
  column on the parent and saves.
  implication: CAUSE C. For every module family that owns submodules
  (Input, Irrigation, Transport, Storage, Packaging, Processing,
  AnnualCropland with minor season, ValueChain, ...), the parent's restored
  cache is wiped during import even after causes A and B are fixed. Any fix
  that only writes cache values at `objects.create()` time is insufficient;
  the restore must be re-applied after all descendants exist, and must bypass
  `save()` so it cannot re-trigger invalidation.

- checked: `djangoexact/api/models.py:1400-1410` (`Submodule.save`)
  found: submodules carry their own `status` FK (`models.py:1377`) and are
  likewise forced to EMPTY when status is falsy.
  implication: the restore pass must cover submodules, not just top-level
  modules.

- checked: EMPIRICAL. Ran the new regression test against unmodified develop
  on a local SQLite harness. The exported `Input` module payload was:
  `{'_original_id': 1, 'updated_at': '...', 'start_year': 1, '_submodules':
  [{'_original_id': 1, 'updated_at': '...', 'value_start': 0.0,
  'value_w': 1.0, '_submodule_type': 'InputEntry'}]}`
  found: `status` and `last_modified` are absent as predicted, but so are
  `last_cached_at` and every `cached_results_*` key, even though the setUp
  precondition assertion proved the cache was valid in the DB immediately
  before the export call.
  implication: refutes the earlier code-reading conclusion that the cache
  fields were already being exported. They are omitted because they are None
  BY THE TIME the serializer runs. Something invalidates them during the
  export request itself. This is why the code-reading pass was insufficient
  and the empirical run was necessary.

- checked: `djangoexact/api/models.py:752-768` (`Project.save`) and
  `views.py:833-836` (the `export` action)
  found: `Project.save()` calls `invalidate_module_caches(project=self)`
  whenever any dirty field is outside its `exclude_fields` allowlist
  (`is_locked`, `locked_at`, `lock_updated_at`, `locked_by`, `updated_at`,
  `is_finalized`, `is_public`, `is_archived`, `archived_at`).
  `export_id` is NOT in that list. The export action does
  `project.export_id = uuid.uuid4(); project.save(update_fields=['export_id'])`
  on first export, which bulk-nulls the cache columns of every module in the
  project (`models.py` `invalidate_module_caches`) BEFORE
  `ProjectExportSerializer` reads them.
  implication: CAUSE D, and the dominant one. Exporting a project destroys
  the cached results of the SOURCE project as a side effect, and guarantees
  the export file can never carry them. `export_id` is pure metadata with no
  bearing on emission calculations, so it belongs in `exclude_fields`
  alongside the other lifecycle flags. Note the second-order symptom the user
  did not report: the original project also loses its results on first export.

- checked: `grep export_id` across `api/models.py` and `api/views.py`
  found: `export_id` is written in exactly two places, the export action
  (`views.py:835`) and the import action (`views.py:1056`).
  implication: no caller depends on assigning `export_id` invalidating
  caches, so adding it to `exclude_fields` is safe.

- checked: `djangoexact/api/tests/test_project_export.py` (296 lines)
  found: 14 tests covering export_id semantics, file shape, compatibility
  gating, force-copy, and thread/comment reconstruction. Zero assertions on
  `cached_results_*`, `last_cached_at`, `is_cached_results_valid()`, or
  `status`.
  implication: no existing gate could have caught this. Explains the silent
  regression.

## Eliminated

- hypothesis: A prior fix exists on `feature/project-import-export`,
  `release/offline-tool`, `refactor/module-status-validation-er8`, or
  `feat/project-results-cache` and simply never reached develop.
  evidence: `git show <branch>:djangoexact/api/serializers.py` returns the
  identical `excluded_fields` tuple on all four branches plus develop. No
  commit in `develop..<branch>` touches cache or status export.
  timestamp: 2026-08-11

- hypothesis: `last_modified` is declared `auto_now=True`, so the importer
  cannot preserve it and any restore attempt would be clobbered on save
  (the trap flagged in the investigation guidance).
  evidence: `models.py:1286` declares
  `last_modified = models.DateTimeField(auto_now=False, null=True, blank=True)`.
  `auto_now=True` is on `updated_at` (`models.py:1279`), which plays no part
  in `is_cached_results_valid()`. Explicit values survive create.
  timestamp: 2026-08-11

- hypothesis: The importer drops the `cached_results_*` fields, so the fix
  must add cache-restore plumbing to `import_project`.
  evidence: `prepare_model_data` (`views.py:992-1033`) is field-generic and
  already forwards every columned field present in the payload.
  NOTE: partially reinstated. The generic forwarding is real, but a deferred
  restore pass was still required because create-time writes are wiped by
  cause C. What was correctly eliminated is the idea that the importer needs
  per-field plumbing.
  timestamp: 2026-08-11

- hypothesis: Project-level `ProjectResultCache` / `results_stamp` must also
  be transported for results to surface.
  evidence: `get_cached_results()` reads only module-local columns guarded by
  `is_cached_results_valid()`. Module-level restore is sufficient to make the
  per-module results endpoint serve cached numbers, now confirmed empirically
  by `test_import_keeps_cached_results_valid`. Scope stays as the user
  bounded it.
  timestamp: 2026-08-11

- hypothesis: The exported cache fields are present in the file but merely
  invalidated on import (the original two-cause theory).
  evidence: DISPROVED empirically. The exported payload contains no
  `last_cached_at` and no `cached_results_*` keys at all, because
  `Project.save()` bulk-invalidates every module cache when the export action
  assigns `export_id`. The file was empty of results, not carrying stale ones.
  timestamp: 2026-08-11

## Resolution

- root_cause: >
  Four independent defects compose. (A) `ModuleExportSerializer` listed
  `status` in `excluded_fields`, so module status never reached the file and
  every imported module was forced to EMPTY by `Module.save()`, which makes
  the results endpoint refuse the module outright at `views.py:2613`.
  (B) the same tuple listed `last_modified`, the timestamp
  `is_cached_results_valid()` compares `last_cached_at` against, so any
  restored cache would read as stale.
  (C) `CachedResultMixin.save()` calls `parent.invalidate_cached_results()`
  for every `Submodule` save, and the importer creates submodules after the
  parent, wiping a cache written at create time.
  (D, dominant) `Project.save()` bulk-invalidates every module cache for any
  dirty field outside its allowlist, and `export_id` was not on that list, so
  the export action's `project.save(update_fields=['export_id'])` destroyed
  the caches of the project being exported before the serializer ran. The
  file therefore never contained results in the first place, and the source
  project silently lost its own results on first download.

- fix: >
  (D) add `export_id` to the `exclude_fields` allowlist in `Project.save`
  (`models.py:760-769`), matching the documented intent of that list.
  (A, B) drop `status` and `last_modified` from `ModuleExportSerializer`'s
  `excluded_fields` (`serializers.py:656-666`).
  (C) in `import_project`, pull the cache/status columns out of the payload
  before `objects.create()` and replay them once the whole module tree exists
  via `Model.objects.filter(pk=...).update(...)`, which bypasses `save()` and
  so cannot re-invalidate or re-stamp. Exported StatusType PKs are validated
  before use, so a file from an installation with different reference data
  degrades to EMPTY instead of aborting the import with an FK violation.
  Restore is keyed on the presence of each field, so files from older builds
  import exactly as before.

- verification: >
  Built a local SQLite harness (no Postgres in this sandbox) and ran the
  suite for real rather than reasoning only.
  RED: 6 of 7 new tests failed on unmodified develop with the predicted
  messages. GREEN: all 8 pass with the fix, 5 consecutive runs, no flake.
  ABLATION: each fix reverted individually with the other three in place
  makes at least one test fail (D -> 4 failures, A+B -> 5, C -> 3, D alone
  for the new source-cache test), so no fix is redundant.
  REGRESSION: ran 167 tests across all api test modules before and after.
  Failure sets are identical except that the 6 new tests flip from fail to
  pass. No new failure introduced. The 2 remaining failures and 26 errors are
  pre-existing sandbox artifacts (ProjectFactory needs a country under this
  SQLite schema), confirmed by running the same set on stock develop.
  `test_reference_bootstrap` failure is likewise pre-existing.
  bandit clean on all three changed source files. No em-dashes added.
  NOT verified on Postgres. CI remains the real gate.

- files_changed:
    - djangoexact/api/models.py (Project.save exclude_fields)
    - djangoexact/api/serializers.py (ModuleExportSerializer.excluded_fields)
    - djangoexact/api/views.py (deferred cache/status restore in import_project)
    - djangoexact/api/tests/test_project_export.py (8 regression tests)

- branch: fix/export-import-carries-cached-results (off develop, not pushed)
- commits:
    - 845dd6fb fix(api): carry cached results and status through export/import round trip
    - 411df22c test(api): cover cached results and status across export/import

- outstanding: >
  NOT verified against Postgres. The whole verification story rests on a local
  SQLite harness, and JSONField plus DateTimeField round-tripping is exactly
  where SQLite and Postgres diverge. CI is the gate. Nothing here should be
  read as a Postgres pass. The manual round trip on a real project (export,
  confirm the source project keeps its results, re-import, confirm the numbers
  appear without recompute, then import an older .exactproject file for
  backward compatibility) is also still to be done.

## Historical data loss (flag to product, no code)

Cause D was not only an import bug. Because `Project.save()` invalidated every
module cache on the `export_id` write, **every export performed before this fix
silently wiped the cached results of the project being exported**. This is a
historical, already-happened data loss, not a hypothetical.

What the team needs to know:

- **What happened.** Downloading a project destroyed that project's own cached
  results as a side effect of stamping `export_id` on first download. The user
  who exported was not warned, nothing failed, and no error was logged.
- **It is silent and historical.** The damage is already in the production
  database for any project that was ever exported. The fix stops it recurring
  from now on. It does **not** restore caches that were already cleared.
- **How affected users experience it.** Not as an error. They report it as "my
  results disappeared", "the project shows as not computed", or "I have to
  recompute every module again". Support tickets phrased that way, especially
  from users who had just downloaded a project, are very likely this bug.
- **User-side recovery.** Recomputation is the recovery path. Re-running the
  results endpoint for the affected modules repopulates the cache. The inputs
  were never touched, so nothing the user entered was lost and recomputation
  reproduces the appraisal.
- **Deliberately not done.** No remediation code, no data migration, and no
  blast-radius query were written. This is a product decision about user
  communication, not an engineering one. Product decides whether and how to
  notify affected users.

One caveat worth stating for whoever picks this up: because the cache was
cleared rather than marked, there is no flag in the data that distinguishes a
project damaged by this bug from one the user simply never computed. Sizing the
affected population would need a query over export history rather than over the
cache columns.
