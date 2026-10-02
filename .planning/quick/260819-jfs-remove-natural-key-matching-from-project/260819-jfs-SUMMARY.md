---
quick_id: 260819-jfs
subsystem: api
tags: [django-migrations, project-export-import, revert]

# Dependency graph
requires: []
provides:
  - Project export/import restored to raw primary-key matching (pre-87c8fec8 behavior)
  - Migration 0291 retained with dependency rewired to 0289_asyncjob (no 0290 in the graph)
affects: [any future work touching api/serializers.py export logic, api/views.py import logic, or the offline-tool reference-data sync]

# Actuals (#2632) — chars/4 over the realized diff (git show HEAD | wc -c = 97777)
actuals:
  tokens: 24444
  tasks: 3
  commits: 1

tech-stack:
  added: []
  patterns: []

key-files:
  created: []
  modified:
    - djangoexact/api/models.py
    - djangoexact/ipcc/models.py
    - djangoexact/api/serializers.py
    - djangoexact/api/views.py
    - djangoexact/api/tests/test_project_export.py
    - djangoexact/api/migrations/0291_alter_fishery_ef_source_verbose_name.py
    - djangoexact/docs/guides/offline-db-bootstrap.md

key-decisions:
  - "Used git checkout bf7f906d~1 for the 5 pre-existing files instead of git revert --no-commit, since git diff e57b9673 HEAD was verified empty for all affected files during planning — a deterministic byte-exact restore with no merge risk"
  - "Kept migration 0291's filename and rewired its dependency from 0290 to 0289_asyncjob, leaving a numbering gap at 0290, because develop/review/release/offline-tool databases already recorded 0291 by name in django_migrations"
  - "Deleted the offline-db-bootstrap.md paragraph instructing a pre-deploy run of check_reference_natural_keys against production, since both the command and the migration it guarded are now gone"

patterns-established: []

requirements-completed: []

coverage: []

duration: 4min
completed: 2026-08-19
status: complete
---

# Quick Task 260819-jfs: Remove natural-key matching from project export/import Summary

**Reverted project export/import to raw primary-key matching by deleting the natural-key module, its tests, its management command, and both uniqueness-constraint migrations, restoring the five affected files to their pre-natural-key state via byte-exact checkout, and rewiring migration 0291's dependency past the deleted 0290**

## Performance

- **Duration:** 4 min
- **Started:** 2026-08-19T12:07:47Z
- **Completed:** 2026-08-19T12:11:18Z
- **Tasks:** 3
- **Files modified:** 12 (5 restored, 5 deleted, 2 hand-edited)

## Accomplishments
- Restored `api/models.py`, `ipcc/models.py`, `api/serializers.py`, `api/views.py`, and `api/tests/test_project_export.py` to their exact `bf7f906d~1` content via `git checkout`
- Deleted `api/natural_keys.py`, `api/tests/test_natural_keys.py`, `api/management/commands/check_reference_natural_keys.py`, and migrations `0290_reference_natural_key_constraints.py` (api) and `0065_gwp_natural_key_constraint.py` (ipcc) — removing all 18 uniqueness constraints from the migration graph
- Rewired migration `0291_alter_fishery_ef_source_verbose_name.py`'s dependency from `0290_reference_natural_key_constraints` to `0289_asyncjob`, and reworded its docstring to no longer reference the deleted 0290
- Deleted the trailing paragraph in `docs/guides/offline-db-bootstrap.md` instructing a pre-deploy run of `check_reference_natural_keys` against production
- Export `formatVersion` is back to `1`; `compatibilityGroup` untouched
- `.planning/debug/offline-import-fk-constraint.md` retained unmodified, as required

## Task Commits

1. **Tasks 2+3: Restore pre-change state, verify, commit** - `23385e86` (revert)

Task 1 (baseline capture) produced no commit — see Issues Encountered below.

**Plan metadata:** not committed per orchestrator instruction (PLAN.md/SUMMARY.md/STATE.md are handled separately)

