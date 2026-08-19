---
quick_id: 260819-jfs
slug: remove-natural-key-matching-from-project
date: 2026-08-19
status: planned
---

# Quick Task 260819-jfs — Remove natural-key matching from project export/import

## Goal

Revert project export/import to raw primary-key matching by removing the
natural-key mechanism from all three layers it reached: export emission
(`serializers.py`), import resolution (`views.py`), and the DB uniqueness
constraints (`models.py` + two migrations). Undoes commits `bf7f906d`,
`87c8fec8`, and `e57b9673`, with two deliberate exceptions (migration `0291`
and the debug record) that must survive.

## Approach

**Checkout, not `git revert`.** Planning verified that
`git diff e57b9673 HEAD` is **empty** for all eleven affected files — HEAD is
byte-identical to `e57b9673` for every one of them. That makes the revert a
deterministic file restore with no merge and no conflict possibility:

- 5 pre-existing files → `git checkout bf7f906d~1 -- <paths>` (exact pre-change bytes)
- 5 files introduced by the natural-key work → `git rm -f`
- 2 files edited by hand (migration `0291`, one docs paragraph)

`git revert --no-commit` was the suggested base, but it works out worse here: it
would additionally try to delete `0291` and
`.planning/debug/offline-import-fk-constraint.md` — both of which must be kept —
so it needs the same hand-fixes *plus* a resurrection step. Checkout is the
shorter, more auditable diff.

**Locked decisions 3 and 4 come free.** `bf7f906d~1:views.py` already reads
`"formatVersion": 1` (line 912) and already defines `resolve_status_id(value)`
with the identity/`None` behavior. Restoring that file satisfies both decisions
exactly; no hand-editing of export or import logic is required.

## Verified facts (established during planning — do not re-verify)

- Zero drift: `git diff --stat e57b9673 HEAD -- <all 11 files>` is empty.
- `0290` contains **17** `AddConstraint` operations and nothing else, and already
  depends on `('api', '0289_asyncjob')` — so rewiring `0291` to `0289_asyncjob`
  simply inherits `0290`'s own dependency. `ipcc/0065` is one `AddConstraint`.
- `0291`'s four `AlterField` operations target the fishery `ef_source` fields and
  do not depend on any constraint added by `0290`.
- Nothing in the frontend (`*.ts`, `*.vue`, `*.js`) references `formatVersion` or
  the export key suffix — dropping the version back to 1 has no client impact.
- Python env: `.venv/Scripts/python.exe`, Django 5.2.17. `manage.py` lives at
  `djangoexact/manage.py`.

## Extra finding not in the task brief

