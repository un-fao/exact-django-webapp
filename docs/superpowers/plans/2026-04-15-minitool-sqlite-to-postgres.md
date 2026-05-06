# Minitool: SQLite → Postgres Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Per the project's `CLAUDE.md`, implementation tasks (code edits) MUST be delegated to the `Backend Architect` agent via the `Agent` tool — plan reading, test runs, and git operations stay in the main session.

**Goal:** Move the `minitool` Django app's 7 models from a dedicated SQLite database (`djangoexact/minitool.db`) onto the project's default Postgres instance, so that future Cloud Run / Cloud Function jobs can write `ChangeRecord` rows back into the same database the Django webapp reads from.

**Architecture:** Delete the `minitool` entry from `DATABASES`, drop `minitool.db_router.AppSpecificDatabaseRouter` from `DATABASE_ROUTERS`, delete the router file, fix every real code-side usage of the `"minitool"` DB alias (two management commands, one test module, one standalone script), run fresh migrations on the default DB, and ship a documented one-shot conversion recipe for anyone with existing production data. This is **PR 1** of an eight-PR feature series — it is intentionally self-contained and revertable.

**Tech Stack:** Django 4.1, Python 3.11+, Postgres (default DB), `manage.py test` for the test runner, `git` for version control. No Celery, no GCP in this PR. Feature branch: `feature/minitool-sqlite-to-postgres` (already created off `develop`).

**Scope boundaries — what this PR does NOT do:**