## Files Created/Modified
- `djangoexact/api/models.py` - restored to pre-natural-key state (removed unique constraints, natural-key helper fields)
- `djangoexact/ipcc/models.py` - restored to pre-natural-key state
- `djangoexact/api/serializers.py` - export no longer emits natural-key fields
- `djangoexact/api/views.py` - import resolves reference FKs by raw primary key again; `formatVersion` back to 1
- `djangoexact/api/tests/test_project_export.py` - reverted to pre-`87c8fec8` content (loses ~446 lines of natural-key test coverage, as expected)
- `djangoexact/api/migrations/0291_alter_fishery_ef_source_verbose_name.py` - dependency rewired to `0289_asyncjob`; docstring reworded
- `djangoexact/docs/guides/offline-db-bootstrap.md` - removed the now-stale pre-deploy instruction paragraph
- `djangoexact/api/natural_keys.py` - deleted
- `djangoexact/api/tests/test_natural_keys.py` - deleted
- `djangoexact/api/management/commands/check_reference_natural_keys.py` - deleted
- `djangoexact/api/migrations/0290_reference_natural_key_constraints.py` - deleted
- `djangoexact/ipcc/migrations/0065_gwp_natural_key_constraint.py` - deleted

## Decisions Made
- Checkout over revert (see key-decisions above) — smaller, more auditable diff, no resurrection step needed for the two retained files.
- Kept `0291`'s filename rather than renumbering it to `0290`, per the plan's locked decision, to avoid presenting it as a new migration in environments that already recorded it by that name.

## Deviations from Plan

None — plan executed exactly as written for all file changes (Task 2 and Task 3a-3c, 3e). Task 1 and Task 3d (the DB-backed test comparison) could not be executed; see Issues Encountered.

## Issues Encountered

**No local Postgres server available — Task 1 (baseline capture) and Task 3d (post-revert comparison) could not run.**

- The plan's Task 1 command (`manage.py test api.tests.test_project_export -v 2`, no `--keepdb`) was run before any file changes. It failed immediately at test-collection/import time with:
  ```
  django.db.utils.OperationalError: connection to server at "localhost" (::1), port 5432 failed: Connection refused (0x0000274D/10061)
  ```
  This happens in `api/tests/factories.py` at module import (`SmallFisheryGearType.objects.all()` module-level query), before any individual test can run — no `FAIL:`/`ERROR:` test names were ever produced.
- No `.env` file configuring an alternate DB engine was found in the repo, and neither `docker` nor a local `pg_ctl`/Postgres service is available in this environment. Starting a Postgres instance was out of scope for this revert task and was not attempted.
- I re-ran the identical command after the revert (Task 3d) to check whether the failure signature changed; it failed identically (same exception, same point of failure), confirming the DB unavailability is an environment property unrelated to the code change, not a regression signal.
- Per the plan's own risk note ("if no local DB is configured, skip 2a — the test DB is built fresh in Task 3"), Task 2a (unapplying migrations 0290/0065 against a local DB) was also skipped for the same reason — `showmigrations` was not run since there is no DB to query.
- **This means the plan's stated success bar for Task 3d — "no new failure names versus baseline" — was not verified by test execution in this session.** The file-level checks (3a: no `natural_key`/`__nk` references remain in source or docs, and the three target files are gone from the index; 3b: `makemigrations --check --dry-run` reports "No changes detected"; 3c: `formatVersion` is `1`) all passed and give strong static confidence the revert is complete and self-consistent, but they are not a substitute for the dynamic test-suite comparison the plan specifies. A CI run or a local run against a reachable Postgres instance is the outstanding verification step.
- No misleading `baseline-before.txt`/`baseline-after.txt` artifacts were kept — both capture attempts produced the same import-time traceback with no test names, and keeping a "before" file that was actually captured after the code was reverted (identical content either way, but incorrectly labeled) would have been worse than omitting it. The raw error is reproduced above instead.

## User Setup Required

None - no external service configuration required. (A reachable Postgres/CI run to complete the test-comparison verification step above would need to happen outside this session.)

## Next Phase Readiness

- The revert is complete and self-consistent per all DB-independent checks. `git diff e57b9673 HEAD` for the 11 target files (excluding 0291, which carries its intentional rewire) is now empty again for the 10 fully-reverted files, and `makemigrations --check --dry-run` confirms no model/migration drift.
- Outstanding: run `api.tests.test_project_export` (and ideally the full suite) against a real Postgres connection — locally or via CI — to confirm no new failure names versus the pre-revert baseline, per the plan's stated success bar. This was the one step this session could not execute.

