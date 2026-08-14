---
slug: offline-import-fk-constraint
status: fix_committed_awaiting_deploy
trigger: "despite the latest changes applied, importing an online .exactp into the offline tool, still gives me FOREIGN KEY constraint failed"
created: 2026-08-14
updated: 2026-08-14
---

# Debug: online .exactp import into offline tool fails with FOREIGN KEY constraint failed

## Symptoms

**Expected behavior**
A `.exactp` project file exported from the online (Cloud SQL / PostgreSQL) EX-ACT tool imports cleanly into the offline tool, with all reference-data foreign keys resolved by natural key.

**Actual behavior**
Import fails with `FOREIGN KEY constraint failed` (SQLite-level integrity error surfacing through the API).

**Error messages**
Only the API error message is available: `FOREIGN KEY constraint failed`. No server-side traceback captured yet. Capturing the full traceback (which model/field/row triggers it) is a primary early investigation step.

**Timeline**
- Offline -> offline import works.
- Online -> offline import fails.
- Persists after PR #274 (`fix/export-import-reference-data-identity`, merged as 1ecb371f) which introduced natural-key declaration + natural-key FK resolution on import:
  - bf7f906d `feat(api): declare reference-data natural keys and enforce uniqueness behind them`
  - 87c8fec8 `fix(api): resolve reference-data FKs by natural key on project import`
  - b98175e6 docs
  - 6190429f `feat(offline): build the offline reference database from fixtures instead of a committed sqlite snapshot`

**Reproduction**
1. Export a project as `.exactp` from the online tool.
2. In the offline tool (latest code, DB rebuilt from fixtures via `migrate` + `load_reference_data --app=all`), use the import button in the UI.
3. Import fails with `FOREIGN KEY constraint failed`.