- Does not touch `admin_scripts/` views, HTMX endpoints, or scenario builder UI.
- Does not introduce the YAML catalog, `ComputationJob` model, Cloud Run wiring, notifications, or the jobs panel (those are PRs 2–8).
- Does not touch `ipcc.db_router` or `api.db_router` (they're no-op routers pointing at `default`; harmless).
- Does not delete `djangoexact/minitool.db` from disk — it stays as a local artifact so the developer can roll back via `git revert` without losing data. `.gitignore` already excludes `*.db` (verified during Task 1).
- Does not migrate prod data automatically — prod cutover is a documented, reviewed, human-run script landing in Task 12.

---

## File Structure

**Files modified (all live edits):**

| File | Change | Reason |
|---|---|---|
| `djangoexact/djangoexact/settings.py` | Delete `"minitool"` entry from both `DATABASES` blocks; remove `"minitool.db_router.AppSpecificDatabaseRouter"` from `DATABASE_ROUTERS` | Remove the second-DB configuration |
| `djangoexact/minitool/management/commands/import_changes.py` | Replace `connections["minitool"]` with `connections["default"]` at two call sites; update the adjacent comment | Cursor calls must hit the new DB |
| `djangoexact/minitool/management/commands/cleanup_sqlite.py` | **Delete the file entirely** | SQLite-specific management command; the file references `settings.DATABASES["minitool"]["NAME"]` which no longer exists. Dead code after the move. |
| `djangoexact/admin_scripts/tests.py` | Change `databases = {"default", "minitool"}` → `databases = {"default"}` on 3 test classes | Tests previously needed both DBs; now only `default` |
| `djangoexact/scripts/minitool_import.py` | Replace `Model.objects.db_manager("minitool")` → `Model.objects` on 3 call sites | Use default manager |
| `djangoexact/minitool/tests.py` | **Add** new `RoutingRegressionTest` class that asserts `router.db_for_write(ChangeRecord) == "default"` (TDD guardrail) | Failing test proves the router is really gone |

**Files deleted:**

| File | Reason |
|---|---|
| `djangoexact/minitool/db_router.py` | The entire router class is obsolete once the DB alias is gone |
| `djangoexact/minitool/management/commands/cleanup_sqlite.py` | Dead code (see above) |

**Files created:**

| File | Purpose |
|---|---|
| `docs/migrations/2026-04-15-minitool-sqlite-to-postgres.md` | Documented one-shot prod cutover recipe (pgloader + verification queries) |

**Files explicitly left untouched:**

- `djangoexact/minitool/db_manager.py` — `managed_db_connection()` is DB-alias-agnostic (just wraps `connections.close_all()`), remains valid
- `djangoexact/minitool/middleware.py` — `DatabaseConnectionMiddleware` is DB-alias-agnostic, remains valid
- `djangoexact/minitool/models.py` — no `Meta.app_label` or `using=` overrides to change
- `djangoexact/minitool/migrations/*.py` — already account for the schema; Django will run them against `default` once the router is gone
- `djangoexact/ipcc/db_router.py`, `djangoexact/api/db_router.py` — unrelated no-op routers

---

## Prerequisites (environment)

Because `djangoexact/djangoexact/settings.py` uses literal `$DB_*` placeholders (substituted at deploy time), running any `manage.py` command locally requires these environment variables in the operator's shell **before starting Task 1**:

```bash
export DB_ENGINE=django.db.backends.postgresql
export DB_HOST=127.0.0.1        # or wherever your local Postgres lives
export DB_PORT=5432
export DB_NAME=djangoexact_dev  # must exist and be empty-or-compatible
export DB_USER=...
export DB_PASSWORD=...
```

Task 1 verifies these are working **before** any code is touched. If the operator does not have a local Postgres instance available, they must stop and provision one (Postgres.app, Docker, Colima, whatever they prefer) — this PR cannot land without one. **Do not attempt to complete this plan without a running Postgres.**

---

## Task 1: Baseline verification (read-only recon)

**Files:** none (this task only reads)

**Goal:** Confirm the environment is ready before touching any code. Catches the "no local Postgres" failure mode at the start, not halfway through.

- [ ] **Step 1: Confirm current branch**

Run: `git rev-parse --abbrev-ref HEAD`
Expected: `feature/minitool-sqlite-to-postgres`

If not, stop and ask.

- [ ] **Step 2: Confirm env vars are set and point at a real Postgres**

Run:
```bash
python -c "import os; [print(f'{k}={os.environ.get(k, \"<MISSING>\")}') for k in ['DB_ENGINE','DB_HOST','DB_PORT','DB_NAME','DB_USER']]"
```

Expected: every line has a real value (no `<MISSING>`, no literal `$DB_ENGINE`).

If any are missing, stop. Set them per the Prerequisites section. Do not proceed.

- [ ] **Step 3: Confirm Postgres is reachable**

Run:
```bash
cd djangoexact && python manage.py dbshell --database=default -- -c '\q'
```

Expected: exit code 0, no error. (The `\q` quits psql immediately.)

If this fails with a connection error, stop and fix Postgres. Do not proceed.

- [ ] **Step 4: Confirm current (pre-migration) test suite runs and gives a baseline**

Run:
```bash
cd djangoexact && python manage.py test minitool admin_scripts -v 2
```

Expected: all tests pass (or if any are already failing on `develop`, note which — they are the baseline and must still fail the *same way* after this PR, not more).

Record the exact baseline in a scratch note — it's the comparison set for Task 11.

- [ ] **Step 5: Confirm `minitool.db` is gitignored**

Run: `git check-ignore djangoexact/minitool.db`
Expected: prints `djangoexact/minitool.db`, exit 0.

If it's tracked, stop and ask — a 286 MB file should never be committed, and we need to figure out how it got there before proceeding.

- [ ] **Step 6: Confirm no stashed/staged work**

Run: `git status --short`
Expected: empty (clean tree).

---

## Task 2: Add the failing routing regression test

**Files:**
- Modify: `djangoexact/minitool/tests.py` (append a test class)

**Goal:** Add a TDD guardrail that asserts `ChangeRecord` routes to `"default"`. This test **must fail on the current code** (because the router still sends it to `"minitool"`), and **must pass** after Task 5 deletes the router. This is how we prove the move is real.

- [ ] **Step 1: Inspect the current test file**

Run: `wc -l djangoexact/minitool/tests.py && head -20 djangoexact/minitool/tests.py`

Note the import style used (Django `TestCase` vs `SimpleTestCase` vs pytest). The new test class must follow the existing convention.

- [ ] **Step 2: Delegate the edit to Backend Architect**

Use the `Agent` tool with `subagent_type="Backend Architect"`. Prompt:

> **Task:** Append one new test class to `djangoexact/minitool/tests.py` that asserts `ChangeRecord` routes to the `"default"` DB. This is a TDD guardrail for a PR that deletes `minitool.db_router.AppSpecificDatabaseRouter`. The test **must currently fail** on branch `feature/minitool-sqlite-to-postgres` (because the router is still active), and will pass once a later task removes the router.
>
> Append this class exactly (match the existing file's import style — add imports at the top if needed, otherwise reuse):
>
> ```python
> from django.db import router
> from django.test import SimpleTestCase
>
> from minitool.models import (
>     ChangeAggregate,
>     ChangeRecord,
>     EmissionScenario,
>     EmissionScenarioCategory,
>     EmissionStatisticsByModule,
>     Entry,
>     StatisticsModuleTotal,
> )
>
>
> class RoutingRegressionTest(SimpleTestCase):
>     """
>     Guardrail for the minitool SQLite → Postgres migration (PR 1).
>     After this PR lands, every minitool model must route to the default DB.
>     """
>
>     databases = {"default"}
>
>     def test_all_minitool_models_route_to_default(self):
>         models = [
>             Entry,
>             StatisticsModuleTotal,
>             EmissionStatisticsByModule,
>             ChangeRecord,
>             ChangeAggregate,
>             EmissionScenarioCategory,
>             EmissionScenario,
>         ]
>         for model in models:
>             with self.subTest(model=model.__name__):
>                 self.assertEqual(
>                     router.db_for_write(model),
>                     "default",
>                     f"{model.__name__} must route to default DB after migration",
>                 )
> ```
>
> If `minitool/tests.py` already imports some of these symbols, deduplicate — do not introduce a second `from django.test import ...` line. If the file already has a `SimpleTestCase` import, reuse it. The new class goes at the end of the file.
>
> Do not modify any other file. Do not run tests yourself — the caller will.

- [ ] **Step 3: Run the new test and confirm it fails**

Run:
```bash
cd djangoexact && python manage.py test minitool.tests.RoutingRegressionTest -v 2
```

Expected: **FAIL.** The failure message should say something like `"minitool" != "default"` for every model subtest. If the test passes, something is wrong — stop and investigate before proceeding (maybe the router was already removed in a previous run).

- [ ] **Step 4: Commit the failing test**

Run:
```bash
cd /Users/claudiolavacca/Developer/FAO/exact-django-webapp
git add djangoexact/minitool/tests.py
git commit -m "test(minitool): add routing regression test (currently failing)

TDD guardrail for the SQLite→Postgres migration. Asserts every minitool
model routes to the default DB. Will pass once AppSpecificDatabaseRouter
is removed."
```

---

## Task 3: Remove the minitool DB alias and router from settings

**Files:**
- Modify: `djangoexact/djangoexact/settings.py` (two `DATABASES` blocks + `DATABASE_ROUTERS`)

**Goal:** Eliminate the `"minitool"` DB alias from both the GAE-production and local-development branches of `DATABASES`, and drop the minitool router from `DATABASE_ROUTERS`.

- [ ] **Step 1: Delegate the edit to Backend Architect**

Use `Agent` with `subagent_type="Backend Architect"`. Prompt:

> **Task:** Edit `djangoexact/djangoexact/settings.py` to remove the `"minitool"` DB alias and router. Three precise edits:
>
> **Edit A — in the `if os.getenv("GAE_APPLICATION", None):` branch (~line 132).**
> Delete this entire block (keep the closing `}` of the outer dict):
> ```python
>         "minitool": {
>             "ENGINE": "django.db.backends.sqlite3",
>             "NAME": os.path.join(BASE_DIR, "minitool.db"),
>             "OPTIONS": {
>                 "timeout": 20,
>                 "check_same_thread": False,
>             },
>         },
> ```
>
> **Edit B — in the `else:` branch (~line 159).** Delete:
> ```python
>         "minitool": {
>             "ENGINE": "django.db.backends.sqlite3",
>             "NAME": os.path.join(BASE_DIR, "minitool.db"),
>         },
> ```
>
> **Edit C — on the `DATABASE_ROUTERS = [...]` line (~line 180).** Change:
> ```python
> DATABASE_ROUTERS = ["minitool.db_router.AppSpecificDatabaseRouter", "ipcc.db_router.AppSpecificDatabaseRouter", "api.db_router.AppSpecificDatabaseRouter"]
> ```
> to:
> ```python
> DATABASE_ROUTERS = ["ipcc.db_router.AppSpecificDatabaseRouter", "api.db_router.AppSpecificDatabaseRouter"]
> ```
>
> Do not change anything else in the file. Do not reformat surrounding lines. Do not run tests.

- [ ] **Step 2: Eyeball the diff**

Run: `git diff djangoexact/djangoexact/settings.py`

Expected: exactly three deletions matching Edits A/B/C above. Any extra lines changed → reject and retry.

- [ ] **Step 3: Verify Django can still import settings**

Run:
```bash
cd djangoexact && python -c "import django; django.setup()" 2>&1 | head -30
```

Wait — `django.setup()` needs `DJANGO_SETTINGS_MODULE`. Use the real command:

```bash
cd djangoexact && python manage.py check 2>&1 | tail -20
```

Expected: `System check identified no issues (0 silenced).` or similar clean output. If it errors about a missing `"minitool"` DB alias somewhere, that's a signal Task 4/5 must happen before commit — note the error and proceed.

- [ ] **Step 4: Do NOT commit yet** — settings change pairs with Task 4 router deletion; both land in one atomic commit in Task 4.

---

## Task 4: Delete the minitool database router

**Files:**
- Delete: `djangoexact/minitool/db_router.py`

**Goal:** Remove the now-dead router class and commit settings + router removal together.

- [ ] **Step 1: Delete the file**

Run:
```bash
cd /Users/claudiolavacca/Developer/FAO/exact-django-webapp
git rm djangoexact/minitool/db_router.py
```

Expected: `rm 'djangoexact/minitool/db_router.py'`

- [ ] **Step 2: Confirm nothing imports it**

Run:
```bash
cd djangoexact && python -c "
import ast, pathlib
for p in pathlib.Path('.').rglob('*.py'):
    try:
        tree = ast.parse(p.read_text())
    except SyntaxError:
        continue
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module and 'minitool.db_router' in node.module:
            print(f'STILL IMPORTS: {p}:{node.lineno}')
        if isinstance(node, ast.Import):
            for alias in node.names:
                if 'minitool.db_router' in alias.name:
                    print(f'STILL IMPORTS: {p}:{node.lineno}')
"
```

Expected: no output (no file still imports the router).

- [ ] **Step 3: Run the routing regression test from Task 2**

Run:
```bash
cd djangoexact && python manage.py test minitool.tests.RoutingRegressionTest -v 2
```

Expected: **PASS.** Every model subtest now reports `router.db_for_write(...) == "default"`. If it still fails, something else is routing to `"minitool"` — stop and investigate.

- [ ] **Step 4: Commit the settings + router removal atomically**

Run:
```bash
cd /Users/claudiolavacca/Developer/FAO/exact-django-webapp
git add djangoexact/djangoexact/settings.py djangoexact/minitool/db_router.py
git commit -m "feat(minitool): remove sqlite DB alias and router

Drop the 'minitool' entry from DATABASES (both GAE and local branches)
and delete minitool/db_router.py. Minitool models now route to the
default Postgres DB. Routing regression test from the previous commit
now passes."
```

---

## Task 5: Fix `import_changes` to use the default connection

**Files:**
- Modify: `djangoexact/minitool/management/commands/import_changes.py` (lines ~78 and ~123)

**Goal:** Replace the two `connections["minitool"]` call sites with `connections["default"]` and update the adjacent comments.

- [ ] **Step 1: Delegate the edit to Backend Architect**

Use `Agent` with `subagent_type="Backend Architect"`. Prompt:

> **Task:** Edit `djangoexact/minitool/management/commands/import_changes.py`. Two find-and-replace operations, each unique in the file:
>
> **Edit A — around line 77–78.** Replace:
> ```python
>         # Use the minitool database connection
>         minitool_connection = connections["minitool"]
> ```
> with:
> ```python
>         # Use the default database connection (minitool app moved to default DB)
>         minitool_connection = connections["default"]
> ```
>
> **Edit B — around line 122–123.** Replace:
> ```python
>         # Use the minitool database connection
>         minitool_connection = connections["minitool"]
> ```
> with:
> ```python
>         # Use the default database connection (minitool app moved to default DB)
>         minitool_connection = connections["default"]
> ```
>
> Leave the local variable name `minitool_connection` as-is — renaming it is unnecessary churn. Do not touch any other line in the file.

- [ ] **Step 2: Verify the diff**

Run: `git diff djangoexact/minitool/management/commands/import_changes.py`

Expected: exactly two hunks, each changing `"minitool"` → `"default"` and updating the comment above it.

- [ ] **Step 3: Syntax-check the command**

Run:
```bash
cd djangoexact && python manage.py help import_changes 2>&1 | head -20
```

Expected: the help text prints without error.

- [ ] **Step 4: Commit**

Run:
```bash
git add djangoexact/minitool/management/commands/import_changes.py
git commit -m "fix(minitool): use default DB connection in import_changes"
```

---

## Task 6: Update `admin_scripts/tests.py` to drop the minitool DB

**Files:**
- Modify: `djangoexact/admin_scripts/tests.py` (lines 84, 187, 467)

**Goal:** Three test classes declare `databases = {"default", "minitool"}` so Django creates test DBs for both. Now there's only one.

- [ ] **Step 1: Delegate the edit to Backend Architect**

Use `Agent` with `subagent_type="Backend Architect"`. Prompt:

> **Task:** In `djangoexact/admin_scripts/tests.py`, replace every occurrence of:
> ```python
>     databases = {"default", "minitool"}
> ```
> with:
> ```python
>     databases = {"default"}
> ```
>
> Per the grep earlier, there are exactly 3 occurrences (lines 84, 187, 467). Do not touch any other line. Do not reorder set literals. If any occurrence is a `frozenset(...)` or list `["default", "minitool"]` instead, still swap to `{"default"}`.

- [ ] **Step 2: Verify the diff**

Run: `git diff djangoexact/admin_scripts/tests.py`

Expected: exactly 3 single-line changes.

- [ ] **Step 3: Run the admin_scripts test suite**

Run:
```bash
cd djangoexact && python manage.py test admin_scripts -v 2
```

Expected: the tests that were passing on `develop` still pass. Some may fail with "ChangeRecord table does not exist" — that's expected if Task 9 (the migration) hasn't run yet. Note which tests fail for that reason; they must pass by end of Task 10.

- [ ] **Step 4: Commit**

Run:
```bash
git add djangoexact/admin_scripts/tests.py
git commit -m "test(admin_scripts): drop minitool DB from test databases set"
```

---

## Task 7: Fix `scripts/minitool_import.py` db_manager calls

**Files:**
- Modify: `djangoexact/scripts/minitool_import.py` (3 call sites)

**Goal:** Replace `Entry.objects.db_manager("minitool").bulk_create(...)` and the two `StatisticsModuleTotal.objects.db_manager("minitool").bulk_create(...)` with the plain default manager.

- [ ] **Step 1: Delegate the edit to Backend Architect**

Use `Agent` with `subagent_type="Backend Architect"`. Prompt:

> **Task:** In `djangoexact/scripts/minitool_import.py`, replace:
>
> - `Entry.objects.db_manager("minitool").bulk_create(entries)` → `Entry.objects.bulk_create(entries)`
> - `StatisticsModuleTotal.objects.db_manager("minitool").bulk_create(entries, ignore_conflicts=True)` → `StatisticsModuleTotal.objects.bulk_create(entries, ignore_conflicts=True)` (this occurs **twice** in the file)
>
> Three total edits. No other changes. Preserve existing indentation exactly.

- [ ] **Step 2: Verify the diff**

Run: `git diff djangoexact/scripts/minitool_import.py`

Expected: exactly 3 changes, each removing `.db_manager("minitool")` from the method chain.

- [ ] **Step 3: Byte-compile the script**

Run:
```bash
python -m py_compile djangoexact/scripts/minitool_import.py && echo OK
```

Expected: `OK`.

- [ ] **Step 4: Commit**

Run:
```bash
git add djangoexact/scripts/minitool_import.py
git commit -m "fix(scripts): drop db_manager(\"minitool\") from minitool_import"
```

---

## Task 8: Delete the dead `cleanup_sqlite` management command

**Files:**
- Delete: `djangoexact/minitool/management/commands/cleanup_sqlite.py`

**Goal:** This command references `settings.DATABASES["minitool"]["NAME"]`, which no longer exists. After the move it's dead code — running it would raise `KeyError`.

- [ ] **Step 1: Sanity-check that the file really is SQLite-only**

Run:
```bash
cat djangoexact/minitool/management/commands/cleanup_sqlite.py
```

Expected: a short command whose only purpose is vacuuming/cleaning the SQLite file. If it does anything else (e.g. has Postgres-compatible logic mixed in), stop and ask — do not delete blindly.

- [ ] **Step 2: Confirm nothing references it**

Run:
```bash
cd djangoexact && grep -rn "cleanup_sqlite" --include="*.py" --include="*.yml" --include="*.yaml" .
```

Expected: only the file itself (one hit) or zero hits outside the file. No CI pipeline, cron, or other Python module invokes it.

- [ ] **Step 3: Delete the file**

Run:
```bash
cd /Users/claudiolavacca/Developer/FAO/exact-django-webapp
git rm djangoexact/minitool/management/commands/cleanup_sqlite.py
```

- [ ] **Step 4: Commit**

Run:
```bash
git commit -m "chore(minitool): remove dead cleanup_sqlite management command

This command only operates on djangoexact/minitool.db (SQLite-specific
VACUUM logic). With minitool moved to Postgres, the command would
KeyError on settings.DATABASES[\"minitool\"]. Dead code — delete."
```

---

## Task 9: Create minitool tables on the default Postgres DB

**Files:** none modified; this runs a migration.

**Goal:** Django now sees all 27 minitool migrations as pending on the default DB (previously they were confined to the SQLite alias). Apply them.

- [ ] **Step 1: Verify migrations are pending**

Run:
```bash
cd djangoexact && python manage.py showmigrations minitool
```

Expected: 27 migrations listed, **all unapplied** (no `[X]` marks) on the default connection. If any are marked applied, stop and ask — the target Postgres already has minitool state, which contradicts the option-(a) plan.

- [ ] **Step 2: Apply migrations**

Run:
```bash
cd djangoexact && python manage.py migrate minitool
```

Expected: all 27 migrations applied, exit 0, no `OperationalError`. If a migration fails due to a Postgres-vs-SQLite SQL incompatibility, **STOP** and surface the specific migration file — that's a real problem that needs human judgment.

- [ ] **Step 3: Verify tables exist**

Run:
```bash
cd djangoexact && python manage.py dbshell --database=default -- -c "\dt minitool_*"
```

Expected: a list including (at minimum) `minitool_entry`, `minitool_statisticsmoduletotal`, `minitool_emissionstatisticsbymodule`, `minitool_changerecord`, `minitool_changeaggregate`, `minitool_emissionscenariocategory`, `minitool_emissionscenario`.

- [ ] **Step 4: Do not commit** — no files changed in this task; the migration state lives in the DB, not git.

---

## Task 10: Run the full test suite

**Files:** none (verification only)

**Goal:** Compare against the Task 1 baseline and confirm no regressions.

- [ ] **Step 1: Run the minitool tests**

Run:
```bash
cd djangoexact && python manage.py test minitool -v 2
```

Expected: all tests that passed on `develop` pass here. `RoutingRegressionTest.test_all_minitool_models_route_to_default` passes.

- [ ] **Step 2: Run the admin_scripts tests**

Run:
```bash
cd djangoexact && python manage.py test admin_scripts -v 2
```

Expected: all tests pass. The ones that failed in Task 6 Step 3 (due to missing tables) must now pass, because Task 9 created the tables.

- [ ] **Step 3: Run the api tests (blast radius check)**

Run:
```bash
cd djangoexact && python manage.py test api -v 2
```

Expected: no regressions vs the baseline from Task 1. This catches any cross-app dependency on the minitool DB we may have missed.

- [ ] **Step 4: If anything failed that was not failing in the Task 1 baseline**, STOP. Do not commit a "fix" without understanding the failure. Options: (a) return to Task 2–8 and verify the edit is right, (b) surface to the user.

---

## Task 11: Remove `DatabaseConnectionMiddleware` defensively? (NO)

**Decision:** Keep `minitool.middleware.DatabaseConnectionMiddleware` and its registration in `MIDDLEWARE` untouched. The middleware calls `connections.close_all()` after each response, which is still meaningful behavior (closes the default Postgres connection) and removing it is out of scope for this PR. If anyone wants to reconsider it later, that's a separate refactor.

This task exists as a **no-op marker** so the execution log shows that the middleware was deliberately left alone, not forgotten.

- [ ] **Step 1: Sanity-check that `MIDDLEWARE` still lists it**

Run:
```bash
grep -n "DatabaseConnectionMiddleware" djangoexact/djangoexact/settings.py
```

Expected: one hit, unchanged from `develop`.

- [ ] **Step 2: Nothing to commit.**

---

## Task 12: Document the one-shot production migration

**Files:**
- Create: `docs/migrations/2026-04-15-minitool-sqlite-to-postgres.md`

**Goal:** Produce a reviewable recipe that someone with production data can run against a real deployment. This is explicitly **not executed** in this PR — it's a document.

- [ ] **Step 1: Ensure the directory exists**

Run:
```bash
mkdir -p /Users/claudiolavacca/Developer/FAO/exact-django-webapp/docs/migrations
```

- [ ] **Step 2: Write the document**

Use the `Write` tool to create `docs/migrations/2026-04-15-minitool-sqlite-to-postgres.md` with this content verbatim:

````markdown
# Minitool: SQLite → Postgres production cutover

**Status:** Manual. One-shot. Run only by an operator with DB credentials.
**Applies to:** Any environment (staging, prod) that still has a populated `djangoexact/minitool.db` SQLite file after the code change landed.

## Why

PR 1 of the scenario-builder-async-computation feature moves the `minitool` Django app off its dedicated SQLite DB (`djangoexact/minitool.db`) and onto the project's default Postgres instance. The code change is revertable via `git revert`; the data migration is a one-way operation and must be done deliberately, per environment, by a human.

## Preconditions

1. The new code (post-PR 1) is deployed and `manage.py migrate minitool` has been run against the default Postgres, producing empty tables.
2. The old `djangoexact/minitool.db` file still exists in the environment (verify with `ls -lh`).
3. The environment is in a maintenance window — `admin_scripts` is staff-only, so the blast radius is small, but new `ChangeRecord` writes during the cutover would be lost.
4. `pgloader` is available on the host running the migration. `brew install pgloader` on macOS; `apt-get install pgloader` on Debian/Ubuntu. Alternatively, Django `dumpdata` + `loaddata` works for databases under ~100MB — our file is 286 MB, so prefer pgloader.

## Option A — pgloader (recommended for >100MB files)

```bash
# 1. Take a snapshot of the source SQLite file (read-only cutover safety).
cp djangoexact/minitool.db /tmp/minitool-pre-cutover.db

# 2. Run pgloader with a command file that maps all 7 tables.
cat > /tmp/minitool-migrate.load <<'EOF'
LOAD DATABASE
  FROM sqlite:///tmp/minitool-pre-cutover.db
  INTO postgresql://DB_USER:DB_PASSWORD@DB_HOST:DB_PORT/DB_NAME

  WITH data only, truncate, disable triggers, reset sequences

  SET work_mem to '64MB', maintenance_work_mem to '512MB'

  CAST type datetime to timestamptz
       drop default drop not null using zero-dates-to-null,
       type date drop not null drop default using zero-dates-to-null

  INCLUDING ONLY TABLE NAMES MATCHING
    'minitool_entry',
    'minitool_statisticsmoduletotal',
    'minitool_emissionstatisticsbymodule',
    'minitool_changerecord',
    'minitool_changeaggregate',
    'minitool_emissionscenariocategory',
    'minitool_emissionscenario';
EOF

pgloader /tmp/minitool-migrate.load
```

**Expected output:** a summary table showing rows copied per table, zero errors.

## Option B — Django dumpdata/loaddata (safe for small datasets)

```bash
# 1. Dump from the SQLite alias (still accessible via Django if you temporarily
#    re-add the DATABASES["minitool"] block and the router).
python manage.py dumpdata minitool \
  --database=minitool \
  --natural-primary --natural-foreign \
  --indent 2 \
  -o /tmp/minitool-dump.json

# 2. Deploy the PR 1 code change (removes the alias).

# 3. Load into default Postgres.
python manage.py loaddata /tmp/minitool-dump.json --database=default
```

**Warning:** For a 286 MB SQLite file, the JSON dump can exceed 1 GB and `loaddata` can take >30 minutes. Option A is strongly preferred at this scale.

## Verification

Run these queries against the target Postgres and compare row counts against the source SQLite:

```bash
# Source counts
sqlite3 /tmp/minitool-pre-cutover.db "
SELECT 'entry', COUNT(*) FROM minitool_entry UNION ALL
SELECT 'stat_total', COUNT(*) FROM minitool_statisticsmoduletotal UNION ALL
SELECT 'emission_stat', COUNT(*) FROM minitool_emissionstatisticsbymodule UNION ALL
SELECT 'changerecord', COUNT(*) FROM minitool_changerecord UNION ALL
SELECT 'change_agg', COUNT(*) FROM minitool_changeaggregate UNION ALL
SELECT 'category', COUNT(*) FROM minitool_emissionscenariocategory UNION ALL
SELECT 'scenario', COUNT(*) FROM minitool_emissionscenario;
"

# Destination counts
python manage.py dbshell --database=default -- -c "
SELECT 'entry', COUNT(*) FROM minitool_entry UNION ALL
SELECT 'stat_total', COUNT(*) FROM minitool_statisticsmoduletotal UNION ALL
SELECT 'emission_stat', COUNT(*) FROM minitool_emissionstatisticsbymodule UNION ALL
SELECT 'changerecord', COUNT(*) FROM minitool_changerecord UNION ALL
SELECT 'change_agg', COUNT(*) FROM minitool_changeaggregate UNION ALL
SELECT 'category', COUNT(*) FROM minitool_emissionscenariocategory UNION ALL
SELECT 'scenario', COUNT(*) FROM minitool_emissionscenario;
"
```

Every row count must match. If any differ, **rollback** (see below) and investigate.

## Rollback

Rollback is the `git revert` of the PR 1 commits plus restoring `minitool.db` from `/tmp/minitool-pre-cutover.db`. Because PR 1's code change is self-contained and PR 2 does not depend on any data being in the new Postgres tables, rollback is low-risk for the first week after cutover.

After a successful, verified cutover, delete the snapshot:

```bash
rm /tmp/minitool-pre-cutover.db /tmp/minitool-migrate.load /tmp/minitool-dump.json
```
````

- [ ] **Step 3: Commit**

Run:
```bash
cd /Users/claudiolavacca/Developer/FAO/exact-django-webapp
git add docs/migrations/2026-04-15-minitool-sqlite-to-postgres.md
git commit -m "docs(minitool): add SQLite→Postgres production cutover recipe"
```

---

## Task 13: Final sanity pass

**Files:** none (verification only)

- [ ] **Step 1: Re-run the full test suite one more time**

Run:
```bash
cd djangoexact && python manage.py test -v 1 2>&1 | tail -20
```

Expected: same pass/fail profile as `develop`, plus the new `RoutingRegressionTest` passing.

- [ ] **Step 2: Confirm the commit log is clean**

Run:
```bash
git log --oneline develop..HEAD
```

Expected: roughly 7 commits, each scoped and message-ful:

```
docs(minitool): add SQLite→Postgres production cutover recipe
chore(minitool): remove dead cleanup_sqlite management command
fix(scripts): drop db_manager("minitool") from minitool_import
test(admin_scripts): drop minitool DB from test databases set
fix(minitool): use default DB connection in import_changes
feat(minitool): remove sqlite DB alias and router
test(minitool): add routing regression test (currently failing)
```

- [ ] **Step 3: Confirm no orphan references to `"minitool"` DB alias remain in code**

Run:
```bash
cd djangoexact && grep -rn '"minitool"\|'"'"'minitool'"'"'' \
  --include="*.py" . \
  | grep -v "_meta.app_label" \
  | grep -v "INSTALLED_APPS" \
  | grep -v "migrations/" \
  | grep -E 'connections\[|databases\s*=|db_manager\(|DATABASES\[|DATABASE_ROUTERS' \
  || echo "CLEAN"
```

Expected: `CLEAN`. Any hit means a usage of the alias was missed — stop and fix before handing off.

- [ ] **Step 4: Done.** The feature branch is ready for finishing-a-development-branch review.

---

## Open questions / flag for user

These do NOT block PR 1, but MUST be addressed before PR 6 is planned:

1. **Pre-existing `gcp-deployment/cloud-function/main.py` — "minitool-processor" Cloud Function.** During recon I discovered there is already a Cloud Function that imports `minitool`, uses `PermutationComputer`, and orchestrates permutation runs remotely. This overlaps heavily with what PR 6 of the original design spec was meant to introduce (the Cloud Run Job). Before writing PR 6's plan, we need to decide: (a) extend/replace the existing Cloud Function, (b) run both side-by-side, (c) retire the Cloud Function in favor of the new Cloud Run Job. This is a **design re-decision** that belongs in a follow-up brainstorming session, not in PR 1 or PR 2.

2. **Settings placeholder-vs-env-var hybrid.** The current `DATABASES` block uses literal `$DB_ENGINE`-style placeholders as fallbacks, which means any developer whose shell doesn't set `DB_ENGINE` gets a literal `"$DB_ENGINE"` string and a Django error. This is not new and not caused by PR 1, but it's a sharp edge. Consider a follow-up PR replacing the `$...` placeholders with `os.getenv(..., default="django.db.backends.postgresql")`-style safe defaults. Noted here so it's not forgotten.

3. **Test DB creation for Postgres.** Django creates a `test_<DB_NAME>` database when `manage.py test` runs. The user's Postgres role must have `CREATEDB` privilege. If Task 1 Step 4 hits `permission denied to create database`, the resolution is either `GRANT CREATE ON DATABASE` or `ALTER USER ... CREATEDB;`. Document on the user's own local notes.