## Orchestrator Addendum: verification actually performed

The executor reported it could not run any DB-backed check because no Postgres
was reachable. The orchestrator got further by pointing Django at SQLite, which
`settings.py` supports via `DB_ENGINE` (the offline tool uses this path).

PASSED — full migration graph applied from scratch:

- `manage.py migrate` on an empty SQLite database: 427 migrations, exit 0.
- `django_migrations` confirms `api.0289_asyncjob` applied, `api.0290%` ABSENT,
  `api.0291_alter_fishery_ef_source_verbose_name` applied. The rewired
  dependency builds a complete schema with no 0290 in the graph.
- `ipcc` stops at `0064_cropnitrousestimationdefaultfactor_comment`; `0065` gone.
- `sqlite_master` shows NO index on `ipcc_globalwarmingpotential`, confirming the
  natural-key uniqueness constraint is genuinely not created any more.
- `manage.py load_reference_data` then loaded all 162 fixtures without error.

This is the verification that actually mattered. Migration `0291`'s rewired
dependency was the ONLY genuinely new artifact in this revert; every other
changed file is byte-identical to `bf7f906d~1`, i.e. code that already shipped.

NOT PERFORMED — the export/import test comparison:

`manage.py test api.tests.test_project_export` was started and then deliberately
killed by the user after ~9 minutes. Django's test runner builds its own
`test_*` database, replaying all 427 migrations again, and that test database
would NOT contain the reference fixtures loaded above, so a portion of any
failures would be fixture-absence noise rather than revert signal. A meaningful
pass/fail number also needs a pre-revert baseline, which would have required a
second full stash-and-migrate cycle.

So: NO test pass/fail counts were obtained, before or after. This is not a
"tests passed" result and must not be read as one. The intended place to get
real test signal is CI on the PR, which has a working Postgres and a natural
baseline. Treat that CI run as the remaining verification gate.

## Orchestrator Addendum: constraints are live on the review database

Found by the orchestrator after the executor returned; the executor had no way to
see this, since it is a deployment-state fact rather than a repository fact.

`.github/workflows/deploy-cloudrun.yaml` triggers on push to `review` and runs
`python manage.py migrate` (line 179). PR #275 merged `develop` into `review` on
2026-08-18 and that Cloud Run deploy completed successfully (run 32149218089).
`git merge-base --is-ancestor bf7f906d origin/review` confirms the constraint
commit is an ancestor of `origin/review`.

**Therefore `api/0290` and `ipcc/0065` are applied on the review Cloud SQL
database, and the 18 UniqueConstraints they added are live there now.**

Deleting the migration files does not drop a constraint that is already applied.
Django will not error — it simply leaves the `django_migrations` rows for two
migrations whose files no longer exist — but the review database will go on
enforcing 18 uniqueness rules that nothing in the migration graph declares. That
is silent until a duplicate reference row is inserted, at which point it fails
with no migration to explain why.

`main` / production never had these migrations applied, so production is
unaffected. `release/offline-tool` builds its SQLite database from fixtures, so
a fresh build after this revert simply never creates the constraints.

Remedies, in preference order:

1. Unapply on review BEFORE this revert is deployed there, from a checkout that
   still contains the migration files (for example `git checkout e57b9673`),
   against the review database via cloud-sql-proxy:
   `python manage.py migrate api 0289_asyncjob` and
   `python manage.py migrate ipcc 0064_cropnitrousestimationdefaultfactor_comment`.
   This is the clean path: Django drops the constraints and removes the rows.
2. If the revert reaches review first, drop the 18 constraints by hand in SQL and
   delete the two `django_migrations` rows in the same transaction.
3. Accept them as inert data-hygiene constraints on review only. Viable only if
   review reference data is never expected to hold duplicate names — which was
   never verified against review; the duplicate scan cited in `bf7f906d` covered
   the fixtures and the shipped offline snapshot, not the review database.

This is an outward-facing action against a live database and was NOT performed.

---
*Quick task: 260819-jfs*
*Completed: 2026-08-19*

## Self-Check: PASSED

- All 7 restored/edited files confirmed present on disk.
- All 5 deleted files confirmed absent from disk.
- Commit `23385e86` confirmed present in `git log --oneline --all`.
- `.planning/debug/offline-import-fk-constraint.md` confirmed retained.