**Environment facts confirmed with user**
- Offline tool IS running the latest code (post PR #274) AND its database was rebuilt from fixtures (not the old committed `db.sqlite3` snapshot). This rules out the stale-snapshot explanation recorded in prior memory for the earlier "reference data IDs do not match" bug.
- Import performed through the offline tool's UI (API import endpoint), not a management command.

## Relevant code (starting points)

- `djangoexact/api/natural_keys.py` - natural key declarations introduced by PR #274
- `djangoexact/api/reference_parity.py`
- `djangoexact/api/views.py` - project import/export endpoints
- `djangoexact/api/management/commands/check_reference_natural_keys.py`
- `djangoexact/api/management/commands/verify_reference_parity.py`
- `djangoexact/api/tests/test_project_export.py`
- `djangoexact/ipcc/migrations/0065_gwp_natural_key_constraint.py`

## Current Focus

bug_class: Bohrbug (deterministic, reproduces on every online -> offline import)

hypothesis: CONFIRMED and fixed. The `.exactp` files the user is importing are formatVersion 1,
  because the ONLINE production deployment does not yet run PR #274. A v1 payload carries no
  `<field>__nk` natural keys, so `prepare_model_data`'s `reference_pk()` returned None for every
  reference FK and the raw online integer PK was written through unchanged. `Project.gw_potential`
  is NOT NULL and the online payloads carry `gw_potential = 1`, which does not exist in the
  fixture-built offline DB (fixture pks are 8-12). SQLite's DEFERRED FK check then failed at
  COMMIT with no table or column, which is the reported string.

test: done. Payload-vs-fixture cross-check over six real `.exactp` files, then a full
  ablation on a fixture-built SQLite database.

expecting: done. The ablation reproduced the violation on exactly the predicted column.

next_action: DEPLOY. The code fix is committed on `develop` (see Resolution). The user has
  chosen to ship PR #274 to the `review` branch, not `main`, and to re-export the project from
  the review environment. That merge and push are NOT yet performed: they are outward-facing
  deploy actions the user authorised as a direction, not as an execution step. See
  "Deploy sequence (review path)" below, including a blocking workflow-trigger defect
  (`.github/workflows/deploy.yaml` does not fire on a push to `review`).
  Session stays OPEN: the user's original goal (importing their existing v1 file) is not
  achieved and cannot be until the re-export happens.

## Evidence

- timestamp: 2026-08-14 phase-1
  checked: `git show 87c8fec8` (import path) and `djangoexact/api/serializers.py:705,764,796` (export path)
  found: natural keys are emitted ONLY when the exporting installation runs PR #274 (`"formatVersion": 2` hardcoded at `views.py:926`). On import, `reference_pk(field, field_name)` reads `data.get(f"{field_name}__nk")` and returns None when absent, and both call sites then do `result[f"{field_name}_id"] = value if resolved is None else resolved`.
  implication: the entire natural-key fix is inert for a formatVersion 1 payload. v1 falls back to writing the raw exporting-installation integer PK, which is the pre-#274 behaviour that fails.

- timestamp: 2026-08-14 phase-1
  checked: `head` of every `.exactp` in ~/Downloads, with mtimes
  found: three files exported today 2026-08-14 at 12:51 UTC (`Liberia - HiH 2026 (Copy).exactp`, `test0406 (1) (2) (1) (1) (1).exactp`, `test 2807 (1).exactp`) are all `"formatVersion": 1`. The only `"formatVersion": 2` file (`test may 2026 (Copy) (Copy).exactp`, 12:56 UTC) carries full `__nk` keys.
  implication: DIRECT OBSERVATION that the online tool still emits v1. The offline/local build emits v2. The user updated the importing side only; the exporting side is the one that has to change for #274 to engage.

- timestamp: 2026-08-14 phase-1
  checked: project-level reference FKs in the v1 online exports vs `djangoexact/ipcc/fixtures/globalwarmingpotential.json`
  found: all three v1 online exports carry `gw_potential = 1` with no `gw_potential__nk`. The fixtures define GlobalWarmingPotential at pk 8, 9, 10, 11, 12 only. The v2 export carries `gw_potential = 11` with `gw_potential__nk = ["IPCC Fifth Assessment Report (AR5) without Climate Change Feedback"]`.
  implication: pk 1 does not exist in a fixture-built offline database. `Project.gw_potential` is NOT NULL, so the very first insert (`Project.objects.create`) violates the FK. This matches, verbatim, the prediction already written into `api/natural_keys.py:138-142`.

- timestamp: 2026-08-14 phase-3 (hypothesis test)
  checked: wrote a Django-introspection cross-check (scratchpad `xcheck.py`) that walks Project / Activity / every module and submodule in a payload, and for each ForeignKey with an integer value compares the value against the pk set in the committed fixtures. No DB connection, model metadata only. Ran it over all six `.exactp` files on disk.
  found:
    - `Liberia - HiH 2026 (Copy).exactp` (v1): exactly ONE violation, `Project.gw_potential = 1` -> `ipcc.globalwarmingpotential`, registered=True, nk_in_file=False, nullable=False.
    - `test0406 ... .exactp` (v1) and `20260810.exactp` (v1): same single violation.
    - `test 2807 (1).exactp` (v1): the same `gw_potential = 1`, PLUS `TransportEntry.fuel_type_start/_w/_wo = 51` and `= 52` -> `api.fueltype` (fixture pks are 18-60 but 51 and 52 are absent), registered=True, nk_in_file=False, nullable=True.
    - `test may 2026 (Copy) (Copy).exactp` (v2): ZERO violations. Every reference relation carries a natural key.
    - `GUINEA PDACG (1).exactp` (v1, exported 2026-06-22): ZERO violations, so a v1 file is not automatically broken. It only breaks when it happens to name a pk the two installations disagree on.
  implication: HYPOTHESIS CONFIRMED at mechanism level. The failing FK is `api_project.gw_potential_id`, hit on the FIRST insert of the import. `api.FuelType` is a second, later-firing instance of the same defect. The v2 file proves the #274 machinery is correct when it is fed a v2 payload, which isolates the defect to the v1 path.

- timestamp: 2026-08-14 phase-3 (deployment check)
  checked: `git merge-base --is-ancestor 87c8fec8 origin/main` and `... origin/review`, plus `.github/workflows/deploy.yaml:215,223` (production deploys from `main`)
  found: `87c8fec8` is NOT an ancestor of `origin/main` and NOT an ancestor of `origin/review`. `git branch -a --contains 87c8fec8` lists only `develop`, `fix/export-import-reference-data-identity` and `release/offline-tool`.
  implication: the online production tool is running `main` (`beb7fe10`, v1.20.3), which predates PR #274. It therefore still hardcodes `"formatVersion": 1` at the export endpoint. The export side of the fix has never been deployed. This is the third confirmed contributing cause, and it is the one that decides whether the user is unblocked.

- timestamp: 2026-08-14 phase-3 (divergence direction)
  checked: `api/fixtures/fueltype.json` pk range, and the pk ranges quoted in `.planning/quick/260813-fvj-.../260813-fvj-DUPLICATES.md`
  found: FuelType fixtures hold 19 rows across pks 18-60 with 51 and 52 absent; GWP fixtures hold pks 8-12. The online export uses GWP pk 1 and FuelType pks 51/52. `api/natural_keys.py:139-141` records the shipped offline snapshot as GWP 1-5.
  implication: the committed fixtures are the outlier, not production. The old shipped `db.sqlite3` snapshot (GWP 1-5) happened to AGREE with production, which is why online -> offline v1 imports used to work for `gw_potential`. Commit 6190429f (build the offline DB from fixtures) is what moved the offline side onto the 8-12 range and so exposed the latent defect. Realigning fixture pks to production is not a code fix and needs production access; the natural-key architecture is the correct answer and already exists, but only for v2 payloads.

- timestamp: 2026-08-14 phase-5 (why the message had no detail)
  checked: `select sql from sqlite_master where name='api_project'` on the fixture-built database
  found: `"gw_potential_id" bigint NOT NULL REFERENCES "ipcc_globalwarmingpotential" ("id") DEFERRABLE INITIALLY DEFERRED`. Django emits every SQLite FK as DEFERRABLE INITIALLY DEFERRED.
  implication: the constraint is NOT checked at INSERT, it is checked at COMMIT. `import_project` commits at the end of its `transaction.atomic()` block, so the violation fired after the whole project tree had been created and was caught by the blanket `except Exception`. SQLite's commit-time deferred error carries no table and no column, only the literal string `FOREIGN KEY constraint failed`. This explains the total absence of locality in the reported symptom, and it is why the pre-insert check is worth more than the error text alone suggests.

- timestamp: 2026-08-14 phase-6 (deploy topology, for the review-path decision)
  checked: `.github/workflows/deploy.yaml` trigger block and `deploy` job condition; `grep` for
    `check_reference_natural_keys` / `verify_reference_parity` across `.github/`,
    `bitbucket-pipelines.yml` and `deploy/`; `.env.review` vs `.env.production` at both the repo
    root and `djangoexact/djangoexact/`.
  found:
    - `on.push.branches` lists ONLY `main`. `review` and `develop` are present but COMMENTED OUT.
      `on.pull_request.branches` likewise lists only `main`.
    - The `deploy` job's own `if:` DOES accept `review` (`github.ref_name == 'review'`) and it
      selects `environment: review` and `APP_MODE: review`. So the job is written for review, but
      the workflow it lives in never starts on a push to `review`.
    - Neither `check_reference_natural_keys` nor `verify_reference_parity` appears anywhere in
      CI. There is NO automated pre-migration gate; the deploy step runs bare
      `python manage.py check --deploy` then `python manage.py migrate`.
    - `.env.review` and `.env.production` both declare `DB_NAME=exact`, `DB_USER=exact_user`,
      `DB_HOST=localhost`, `DB_PORT=5432` - byte-identical DB identity. The commented block in
      the root `.env` differs only by port (review 5542, production 5432), same `DB_NAME=exact`,
      same `DB_USER=exact_user`. Firebase DOES differ (`fao-exact-review` vs `fao-exact`).
  implication: two consequences for the chosen review path. (1) Merging `develop` -> `review`
    and pushing will deploy NOTHING until the `review` trigger is uncommented; the change would
    sit unshipped and the re-export would still produce formatVersion 1, reproducing the
    original symptom and looking like the fix failed. (2) The repo CANNOT confirm that review
    uses a database separate from production - the real values come from GitHub Actions
    environment-scoped `vars.DB_INSTANCE_CONNECTION` / `vars.DB_NAME`, which are not in the
    repo, and every DB field visible here is identical between the two profiles. This must be
    confirmed out-of-band BEFORE migrating, because `migrate` runs unguarded in the deploy step.

## Reasoning Checkpoint

```yaml
reasoning_checkpoint:
  hypothesis: >
    The importer writes a foreign installation's private primary key straight into a
    local FK column whenever the payload carries no natural key for that relation.
    A formatVersion 1 payload never carries one, so every reference FK in it is
    written unverified. `Project.gw_potential` is NOT NULL and the online payload
    names GWP pk 1, which no fixture-built offline database has, so the first
    INSERT trips SQLite's immediate FK enforcement and surfaces as the bare string
    "FOREIGN KEY constraint failed".
  confirming_evidence:
    - "Direct read of views.py:1080-1132: reference_pk() returns None when `<field>__nk` is absent, and both call sites then do `result[f'{field_name}_id'] = value if resolved is None else resolved`."
    - "Direct observation: the three .exactp files exported 2026-08-14 12:51 UTC are formatVersion 1 with no __nk keys anywhere."
    - "Direct comparison: ipcc/fixtures/globalwarmingpotential.json defines pks 8-12 only; the payloads carry gw_potential = 1."
    - "Direct check: Project.gw_potential (api/models.py:782) is a ForeignKey with no null=True and no default, so the value cannot be dropped."
    - "Introspection sweep over all six files: the v2 file has zero out-of-range reference FKs; the v1 files have exactly the ones predicted."
    - "git merge-base: 87c8fec8 is not an ancestor of origin/main, so the online exporter genuinely still emits formatVersion 1."
  falsification_test: >
    Import a formatVersion 1 payload whose gw_potential names a pk that DOES exist
    locally and which has no other out-of-range reference FK, into a fixture-built
    SQLite database. If that also fails with FOREIGN KEY constraint failed, the
    hypothesis is wrong and the cause is elsewhere in the insert path.
    (GUINEA PDACG (1).exactp is exactly such a file and is the live control.)
  fix_rationale: >
    Root cause, code half: an unverified write-through of a foreign identifier.
    The fix removes the write-through for REGISTERED reference models only:
    when no natural key is present, the integer is verified to name a local row
    before it is used, and a miss raises a named error that says which model,
    which field, which pk, and what to do. Unregistered targets (Activity, the
    cross-module OneToOne refs, user data) keep their existing path untouched,
    which is the same registry gate the natural-key design already uses.
    This cannot make a currently-working import fail: a pk that resolves today
    passes the existence check unchanged.
  blind_spots:
    - "The code fix converts an opaque failure into a precise one; it does NOT make an already-issued v1 file importable. The information needed to resolve pk 1 is simply not in the file. The actual unblock is deploying #274 so the online tool emits formatVersion 2."
    - "Not verified against production Postgres (no access from this sandbox). The claim `production GWP pk 1` rests on the exported files, which is direct evidence of what production contains, but the full production pk table is unknown."
    - "Whether the offline tool the user runs is built from THIS develop checkout is asserted by the user, not measured here. The 12:56 v2 export is consistent with it."
  candidate_causes:
    - "code: prepare_model_data writes unverified foreign reference PKs through when no `__nk` is present (views.py:1126,1132)"
    - "environment: origin/main (production) predates 87c8fec8, so the online exporter still emits formatVersion 1"
    - "data: committed fixtures and production genuinely disagree on reference PKs (GWP 8-12 vs 1..; FuelType lacks 51/52)"
  and_gate: >
    YES, three conditions must hold simultaneously. (1) payload is formatVersion 1,
    (2) the reference pk it names does not exist locally, (3) that FK is reached
    during import. Proof that it is a genuine AND rather than a single cause:
    GUINEA PDACG (1).exactp is formatVersion 1 and imports cleanly because
    condition (2) does not hold for it; the v2 file satisfies (2)-style divergence
    (gw_potential 11 vs a differently-seeded DB) yet imports because (1) does not
    hold. Offline -> offline works because (2) does not hold. Removing any one of
    the three removes the failure.
```

## Eliminated (continued)

- hypothesis: a reference model reachable from an exported payload was left out of `NATURAL_KEY_SPECS` (registry coverage gap)
  evidence: the introspection sweep reports `registered=True` for BOTH violating targets (`ipcc.globalwarmingpotential`, `api.fueltype`), and the v2 export of a comparable project carries `__nk` for every reference relation with zero unresolved values. The registry is not the gap.
  timestamp: 2026-08-14

- hypothesis: child rows are inserted before their parent (ordering / deferred-constraint difference between SQLite and PostgreSQL)
  evidence: the first and dominant violation is on `Project` itself, the very first INSERT of the import, before any child exists. Ordering is not involved.
  timestamp: 2026-08-14

- hypothesis: an FK is written through a bulk_create / raw insert path that bypasses `prepare_model_data`
  evidence: every insert in `import_project` goes through `prepare_model_data` (`views.py:1175`, `1209`, `1258`, and `_create_submodules` receives it as an argument). The deferred `cache_restores` replay uses `queryset.update()` but only writes the `CACHE_RESTORE_FIELDS` columns plus `status_id`, which is resolved separately and defensively.
  timestamp: 2026-08-14

## Eliminated

- hypothesis: offline DB is the stale committed `db.sqlite3` snapshot with mismatched reference PKs
  reason: user confirmed the offline DB was rebuilt from fixtures with the latest code

## Resolution

root_cause: |
  Three contributing causes, AND-gated. All three must hold for the failure to occur.

  1. **[environment]** The ONLINE production tool runs `origin/main` (`beb7fe10`, v1.20.3),
     which predates PR #274. `87c8fec8` is not an ancestor of `origin/main` or
     `origin/review`. Production therefore still hardcodes `"formatVersion": 1` at the
     export endpoint, so every `.exactp` it issues carries reference relations as raw
     integer primary keys with no `<field>__nk` natural key beside them. Verified
     directly: the three files exported 2026-08-14 12:51 UTC are formatVersion 1.

  2. **[data]** The committed reference fixtures and production genuinely disagree on
     primary keys. `ipcc.GlobalWarmingPotential` is pks 8-12 in the fixtures; the online
     payloads name pk 1. `api.FuelType` is pks 18-60 in the fixtures with 51 and 52
     absent; one payload names both. Commit 6190429f moved the offline tool off the
     shipped `db.sqlite3` snapshot (whose GWP pks 1-5 happened to AGREE with production)
     and onto a fixture-built database, which is what exposed this.

  3. **[code]** `prepare_model_data` wrote a foreign installation's private primary key
     straight into the local FK column whenever no natural key was present
     (`views.py:1126,1132`: `result[f"{field_name}_id"] = value if resolved is None else resolved`,
     where `reference_pk` returned None for any payload lacking `<field>__nk`).
     `Project.gw_potential` is NOT NULL with no default, so the very first statement of
     the import, `Project.objects.create()`, was rejected by SQLite's immediate foreign
     key enforcement. The driver reports only `FOREIGN KEY constraint failed`, naming
     neither table nor column, which is why the failure was unactionable.

  Cause 3 is the only one fixable in code here, and it is the one that made the bug
  undiagnosable. Cause 1 is what actually blocks the user and is a deployment action.
  Cause 2 is a data question requiring production access.

fix: |
  Removed the unverified write-through, for registered reference models only.

  - `api/natural_keys.py`: new `ReferenceResolutionError` base with
    `UnresolvableNaturalKeyError` (formatVersion 2, key present but unresolvable) and the
    new `LegacyReferenceIdError` (formatVersion 1, integer names no local row) beneath it.
    New `verify_legacy_reference_pk(model, field_name, pk, cache)` is the v1 counterpart of
    `resolve_natural_key`: it checks the integer names a local row and raises by name if
    not. It shares the per-request `nk_cache` under a `("verify", ...)` namespace, so a
    payload naming the same bad id on N modules costs one query, and memoises the miss.
  - `api/views.py`: `reference_pk()` now takes the value and is gated first on registry
    membership, so unregistered targets (`Activity`, the cross-module OneToOne refs, all
    user data) return None and keep their existing path byte for byte. With a key it
    resolves as before; without one it verifies. The handler catches the
    `ReferenceResolutionError` base, so both encodings return their own 400 message
    inside the existing `transaction.atomic`, leaving no partial project.

  What this does NOT do: make an already-issued formatVersion 1 file importable. A primary
  key is private to the database that issued it and v1 carries no other identity, so there
  is nothing to resolve it by. Any code that "fixed" that would be guessing at a mapping,
  which is the silent mis-resolution PR #274 exists to remove. The real unblock is
  deploying #274 so the online tool emits formatVersion 2.

verification: |
  Run on a SQLite database built the same way the offline tool builds its own:
  `manage.py migrate` (10m26s) + `load_reference_data --app=all` (162 fixtures), then
  `manage.py test --keepdb` with CI=true so the seeded database IS the test database.

  - **Signal 1, regression test fails before / passes after:** yes. See ablation below.
  - **Signal 2, not a deletion-only diff:** the fix adds a verifier and an error type;
    nothing was removed except the unverified write-through it replaces.
  - **Signal 3, the bug returns on revert:** yes, and it names the predicted column.
    Restoring the pre-fix `reference_pk` turns the 6 new view-level tests into
    4 failures + 4 errors, with Django's post-test `check_constraints()` reporting:
    `The row in table 'api_project' ... has an invalid foreign key:
     api_project.gw_potential_id contains a value '1013' that does not have a
     corresponding value in ipcc_globalwarmingpotential.id`
    and the same for `api_project.climate_id` = '1021'. That is the exact table and
    column the root-cause statement predicted, produced by the exact defect.
  - **Signal 4, adjacent tests still pass:** yes. Baseline (HEAD, changes stashed):
    63 tests, 1 failure + 21 errors. With the fix: 77 tests, 1 failure + 21 errors.
    `diff` of the sorted FAIL/ERROR name lists is EMPTY, so all 14 new tests pass and
    no existing test changed state in either direction.
  - **Signal 5, the mutation at the fix site is caught:** yes, that is Signal 3. The
    ablation is precisely the mutation "drop the existence check".

  **Why SQLite reported nothing useful, established during verification:** Django creates
  the FK as `"gw_potential_id" bigint NOT NULL REFERENCES "ipcc_globalwarmingpotential"
  ("id") DEFERRABLE INITIALLY DEFERRED`. With `PRAGMA foreign_keys=ON` and a DEFERRED
  constraint, SQLite does not check at INSERT: it checks at COMMIT. `import_project`
  commits at the end of its `transaction.atomic()` block, so the violation was raised
  after the entire project tree had been built, was caught by the blanket
  `except Exception`, and SQLite's commit-time deferred error carries no table or column,
  only the literal string `FOREIGN KEY constraint failed`. That is why the reported
  symptom had zero locality, and why moving the check to the point the bad value is READ
  is the whole value of the fix.

  **Pre-existing failures, confirmed unrelated (identical in baseline):**
  - 21 errors: `django.db.utils.ProgrammingError: Cannot operate on a closed database`
    in the test classes that do NOT apply `MIDDLEWARE_WITHOUT_CONNECTION_CLOSER`, plus
    two `ImportError: cannot import name 'GlobalWarmingPotential' from 'api.models'` at
    `test_project_export.py:185`. Both are defects in the test module, not the app.
  - 1 failure: `ProjectImportTests.test_import_creates_new_project` posts a project
    payload with no `gw_potential` at all, and `Project.gw_potential` is NOT NULL, so
    the create has always returned 400.

  **Harness note for whoever runs this next:** do not put a `TransactionTestCase` in a
  suite run with `CI=true --keepdb`. Its `_fixture_teardown` flushes every table and
  wipes the seeded reference data (this happened once during this session and cost a
  reload). `TestCase` rolls back and is safe.

oracle_type: specified (the API contract is an explicit 400 with a named message, not a
  crash; the negative assertion on "FOREIGN KEY constraint failed" pins the reported symptom
  itself rather than an implicit no-exception oracle)

deliberate_non_changes:
  - "`resolve_status_id` still DROPS an unknown module `status` for a v1 payload rather than
    raising, so the module falls back to EMPTY. That asymmetry with the new hard failure is
    pre-existing, documented at views.py:1146-1167 and covered by tests. `status` is
    bookkeeping and cannot change a number; a fuel type or a GWP report can. Changing it
    would regress the previous debug session's fix (import-project-loses-results)."
  - "A v2 payload whose exporting row had a NULL `name_en` emits `<field>__nk = [null]`,
    which `resolve_natural_key` rejects. Pre-existing, unchanged here, and only reachable
    for models the duplicate detector already flags (api.Unit, which no payload can carry)."
  - "A v1 integer that coincidentally names a DIFFERENT existing row still resolves silently
    to the wrong row. Unchanged: only a natural key can distinguish that case, which is
    exactly what formatVersion 2 is for."

files_changed:
  - djangoexact/api/natural_keys.py
  - djangoexact/api/views.py
  - djangoexact/api/tests/test_natural_keys.py
  - djangoexact/api/tests/test_project_export.py

## Remediation (what actually unblocks the user)

The code change in this session makes the failure diagnosable. It cannot make the user's
existing file import, because the identity needed to resolve `gw_potential = 1` is not in
the file. Three actions, in order of soundness:

1. **Deploy PR #274 to production (the unblock).** `87c8fec8` is only on `develop`.
   Production runs `main`. Until `main` carries it, every `.exactp` the online tool issues
   is formatVersion 1 and will keep failing against any offline build whose reference pks
   differ. Sequence: `develop` -> `review` -> `main`.
   **SUPERSEDED IN PART by the user's decision of 2026-08-14:** the target is `review`, not
   `main`, and the concrete steps (including a workflow-trigger blocker and the review-vs-
   production database question) are in "Deploy sequence (review path)" below. That section
   is authoritative; the gate described here is the same gate, stated less precisely.
   **Gate before deploying:** `.planning/quick/260813-fvj-.../260813-fvj-DUPLICATES.md`
   flags that migration `api/0290` and `ipcc/0065` were validated against the committed
   fixtures and the shipped offline snapshot only, never against production. A duplicate
   `name_en` in production Postgres would fail `0290` at deploy time. Run first:
   ```
   cloud-sql-proxy <INSTANCE_CONNECTION_NAME> &
   DB_ENGINE=django.db.backends.postgresql DB_HOST=127.0.0.1 DB_PORT=5432 \
   DB_NAME=<db> DB_USER=<user> DB_PASSWORD=<pw> \
     python manage.py check_reference_natural_keys
   ```
   After deploying, re-export the project from the online tool. The new file will be
   formatVersion 2 and will import.

2. **Rebuild the offline tool from `develop`** so it carries this session's change.
   Without it the offline tool keeps reporting the anonymous FK error for any file that
   still cannot be resolved.

3. **Optional, and a data decision, not a code one.** The committed fixtures disagree with
   production on reference pks (GWP 8-12 vs production's 1..; FuelType missing 51 and 52).
   Re-dumping the fixtures from production would make a fixture-built offline database
   agree with production pks, which would additionally let ALREADY-ISSUED formatVersion 1
   files import. It is the larger and riskier option: it renumbers reference pks in the
   fixture set, needs production access, and trips the `dump_reference_data` PK-stability
   guard by design. Natural keys are the architecturally correct answer and already exist;
   this is only worth doing if a large number of v1 files must be recoverable.

## Decisions (user, 2026-08-14)

1. **Unblock path: ship to `review`, then re-export.** NOT `main`. The user wants PR #274 on
   the `review` branch so the review environment's online tool exports formatVersion 2, and
   will re-export the project from there. `87c8fec8` is not an ancestor of `origin/review`
   either, so this means merging `develop` -> `review`.
2. **Commit directly on `develop`**, no feature branch, no PR. Done, see Resolution.
3. **The develop -> review merge and push were NOT performed by the agent.** They are
   outward-facing deploy actions the user authorised as a direction, not as an execution step.

## Deploy sequence (review path) - NOT YET EXECUTED

**Blocker 0, fix this first or nothing ships.** `.github/workflows/deploy.yaml` triggers on
`push` to `main` only; `review` is commented out at the top of the file. The `deploy` job's
`if:` already accepts `review`, so only the trigger needs changing:

```yaml
on:
  push:
    branches:
      - main
      - review        # <- uncomment
```

Without this, merging to `review` and pushing is a silent no-op: no build, no migrate, no
deploy, and the re-exported file would still be formatVersion 1.

**Gate 1, confirm the review database is NOT production's.** The repo cannot answer this.
`.env.review` and `.env.production` declare an identical `DB_NAME=exact` / `DB_USER=exact_user`,
and the value that actually deploys comes from the GitHub Actions environment-scoped variable
`vars.DB_INSTANCE_CONNECTION` (plus `vars.DB_NAME`), which is not in the repo. Check in GitHub:
Settings -> Environments -> `review` -> `DB_INSTANCE_CONNECTION`, and compare it against the
same variable under `production`.

- Different instance connection names -> separate databases, proceed.
- **Same instance connection name AND same `DB_NAME` -> review shares production's database.**
  In that case migrations `api/0290` and `ipcc/0065` add UNIQUE constraints to PRODUCTION data
  the moment the review deploy runs. That is a production schema change wearing a review label.
  Do not proceed on the review path; treat it as a production deploy with the corresponding
  care (backup, maintenance window, rollback plan).

**Gate 2, run the natural-key check against the REVIEW database before migrating.** This is not
in CI - `check_reference_natural_keys` appears nowhere in `.github/`, `bitbucket-pipelines.yml`
or `deploy/`, and the deploy step runs `manage.py migrate` unguarded. `260813-fvj-DUPLICATES.md`
records that `api/0290` and `ipcc/0065` were validated against the committed fixtures and the
shipped offline snapshot only, never against a live server database. A duplicate `name_en` there
fails the migration mid-deploy.

From `djangoexact/`, with the review instance's connection name:

```bash
cloud-sql-proxy <REVIEW_INSTANCE_CONNECTION_NAME> --port 5432 &

DB_ENGINE=django.db.backends.postgresql \
DB_HOST=127.0.0.1 DB_PORT=5432 \
DB_NAME=<review DB_NAME> DB_USER=<review DB_USER> DB_PASSWORD=<review DB_PASSWORD> \
  python manage.py check_reference_natural_keys
```

Read the result by EXIT CODE, not by eyeballing the text (`handle()` calls `sys.exit(1)` iff
`findings` is non-empty):

- **exit 0** + `No duplicate or empty natural keys across N registered model(s).` -> GO.
- **exit 1** -> NO-GO. Every finding is either `kind: duplicate` (two or more rows share a
  natural key, listed with their pks) or `kind: empty_key` (rows whose whole key is
  null/blank). Both would be rejected by the UNIQUE constraints in `api/0290` and
  `ipcc/0065`, so the migration fails partway through the deploy. Resolve the named rows
  first. Add `--json` for a machine-readable list of exactly which model, fields and pks.

**Then:**

```bash
git checkout review && git pull
git merge develop
git push origin review          # only meaningful after Blocker 0 is fixed
```

Watch the Deploy workflow. It runs `check --deploy`, then `migrate` (this is where `0290` /
`0065` land), then `collectstatic` and `gcloud app deploy`.

**Finally:** re-export the project from the REVIEW online tool. The new file must begin
`"formatVersion": 2` and carry `gw_potential__nk`. Import that into the offline tool. Verify
the exported file is v2 before concluding anything about the import - a v1 file proves only
that the deploy did not take.

## Adjacent findings (not this bug, recorded for later)

- `TransportEntry.fuel_type_start/_w/_wo` pointing at `api.FuelType` pks 51 and 52 is the
  same defect firing later in the same import, visible in `test 2807 (1).exactp`. It is
  covered by the same fix.
- `api.Unit` is registered but deliberately unconstrained (66 duplicate, 100 blank-named
  rows in the shipped snapshot). It is unreachable from any payload today. If a future
  change makes it reachable, `_lookup_pk` will resolve ambiguously to the lowest pk.
- A v2 payload whose exporting row has a NULL `name_en` emits `<field>__nk = [null]`, which
  `resolve_natural_key` rejects as an empty key. Pre-existing and currently unreachable,
  but it would present as an unexplained import failure if it ever became reachable.