`djangoexact/docs/guides/offline-db-bootstrap.md:138` instructs the reader to run
`python manage.py check_reference_natural_keys` against production before
deploying the uniqueness migration. That doc was written by a **different**
commit (`6190429f`), so no revert of the three target commits touches it — it
would be left pointing at a deleted management command and a deleted migration.
The whole trailing paragraph (starting "Additionally, before the reference-data
uniqueness migration…") describes a deployment precaution that no longer exists
and must be deleted.

## Decision: keep the `0291` filename, leave a gap at 0290

Recommended: **do not rename.** Rewire the dependency, keep the name.

- Django resolves migrations through the `dependencies` graph, not filename
  numbering. A numeric gap is inert.
- `develop`, `review`, and `release/offline-tool` databases already recorded
  `0291_alter_fishery_ef_source_verbose_name` by **name** in `django_migrations`.
  Keeping the name means those environments correctly see it as applied.
  Renaming it to `0290_…` would present it as a brand-new migration and re-apply
  it — harmless in itself (it is state-only, no SQL) but pointless churn plus a
  duplicate historical row.
- Smaller diff.

## Tasks

### Task 1 — Capture the pre-revert baseline

Must run **before** any file changes; the comparison is worthless afterwards.

**Action.** From `djangoexact/`, run the export/import module and record the
verbatim `FAIL:`/`ERROR:` test names plus the summary line:

```
cd djangoexact
../.venv/Scripts/python.exe manage.py test api.tests.test_project_export -v 2 2>&1 | tee ../.planning/quick/260819-jfs-remove-natural-key-matching-from-project/baseline-before.txt | tail -40
```

Do **not** pass `--keepdb`. A kept test DB still physically carries the 18 unique
constraints, which would contaminate the post-revert run. Both runs must build
the DB from migrations.

**Done.** `baseline-before.txt` exists and the set of `FAIL:`/`ERROR:` names is
recorded. The repo has known pre-existing failures — `e57b9673`'s commit message
cites 63 tests / 1F+21E. A non-zero count is expected and is not a blocker.

### Task 2 — Restore the pre-change state

**Files.**
- Checkout (5): `djangoexact/api/models.py`, `djangoexact/ipcc/models.py`,
  `djangoexact/api/serializers.py`, `djangoexact/api/views.py`,
  `djangoexact/api/tests/test_project_export.py`
- Delete (5): `djangoexact/api/natural_keys.py`,
  `djangoexact/api/tests/test_natural_keys.py`,
  `djangoexact/api/management/commands/check_reference_natural_keys.py`,
  `djangoexact/api/migrations/0290_reference_natural_key_constraints.py`,
  `djangoexact/ipcc/migrations/0065_gwp_natural_key_constraint.py`
- Hand-edit (2): `djangoexact/api/migrations/0291_alter_fishery_ef_source_verbose_name.py`,
  `djangoexact/docs/guides/offline-db-bootstrap.md`

**2a. Unapply the constraint migrations first, if a local DB has them.**
Deleting the migration files while the constraints are physically present leaves
them enforced in the DB with orphan `django_migrations` rows. Check, then unapply:

```
cd djangoexact
../.venv/Scripts/python.exe manage.py showmigrations api ipcc | grep -E "0289|0290|0291|0064|0065"
```

If `0290` / `0065` show as applied:

```
../.venv/Scripts/python.exe manage.py migrate api 0289_asyncjob
../.venv/Scripts/python.exe manage.py migrate ipcc 0064_cropnitrousestimationdefaultfactor_comment
```

`AddConstraint` reverses to `RemoveConstraint`, so both unapply cleanly. If no
local DB is configured, skip 2a — the test DB is built fresh in Task 3.

**2b. Restore and delete** (from repo root):

```
git checkout bf7f906d~1 -- \
  djangoexact/api/models.py \
  djangoexact/ipcc/models.py \
  djangoexact/api/serializers.py \
  djangoexact/api/views.py \
  djangoexact/api/tests/test_project_export.py

git rm -f \
  djangoexact/api/natural_keys.py \
  djangoexact/api/tests/test_natural_keys.py \
  djangoexact/api/management/commands/check_reference_natural_keys.py \
  djangoexact/api/migrations/0290_reference_natural_key_constraints.py \
  djangoexact/ipcc/migrations/0065_gwp_natural_key_constraint.py
```

**2c. Rewire `0291`.** Change its `dependencies` entry from
`('api', '0290_reference_natural_key_constraints')` to `('api', '0289_asyncjob')`.
Keep the filename. Its module docstring currently cites migration 0290 as the
contrast case; reword it so it no longer names a migration that no longer exists,
while keeping the substance: the four operations are verbatim `makemigrations`
output correcting pre-existing drift left by 0286/0288, and they carry no SQL.

**2d. Fix the docs guide.** Delete the trailing paragraph of
`djangoexact/docs/guides/offline-db-bootstrap.md` (around lines 137–142) that
instructs running the deleted management command against production before
deploying the deleted uniqueness migration.

**2e. Re-apply `0291`** if 2a was performed: `../.venv/Scripts/python.exe manage.py migrate`.

**Keep untouched.** `.planning/debug/offline-import-fk-constraint.md` — historical
debug record, explicitly retained.

**Done.** `git status` shows exactly 5 modified + 5 deleted + 2 edited files, and
no other path.

### Task 3 — Verify and commit

**3a. No trace left in the source tree.** All three must return no matches
(the grep is scoped to `djangoexact/`, so neither `.venv/` at repo root nor this
plan under `.planning/` can register a false hit):

```
grep -rn "natural_key\|__nk" djangoexact/ --include="*.py"
grep -rn "natural_key\|__nk\|check_reference_natural_keys" djangoexact/ --include="*.md"
git ls-files djangoexact/api/natural_keys.py djangoexact/api/migrations/0290_reference_natural_key_constraints.py djangoexact/ipcc/migrations/0065_gwp_natural_key_constraint.py
```

**3b. Model state agrees with migration state.**

```
cd djangoexact
../.venv/Scripts/python.exe manage.py makemigrations --check --dry-run
```

Must report no changes. Expected to pass: `models.py` reverts to its pre-0290
shape, and the retained `0291` still resolves the older `ef_source` verbose_name
drift — so the tree ends up *cleaner* here than `bf7f906d~1` was.

**3c. Export version reverted.** `grep -n '"formatVersion"' djangoexact/api/views.py`
reports `1` at the export endpoint. Confirm no `compatibilityGroup` change.

**3d. Test comparison — report honestly.** Re-run the Task 1 command (again
without `--keepdb`) into `baseline-after.txt` and diff the `FAIL:`/`ERROR:` name
lists.

The standard is **no new failure names**, not zero failures. Test *count* will
legitimately drop — `test_project_export.py` returns to its pre-`87c8fec8`
content, losing ~446 lines of natural-key tests, and `test_natural_keys.py` is
gone entirely. Failures that disappear are expected. Any failure name present
after but absent before is a regression and blocks the commit. Report both name
lists and both summary lines verbatim; do not round off or claim a clean run.

**3e. Commit** once 3a–3d pass:

```
git add -A
git commit -m "revert(api): drop natural-key matching from project export/import"
```

Commit body should note that `0291` was retained with its dependency rewired to
`0289_asyncjob`, and that `formatVersion` returns to 1.

## Scope

In scope: the 12 files listed in Task 2, plus the two comparison artifacts.

Out of scope (explicitly retained):
- `.planning/debug/offline-import-fk-constraint.md` — historical debug record.
- `djangoexact/api/migrations/0291_alter_fishery_ef_source_verbose_name.py` — kept,
  dependency rewired only.
- `compatibilityGroup` — never bumped, stays as-is.

No new abstractions, no new helper modules, no new tests. The shortest diff that
fully removes the mechanism.

## Risks

- **A dev/review DB that skips Task 2a** keeps 18 unique constraints enforced with
  no migration declaring them. Silent until a duplicate insert fails. Mitigated by
  2a; `showmigrations` makes the check cheap.
- **`--keepdb` on either test run** reuses a DB that still has the constraints and
  produces a misleading result. Both runs must omit it.
