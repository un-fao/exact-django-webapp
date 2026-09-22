---
quick_id: 260813-fvj
type: execute
wave: 1
depends_on: []
autonomous: false
requirements: [D1, D2, D3]
branch: fix/export-import-reference-data-identity
files_modified:
  - djangoexact/djangoexact/settings.py
  - djangoexact/api/management/commands/verify_reference_parity.py
  - djangoexact/api/reference_parity.py
  - djangoexact/scripts/build_offline_db.sh
  - djangoexact/docs/guides/offline-db-bootstrap.md
  - djangoexact/api/tests/test_reference_parity.py
  - djangoexact/api/natural_keys.py
  - djangoexact/api/management/commands/check_reference_natural_keys.py
  - djangoexact/api/models.py
  - djangoexact/ipcc/models.py
  - djangoexact/api/migrations/0290_reference_natural_key_constraints.py
  - djangoexact/ipcc/migrations/0065_gwp_natural_key_constraint.py
  - djangoexact/api/tests/test_natural_keys.py
  - djangoexact/api/serializers.py
  - djangoexact/api/views.py
  - djangoexact/api/tests/test_project_export.py

estimate:
  tokens: 220000
  raw_tokens: 110000
  tasks: 3
  confidence: low

must_haves:
  truths:
    - "A fresh offline database can be built from `migrate` + `load_reference_data --app=all` against sqlite, with no committed binary DB involved (D1)."
    - "`verify_reference_parity` exits non-zero when any reference PK in the database maps to a different row than the committed fixture assigns to that PK (D1)."
    - "Every reference model reachable as a Project/Activity/Module FK has a declared natural key and a database-level uniqueness guarantee behind it (D2)."
    - "Duplicate natural keys are detected and reported BEFORE any UniqueConstraint is added, and duplicates halt the task rather than being silently deduped (D2, research A3)."
    - "New exports carry `formatVersion: 2` with both the legacy integer PK and a `<field>__nk` natural key for every registered reference FK (D3)."
    - "An import of a v2 file resolves reference FKs by natural key even when the encoded integer PK points at a different row in the target database (D3, the actual bug)."
    - "An unresolvable natural key aborts the import with a named actionable error and creates no Project, instead of silently mis-resolving (D3)."
    - "`formatVersion: 1` files still import by integer PK exactly as they do today (hard constraint: backward compatibility)."
    - "`compatibilityGroup` stays 1 in version.config.json and in the emitted envelope (hard constraint)."
  artifacts:
    - djangoexact/api/reference_parity.py
    - djangoexact/api/management/commands/verify_reference_parity.py
    - djangoexact/scripts/build_offline_db.sh
    - djangoexact/docs/guides/offline-db-bootstrap.md
    - djangoexact/api/natural_keys.py
    - djangoexact/api/management/commands/check_reference_natural_keys.py
    - djangoexact/api/migrations/0290_reference_natural_key_constraints.py
    - djangoexact/ipcc/migrations/0065_gwp_natural_key_constraint.py
    - djangoexact/api/tests/test_reference_parity.py
    - djangoexact/api/tests/test_natural_keys.py
  key_links:
    - "settings.py DATABASES OPTIONS (settings.py:190-193) currently passes `connect_timeout` and `application_name` unconditionally, which makes any sqlite bootstrap crash with TypeError before task 1 fixes it. VERIFIED this session."
    - "api/natural_keys.py is the single source of truth shared by the duplicate detector (task 2), the export encoder (task 3, serializers.py:684-687 and serializers.py:739-745) and the import resolver (task 3, views.py:1094-1099)."
    - "ModuleExportSerializer.to_representation walks `instance._meta.get_fields()` (serializers.py:668-673), so encoding natural keys inside that same loop covers every MTI subclass with no per-model registration (research pitfall 4)."
    - "`_extract_cache_restore` (views.py:199-224) pops `status` before prepare_model_data runs, so it must also pop `status__nk` or the module StatusType FK stays on the broken integer path."
    - "Natural keys resolve BEFORE any objects.create(), so the error names the module and key rather than a sqlite deferred-FK table name (research pitfall 6)."
    - "Natural keys are pinned to `name_en`, never the translated `name` descriptor, because `instance.name` resolves through the active language (research pitfall 2)."
---

<objective>
Fix the reference-data ID mismatch that breaks `.exactproject` import between the online tool and the offline tool, by removing the cause and hardening the format against recurrence.

The `.exactproject` format encodes every reference FK as a raw integer PK and the importer resolves nothing. That is only safe while both installations share reference PKs. They do not: the offline build ships a pre-seeded `db.sqlite3` instead of loading the committed fixtures, and 83 of 162 manifest reference models have drifted. `ipcc.GlobalWarmingPotential` PK ranges are fully disjoint (fixtures 8-12, offline DB 1-5) and `Project.gw_potential` is NOT NULL, so every online-to-offline import fails at the first row. Where PKs happen to collide the failure is worse: the project imports and silently displays the wrong climate, soil, GWP or module type.

Purpose: emission appraisals must round-trip between installations without silently changing their inputs.

Output: (1) a fixture-based offline bootstrap plus a parity verifier and a handoff checklist, (2) declared natural keys backed by database uniqueness on every reference model reachable as a Project/Activity/Module FK, (3) `formatVersion: 2` dual encoding with resolve-by-natural-key on import and a named hard failure when a key cannot be resolved.
</objective>

<context>
@.planning/quick/260813-fvj-when-import-exporting-from-online-tool-t/260813-fvj-RESEARCH.md
@CLAUDE.md
@.claude/CLAUDE.md
@djangoexact/docs/guides/fixtures-guide.md
</context>

<environment>
All commands run from the Django root: `/home/sirvosterzo/Developer/FAO/EXACT/exact-django-webapp/djangoexact`.

Virtualenv: `/home/sirvosterzo/Developer/FAO/EXACT/exact-django-webapp/.venv`. Use `../.venv/bin/python`.

Local database reality, verified this session:

- There is no Postgres and no Docker. Nothing in this plan may require them.
- `DJANGO_DEBUG=True ../.venv/bin/python manage.py makemigrations --check --dry-run` runs with no database at all.
- A sqlite database is reachable via `DB_ENGINE=django.db.backends.sqlite3 DB_NAME=<path>`, but ONLY after task 1 lands. Before task 1 it dies immediately with `TypeError: 'connect_timeout' is an invalid keyword argument for Connection()` raised from `django/db/backends/sqlite3/base.py:206`, because `settings.py` passes the Postgres-only `OPTIONS` block unconditionally. VERIFIED by running it.
- A full `manage.py migrate` against a fresh sqlite file is SLOW. It ran past migration `api.0192` in 10 minutes and did not finish; budget 20 to 40 minutes and run it with `run_in_background: true`. The cost is the ~290 migrations plus simple_history table rebuilds, not a defect.
- Because of that cost, build the scratch sqlite ONCE in task 1 and reuse it for tasks 2 and 3 via `--keepdb`.

Scratch paths (use the session scratchpad, never the repo):

```bash
export SP=/tmp/claude-1000/-home-sirvosterzo-Developer-FAO-EXACT-exact-django-webapp-djangoexact/692e71df-18c3-4acf-8655-09efe29cf1de/scratchpad
export SQLITE_ENV="DJANGO_DEBUG=True DB_ENGINE=django.db.backends.sqlite3"
export REF_DB=$SP/refdata.sqlite3      # fixture-seeded, built in task 1
export TEST_DB=$SP/testrun.sqlite3     # copy of REF_DB, used by --keepdb test runs
```

Reusing the seeded DB for tests (settings.py:198-203 only sets `TEST.NAME` when `CI=true`):

```bash
cp $REF_DB $TEST_DB   # never run tests against the artifact you intend to keep
CI=true DJANGO_DEBUG=True DB_ENGINE=django.db.backends.sqlite3 DB_NAME=$TEST_DB \
  ../.venv/bin/python manage.py test api.tests.<module> --keepdb
```

The shipped offline database is obtainable without switching branches:

```bash
git show release/offline-tool:djangoexact/db.sqlite3 > $SP/offline.sqlite3
```

Branch: stay on `fix/export-import-reference-data-identity` for the entire plan. Never check out `release/offline-tool`.

Do not stage `.planning/STATE.md` or `djangoexact/scripts/ipcc_dump.py`. Both were already modified before this task began and belong to unrelated work.
</environment>

<hard_constraints>
- `compatibilityGroup` stays 1 everywhere. It hard-rejects at `api/serializers.py:757-767`; bumping it invalidates every `.exactproject` already issued. Only `formatVersion` goes to 2.
- `formatVersion: 1` files must keep importing by integer PK. New exports carry both encodings.
- Public API contract unchanged. The only additions are optional keys inside the export body.
- Do not touch `math_model/` or `api/calculators.py`. Calculation results must not change.
- Cached results are restored as-is on import by binding product decision (`.planning/debug/resolved/import-project-loses-results.md`). Fix the inputs, not the cache policy.
- Never key on the translated `name` descriptor. Key on `name_en`. modeltranslation copies the wrapped field's `__dict__` onto every language column, so `unique=True` propagates to `name_es`/`name_fr`/`name_ru` and would fail the migration on a shared translation. Use explicit `Meta.constraints = [UniqueConstraint(fields=["name_en"], ...)]`.
- No `pytest-django`. Anything touching the ORM subclasses Django `TestCase` / `APITestCase`.
- Never use em-dashes anywhere.
- Conventional commits, one atomic commit per task.
</hard_constraints>

<tasks>

<task type="tracer">
  <name>Task 1: Build the offline reference database from fixtures, provably</name>
  <files>
djangoexact/djangoexact/settings.py
djangoexact/api/reference_parity.py
djangoexact/api/management/commands/verify_reference_parity.py
djangoexact/scripts/build_offline_db.sh
djangoexact/docs/guides/offline-db-bootstrap.md
djangoexact/api/tests/test_reference_parity.py
  </files>

  <read_first>
djangoexact/djangoexact/settings.py:160-205 (the two DATABASES branches; the `$DB_*` strings are sed placeholders substituted in CI, do not reword those lines)
djangoexact/api/fixtures_manifest.py (MANIFEST, `ReferenceModelSpec`, `filter_manifest`)
djangoexact/api/management/commands/load_reference_data.py:1-60 (argument surface and `_fixture_path`)
djangoexact/docs/guides/fixtures-guide.md
  </read_first>

  <action>
Make a fixture-seeded offline database buildable and verifiable. This is the vertical slice: it touches settings, a new pure-logic module, a management command, a shell entry point, a doc and a test, and ends with a real database built end to end.

**1a. Unblock sqlite in settings.py.** In the non-GAE `DATABASES` branch (settings.py:182-197), the `OPTIONS` dict carries `connect_timeout` and `application_name`, which are psycopg-only. `sqlite3.connect()` rejects `connect_timeout` with a TypeError before a single migration runs. Build the `OPTIONS` value conditionally on the resolved engine: keep the existing dict verbatim when the engine string contains `postgresql`, otherwise use `{}`. Do the same in the GAE branch only if the engine there is also parameterized; if it is a hard `$DB_ENGINE` placeholder, leave the GAE branch alone and note why in a comment. Do not alter the `$DB_ENGINE`, `$DB_HOST`, `$DB_USERNAME`, `$DB_PASSWORD`, `$DB_NAME`, `$DB_PORT` placeholder strings or the `CI=true` TEST block; both are consumed by CI `sed` templating and by the Phase 1 production config guard.

**1b. `api/reference_parity.py` (new, pure logic, no Django imports beyond typing).** Expose:
- `IdentityDiff` dataclass or NamedTuple with `model`, `changed`, `missing_in_db`, `extra_in_db`, where `changed` is a list of `(pk, fixture_identity, db_identity)`.
- `diff_reference_identity(fixture_rows, db_rows) -> IdentityDiff`. Both inputs are `dict[int, tuple]` mapping pk to an identity tuple. `changed` is the semantic-drift case (pk present on both sides, identities differ) and is the only fatal category. `missing_in_db` and `extra_in_db` are warnings, mirroring the existing dump guardrail semantics in fixtures-guide.md ("Adding new rows is always allowed; removing rows prints a warning but does not fail").
Keeping this function free of Django lets it be tested with `SimpleTestCase`, which needs no database.

**1c. `api/management/commands/verify_reference_parity.py` (new).** Mirror the argument surface of `load_reference_data`: `--app` (api|ipcc|all, default all), `--models`, and add `--json` for machine-readable output. For each manifest spec:
- read the committed fixture JSON at the same path `load_reference_data` resolves,
- build `fixture_rows` as `{pk: tuple(fields[f] for f in spec.order_by)}`,
- build `db_rows` with a single `model.objects.values_list("pk", *spec.order_by)` query,
- call `diff_reference_identity`.
Print a per-model summary. Exit code 1 if any model reports `changed`, 0 otherwise, with warnings printed for the other two categories. Use `spec.order_by` as the identity, NOT a natural key: this command must stand alone before task 2 exists, and `order_by` is already required to be a deterministic per-model identity by the manifest contract. Handle `order_by` entries ending in `_id` (for example `api.Definition` uses `("module_type_id", "id")`) by reading the fixture's raw field value, which is already the integer PK.

**1d. `scripts/build_offline_db.sh` (new, executable).** A shell entry point, deliberately not a django-extensions runscript, because it must sequence three separate `manage.py` invocations against a database that does not exist yet. It takes an output path argument, refuses to run if that file already exists (the whole point is that a stale database can never be reused), exports `DB_ENGINE=django.db.backends.sqlite3` and `DB_NAME=$OUT`, then runs `migrate --noinput`, `load_reference_data --app=all`, and `verify_reference_parity --app=all`, with `set -euo pipefail` so any failure aborts. Echo the elapsed time and a warning that the migrate step takes tens of minutes.

**1e. `docs/guides/offline-db-bootstrap.md` (new).** Two parts.

Part one, what this branch delivers: how to build a reference database from fixtures, what `verify_reference_parity` proves, and the measured cost.

Part two, the handoff checklist for `release/offline-tool`, written as an explicit ordered list for a human to execute on that branch, NOT performed here:
1. Run `verify_reference_parity` against the shipped `db.sqlite3` and record the drift, so the change is justified with numbers rather than assertion.
2. `git rm --cached djangoexact/db.sqlite3`, add it to `.gitignore`, and note that history rewriting to reclaim the 53 MB is a separate decision.
3. Generate the database at package time with `scripts/build_offline_db.sh`, from the same commit as the online deployment.
4. Gate the packaging step on `verify_reference_parity` exiting 0.
5. Confirm the offline `.env` sets `DB_ENGINE=django.db.backends.sqlite3`, which only works once 1a has been merged down into that branch.

Then a section headed `Unconfirmed` recording, verbatim, what could not be established from this repo: `settings_offline.py` is byte-identical to develop's `settings.py` on the database question and only strips apps, middleware and URL routes; no `.env` file is committed on `release/offline-tool`; and no packaging script, Dockerfile or installer spec exists in the repo that consumes `db.sqlite3`. State plainly that the packaging step lives outside this Django root, that steps 3 to 5 must be confirmed with whoever owns it, and that this document is the request for that confirmation. Do not guess the mechanism.

**1f. `api/tests/test_reference_parity.py` (new).** `SimpleTestCase` only, so it runs with no database. Cover `diff_reference_identity`: identical inputs produce an empty diff; a pk whose identity changed lands in `changed`; a pk only in fixtures lands in `missing_in_db`; a pk only in the database lands in `extra_in_db`; and a pk that is present on both sides with equal identity appears in none of the three.
  </action>

  <verify>
    <automated>
cd /home/sirvosterzo/Developer/FAO/EXACT/exact-django-webapp/djangoexact
../.venv/bin/python -m py_compile djangoexact/settings.py api/reference_parity.py api/management/commands/verify_reference_parity.py api/tests/test_reference_parity.py
bash -n scripts/build_offline_db.sh
test -x scripts/build_offline_db.sh
# DB-free unit gate on the diff logic
DJANGO_DEBUG=True ../.venv/bin/python manage.py test api.tests.test_reference_parity
# The settings fix, proven directly: opening a sqlite connection must no longer raise
DJANGO_DEBUG=True DB_ENGINE=django.db.backends.sqlite3 DB_NAME=$SP/conn_probe.sqlite3 \
  ../.venv/bin/python manage.py shell -c "from django.db import connection; connection.ensure_connection(); print('sqlite-connect-ok')"
# Postgres OPTIONS must be preserved, not dropped for everyone
DJANGO_DEBUG=True DB_ENGINE=django.db.backends.postgresql ../.venv/bin/python -c "
import django, os; os.environ.setdefault('DJANGO_SETTINGS_MODULE','djangoexact.settings'); django.setup()
from django.conf import settings; o = settings.DATABASES['default']['OPTIONS']
assert o.get('connect_timeout') == 30 and o.get('application_name') == 'djangoexact', o
print('postgres-options-preserved')"
    </automated>
    <automated>
# End-to-end bootstrap. SLOW (20-40 min); run with run_in_background: true and poll.
cd /home/sirvosterzo/Developer/FAO/EXACT/exact-django-webapp/djangoexact
bash scripts/build_offline_db.sh $SP/refdata.sqlite3
# must print the verify_reference_parity summary and exit 0
    </automated>
  </verify>

  <done>
`manage.py shell` opens a sqlite connection without a TypeError, and the Postgres `OPTIONS` are provably still applied when the engine is postgresql. `scripts/build_offline_db.sh $SP/refdata.sqlite3` produces a database built purely from `migrate` + `load_reference_data --app=all` and `verify_reference_parity --app=all` exits 0 against it. `test_reference_parity` passes with no database. `docs/guides/offline-db-bootstrap.md` contains the ordered `release/offline-tool` checklist and an `Unconfirmed` section naming the packaging step as the open dependency. No branch was switched. Committed as `feat(offline): build the offline reference database from fixtures instead of a committed sqlite snapshot`.
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Declare natural keys and enforce uniqueness behind them</name>
  <files>
djangoexact/api/natural_keys.py
djangoexact/api/management/commands/check_reference_natural_keys.py
djangoexact/api/models.py
djangoexact/ipcc/models.py
djangoexact/api/migrations/0290_reference_natural_key_constraints.py
djangoexact/ipcc/migrations/0065_gwp_natural_key_constraint.py
djangoexact/api/tests/test_natural_keys.py
  </files>

  <read_first>
.planning/quick/260813-fvj-when-import-exporting-from-online-tool-t/260813-fvj-RESEARCH.md, the "Natural-key candidates" table and pitfalls 1, 2 and 3
djangoexact/api/models.py:213-610 (the reference model block) plus 2690-2745, 2850-2856, 3356-3372
djangoexact/api/translation.py (which models are registered, hence which have a `name_en` column)
djangoexact/ipcc/models.py:1-20 (GlobalWarmingPotential)
  </read_first>

  <behavior>
The duplicate detector, before any schema change:
- Reports zero duplicates on a fixture-seeded database, which is the precondition for the migration.
- Reports the model, the offending key value and every colliding pk when duplicates exist.
- Exits 1 when any duplicate is found.

The registry:
- `natural_key_for(Climate_instance)` returns `("Tropical",)` when `name_en == "Tropical"`, regardless of the active language.
- `natural_key_for(instance_of_unregistered_model)` returns `None`.
- `resolve_natural_key(Climate, ("Tropical",))` returns the local pk.
- `resolve_natural_key(Climate, ("Nonexistent",))` raises `UnresolvableNaturalKeyError`.
- `resolve_natural_key(Country, ("Turkey",))` resolves to the row named `Türkiye` through the alias table.
- `resolve_natural_key(FuelType, (name_en, fuel_use_type_name, macro_fuel_type_name))` resolves the composite.
  </behavior>

  <action>
Sequence matters inside this task: detection runs and must come back clean BEFORE the constraints are written.

**2a. `api/natural_keys.py` (new). Registry first, no model changes yet.**

```
NaturalKeySpec(fields=(...), label="...")
NATURAL_KEY_SPECS: dict[str, NaturalKeySpec]   # keyed "app_label.ModelName"
class UnresolvableNaturalKeyError(Exception)
def spec_for(model) -> NaturalKeySpec | None
def natural_key_for_pk(model, pk, cache=None) -> tuple | None
def natural_key_for(instance) -> tuple | None
def resolve_natural_key(model, key, cache=None) -> int          # raises UnresolvableNaturalKeyError
```

`fields` holds ORM lookup paths, so a single `model.objects.filter(pk=pk).values_list(*spec.fields).first()` both encodes and, inverted through `filter(**dict(zip(spec.fields, key)))`, decodes. That handles direct columns and FK traversals uniformly and costs one query, cacheable on `(label, pk)`. Accept an optional caller-supplied dict cache rather than `lru_cache`, so an import request cannot be served stale reference data; note the contrast with `module_type_for_class` (models.py:458-467), which is deliberately process-cached because it is read-only at runtime.

Registry membership is the gate for everything downstream: a FK whose target model is absent from `NATURAL_KEY_SPECS` gets no natural key on export and no resolution on import. That is what keeps `Activity.owner`, `Module.activity` and the OneToOne cross-module module refs on their existing paths.

Populate it from the research audit table. Key on `name_en` for every model registered in `api/translation.py` or `ipcc/translation.py`, and on `name` for the untranslated ones:

- `name_en`, already uniquely constrained because `unique=True` on the translated `name` propagates to `name_en` (research pitfall 1, VERIFIED on the shipped schema), so these need NO new constraint: `api.StatusType`, `api.TillageManagementType`, `api.OrganicInputType`, `api.ModuleType`, `api.LargeFisheryGearType`, `api.SmallFisheryGearType`, `api.PackagingMaterialType`, `api.InputType`, `api.MacroInputType`, `api.IrrigationSystemType`.
- `name`, untranslated and already `unique=True`, no new constraint: `api.Country`, `api.RefrigerantType`, `api.EmissionFactorSource`.
- `name_en`, translated and NOT unique today, so these DO need a new constraint: `api.LandUseType`, `api.SettlementType`, `api.SoilType`, `api.ResidueManagementType`, `api.OrganicAmendmentType`, `api.WaterManagementTypeBeforeCultivation`, `api.WaterManagementTypeAfterCultivation`, `api.GrasslandManagementType`, `api.LivestockProductionType`, `api.ManureManagementType`, `api.FireType`, `api.TrophicType`, `api.Climate`, `api.Moisture`, `api.ForestType`, `ipcc.GlobalWarmingPotential`.
- `name`, untranslated and NOT unique today, new constraint needed: `api.Unit`, `api.ProjectStatus`.
- Composite: `api.FuelType`, fields `("name_en", "fuel_use_type__name_en", "macro_fuel_type__name_en")`. The existing `unique_together = ("name", "fuel_use_type", "macro_fuel_type")` (models.py:598-599) constrains the base `name` column, not `name_en`, so add a matching `UniqueConstraint(fields=["name_en", "fuel_use_type", "macro_fuel_type"])`. `macro_fuel_type` is nullable, so pass `nulls_distinct=False` (Django 5.0+); it is honoured on Postgres 15+ and ignored on sqlite. Record that asymmetry in a comment.

`ipcc.GlobalWarmingPotential` is the highest priority entry in the registry. Its PK ranges are fully disjoint between installations (fixtures 8-12, offline DB 1-5, VERIFIED) and `Project.gw_potential` is NOT NULL (models.py:694), so it is what makes every import fail at row one. It must be present and correct.

`api.Country` gets an explicit rename escape hatch, because a name-based natural key breaks on renames exactly as PKs break on renumbering, and `Country` has no stable code column (it carries only `name`, `region`, `ipcc_region`, `gleam_region`; the `code` field at models.py:673 belongs to `Project`). Adding an ISO column is a data-migration project and is out of scope here. Instead:
- key `Country` on `name`,
- add `COUNTRY_NAME_ALIASES: dict[str, str]` mapping a historical name to the current one, seeded with the three renames the research documented: `"Turkey" -> "Türkiye"`, `"Bolivia" -> "Bolivia (Plurinational State of)"`, `"China, Hong Kong Special Administrative Region" -> "China, Hong Kong SAR"`,
- have `resolve_natural_key` try the literal name first and the alias second,
- document in the module docstring that an unaliased rename surfaces as a named import failure rather than a wrong country, that this is the intended trade, and that a future ISO-code column would retire the alias table.

**2b. `api/management/commands/check_reference_natural_keys.py` (new).** Iterate `NATURAL_KEY_SPECS`, and for each model run `values_list(*spec.fields)` annotated or grouped to find keys occurring more than once, plus a separate count of rows where any key component is NULL or empty (an unpopulated `name_en` silently breaks resolution just as badly as a duplicate). Print model, key value and the colliding pks. Exit 1 when anything is reported. Support `--json`.

**2c. Run the detector. This is a gate, not a formality.**
Run it against the fixture-seeded `$REF_DB` from task 1, and again against the shipped offline database `$SP/offline.sqlite3` as a second independent dataset.

If ANY duplicate or NULL key component is reported: STOP. Do not add the constraint for that model. Do not dedupe, rename, merge or delete reference rows. Write the full detector output to `.planning/quick/260813-fvj-when-import-exporting-from-online-tool-t/260813-fvj-DUPLICATES.md` and report to the user with the model, the key values and the pks, then wait. Reference data is database-truth (fixtures-guide.md) and deduping it silently changes what existing projects point at. Research assumption A3 flags precisely this: `LandUseType` name uniqueness is proven for the 211 committed fixture rows only, never against production, and production Postgres is unreachable from here. A clean local run is necessary evidence, not sufficient evidence, so the doc from task 1 should also carry a line telling the release owner to run this command against production via cloud-sql-proxy before the migration ships.

**2d. Only if 2c is clean: add the constraints.** Add `Meta.constraints = [UniqueConstraint(fields=[...], name="uniq_<model_snake>_<field>")]` to the 19 models listed above, in `api/models.py` and `ipcc/models.py`. Several of these models have no `Meta` at all today, so add one; several have a `Meta` carrying only `verbose_name_plural`, so extend rather than replace it. Never use `unique=True` on a translated field, for the propagation reason above.

**2e. Generate the migrations** with `makemigrations api ipcc`. Let Django name them and record the real numbers; `0290` and `0065` are the expected next values but confirm. Do not hand-write the operations. Read the generated files and confirm they contain only `AddConstraint` operations and no unexpected field alterations.

**2f. `api/tests/test_natural_keys.py` (new).** Django `TestCase`. Cover the `<behavior>` list. For the language-independence case, wrap the `natural_key_for` assertion in `django.utils.translation.override("fr")` with a French `name_fr` set on the row, and assert the key is still the English value. Include a registry-integrity test that every entry in `NATURAL_KEY_SPECS` names a resolvable model and that every field path in `spec.fields` resolves against that model, so a typo in the registry fails loudly instead of at import time in production.
  </action>

  <verify>
    <automated>
cd /home/sirvosterzo/Developer/FAO/EXACT/exact-django-webapp/djangoexact
../.venv/bin/python -m py_compile api/natural_keys.py api/management/commands/check_reference_natural_keys.py api/models.py ipcc/models.py api/tests/test_natural_keys.py
# no model change left unmigrated
DJANGO_DEBUG=True ../.venv/bin/python manage.py makemigrations --check --dry-run
# the gate: must exit 0 on both datasets BEFORE the constraints were added
DJANGO_DEBUG=True DB_ENGINE=django.db.backends.sqlite3 DB_NAME=$REF_DB \
  ../.venv/bin/python manage.py check_reference_natural_keys
DJANGO_DEBUG=True DB_ENGINE=django.db.backends.sqlite3 DB_NAME=$SP/offline.sqlite3 \
  ../.venv/bin/python manage.py check_reference_natural_keys
    </automated>
    <automated>
# constraints must actually apply to real fixture data, not just to an empty schema
cd /home/sirvosterzo/Developer/FAO/EXACT/exact-django-webapp/djangoexact
cp $REF_DB $TEST_DB
DJANGO_DEBUG=True DB_ENGINE=django.db.backends.sqlite3 DB_NAME=$TEST_DB \
  ../.venv/bin/python manage.py migrate --noinput
CI=true DJANGO_DEBUG=True DB_ENGINE=django.db.backends.sqlite3 DB_NAME=$TEST_DB \
  ../.venv/bin/python manage.py test api.tests.test_natural_keys --keepdb
    </automated>
  </verify>

  <done>
`check_reference_natural_keys` exits 0 against both the fixture-seeded database and the shipped offline database, and that run happened before the constraints existed. Every reference model reachable as a Project/Activity/Module FK has an entry in `NATURAL_KEY_SPECS`, including `ipcc.GlobalWarmingPotential`, the `api.FuelType` composite and `api.Country` with its alias table. The 19 new `UniqueConstraint`s apply cleanly to a database holding real fixture data. `makemigrations --check --dry-run` is clean. `test_natural_keys` passes, including the `override("fr")` language-independence case and the registry-integrity check. If duplicates had been found the task halted and reported instead of deduping. Committed as `feat(api): declare reference-data natural keys and enforce uniqueness behind them`.
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 3: formatVersion 2 dual encoding with resolve-by-natural-key on import</name>
  <files>
djangoexact/api/serializers.py
djangoexact/api/views.py
djangoexact/api/tests/test_project_export.py
  </files>

  <read_first>
djangoexact/api/serializers.py:649-707 (ModuleExportSerializer.to_representation)
djangoexact/api/serializers.py:730-775 (ProjectExportSerializer.to_representation, ProjectImportSerializer)
djangoexact/api/views.py:160-224 (CACHE_RESTORE_FIELDS, _extract_cache_restore)
djangoexact/api/views.py:892-927 (export action) and 939-1249 (import_project)
djangoexact/api/tests/test_project_export.py
djangoexact/api/natural_keys.py (written in task 2)
  </read_first>

  <behavior>
Export:
- The envelope carries `formatVersion: 2` and `compatibilityGroup: 1`.
- A project with reference FKs emits both `climate: <pk>` and `climate__nk: ["Tropical"]`, and likewise for `country`, `moisture`, `soil_type`, `gw_potential` and `status`.
- A module emits `<field>__nk` beside the integer for every FK whose target model is in the registry, and nothing extra for FKs whose target is not.
- `Activity.module_types` emits both the bare pk list and `module_types__nk` as a list of keys.

Import:
- A v2 body whose `gw_potential` integer points at a nonexistent pk but whose `gw_potential__nk` names an existing row imports successfully and the created Project points at the row named by the key. This is the actual bug.
- A v2 body whose `gw_potential` integer points at a DIFFERENT existing row than the key names resolves to the row the key names, not the integer.
- A v2 body carrying an unresolvable `__nk` returns 400 with the named error, and no Project row is created.
- A v1 body with no `__nk` keys imports by integer pk exactly as today.
- A v2 body from which a `__nk` key is simply absent for one field falls back to the integer for that field only.
  </behavior>

  <action>
**3a. Export, `ModuleExportSerializer.to_representation` (serializers.py:683-687).** In the existing `ForeignKey`/`OneToOneField` branch, after storing the integer, look up `spec_for(field.related_model)`. When a spec exists, also set `data[f"{field.name}__nk"] = list(natural_key_for_pk(field.related_model, value, cache))`, skipping when the lookup returns `None`. Keep this inside the `_meta.get_fields()` loop, which is what makes it cover every MTI subclass with no per-model registration (research pitfall 4). Hold the `(label, pk) -> key` cache on the serializer instance so an export of many modules pays one query per distinct reference row rather than one per module. `ActivityExportSerializer.get_modules` (serializers.py:718-727) already reuses a single `ModuleExportSerializer`, so the cache spans the whole activity.

The `__` separator cannot collide with a real field name, since Django reserves it as the lookup separator, and `prepare_model_data` iterates model fields rather than payload keys, so unknown `__nk` keys are inert on the v1 path.

**3b. Export, `ProjectExportSerializer.to_representation` (serializers.py:739-745).** The loop already flattens `country, climate, moisture, soil_type, gw_potential, status` from nested dicts down to their `id`. Extend it to also emit `<field>__nk` from the same resolved pk. Note that `status` here is `api.ProjectStatus`, while `status` on a module is `api.StatusType`; both are in the registry and both resolve through their own model, so no special-casing is needed as long as the model comes from the field, never from the field name.

**3c. Export, `Activity.module_types` M2M.** `ActivityExportSerializer` inherits `Meta.exclude`, so `module_types` is serialized as a bare pk list. Add a `SerializerMethodField` or a `to_representation` override emitting `module_types__nk` as a list of natural keys alongside the existing list. Do not change the existing key's name or shape.

**3d. Export, envelope (views.py:912).** `"formatVersion": 2`. Leave `compatibilityGroup` reading from `version.config.json` untouched.

**3e. Import, `ProjectImportSerializer.validate_formatVersion` (serializers.py:769-775).** Accept `1` and `2`. Keep the rejection message shape for anything else. Do not touch `validate_compatibilityGroup`.

**3f. Import, `prepare_model_data` (views.py:1042-1102).** This is the fix. In the `ForeignKey` branch at views.py:1097-1099, before falling through to the integer:
- read `data.get(f"{field_name}__nk")`,
- if present and the target model has a spec, set `result[f"{field_name}_id"] = resolve_natural_key(field.related_model, tuple(nk), nk_cache)` and let `UnresolvableNaturalKeyError` propagate,
- if absent, keep the existing integer behavior verbatim.
Never fall back to the integer when a natural key is present but unresolvable. That fallback is the silent mis-resolution this whole task exists to remove. Apply the same treatment in the `OneToOneField` branch, but only in its final `elif isinstance(value, int)` arm at views.py:1091-1094, the one commented as the reference-data case; the `module_id_map` arms above it are cross-module refs and must stay exactly as they are. Thread an `nk_cache = {}` dict alongside the existing `status_id_cache` (views.py:1107).

**3g. Import, StatusType via the cache-restore path.** `_extract_cache_restore` (views.py:199-224) pops `status` out of the payload before `prepare_model_data` ever sees it, so the module `StatusType` FK bypasses 3f entirely. Change it to pop `status__nk` as well and hand both to the resolver. Rewrite `resolve_status_id` (views.py:1109-1124) to take `(value, nk)`: when `nk` is present, resolve through `resolve_natural_key(StatusType, nk)` and let an unresolvable key raise; when `nk` is absent, keep today's v1 behavior of returning the integer if it exists and `None` otherwise. Update the docstring, which currently asserts the false premise that reference PKs are stable across installations, to state the new rule. Both call sites need updating: views.py:1201 and views.py:1306.

**3h. Import, `module_types` (views.py:1173-1175).** Pop `module_types__nk` off `activity_data` alongside `module_types`. When the keys are present, resolve each through the registry and call `activity.module_types.set(resolved_pks)`; otherwise keep the raw pk list. Resolve before the `set()` call so an unknown module type fails by name rather than as an opaque M2M through-table integrity error.

**3i. Import, the error surface (views.py:1244-1249).** Add an `except UnresolvableNaturalKeyError as e:` branch ahead of the blanket `except Exception`, returning HTTP 400 with the message unmodified, not wrapped in the `Failed to import project: ` prefix. `UnresolvableNaturalKeyError.__str__` produces the named actionable message:

  `Cannot import: this file references reference data '{label}: {key}' that does not exist in this installation (offline build reference data may be out of date).`

Because every resolution happens before any `objects.create()`, this message names the model and the key rather than a sqlite deferred-FK table name (research pitfall 6). Keep the `transaction.atomic` block so a failed import creates nothing. Log at the same level the existing handler uses.

Do NOT add a `referenceDataFingerprint` envelope field. The research proposes the hard-fail path as the realization of guardrail (b), and a fingerprint on top of resolve-by-natural-key would refuse files that resolve correctly. Out of scope.

**3j. Tests, extend `api/tests/test_project_export.py`.** Add an `APITestCase`-based or `TestCase`-based class `ProjectImportNaturalKeyTests` covering every line of `<behavior>`.

The skew simulation, which is the load-bearing test and cannot boot two databases (research pitfall 7): create the reference rows through `get_or_create` in `setUp`, capture their real pks, then hand-build an import body whose integer for `gw_potential` is `<real_pk> + 1000` while `gw_potential__nk` names the real row. Assert HTTP 201 and `Project.objects.get(id=response.data["projectId"]).gw_potential_id == real_pk`. Add the nastier variant: create two GWP rows, point the integer at the wrong one and the key at the right one, and assert the key wins. Add the failure case: `gw_potential__nk: ["No Such Report"]` returns 400, the response body contains `does not exist in this installation`, and `Project.objects.count()` is unchanged.

Add a round-trip test: build a project with `country`, `climate`, `moisture`, `soil_type`, `gw_potential` and `status` set, `GET /api/projects/{pk}/export/`, `POST /api/projects/import_project/?forceCopy=true` with the parsed body, and assert every reference FK on the imported project equals the original. Add a v1 regression test asserting a body with no `__nk` keys still imports by integer.

Do not copy the `Country.objects.get_or_create(name=..., defaults={"code": "TC"})` idiom from `ThreadCommentExportImportTests` (test_project_export.py:181). `Country` has no `code` field, so that call raises on the create path; it is pre-existing breakage and out of scope for this task, but do not propagate it.
  </action>

  <verify>
    <automated>
cd /home/sirvosterzo/Developer/FAO/EXACT/exact-django-webapp/djangoexact
../.venv/bin/python -m py_compile api/serializers.py api/views.py api/tests/test_project_export.py
DJANGO_DEBUG=True ../.venv/bin/python manage.py makemigrations --check --dry-run
# compatibilityGroup must not have moved
DJANGO_DEBUG=True ../.venv/bin/python -c "
import json; c = json.load(open('../version.config.json'))
assert c['compatibilityGroup'] == 1, c
print('compatibility-group-unchanged')"
    </automated>
    <automated>
cd /home/sirvosterzo/Developer/FAO/EXACT/exact-django-webapp/djangoexact
cp $REF_DB $TEST_DB
CI=true DJANGO_DEBUG=True DB_ENGINE=django.db.backends.sqlite3 DB_NAME=$TEST_DB \
  ../.venv/bin/python manage.py test api.tests.test_project_export --keepdb
CI=true DJANGO_DEBUG=True DB_ENGINE=django.db.backends.sqlite3 DB_NAME=$TEST_DB \
  ../.venv/bin/python manage.py test api.tests.test_natural_keys api.tests.test_reference_parity --keepdb
    </automated>
  </verify>

  <done>
Exports carry `formatVersion: 2` with both encodings for every registered reference FK on projects, modules, submodules and the `module_types` M2M, while `compatibilityGroup` is still 1. An import resolves reference FKs by natural key and ignores a skewed integer, which is the bug closed. An unresolvable key returns 400 with the named actionable message and leaves no Project behind. `formatVersion: 1` files still import by integer pk. `math_model/` and `api/calculators.py` are untouched, and no cached-result policy changed. The full `test_project_export` module passes against a fixture-seeded sqlite database. Committed as `fix(api): resolve reference-data FKs by natural key on project import`.
  </done>
</task>

</tasks>

<verification>
Run from the Django root with the environment block above exported.

1. `../.venv/bin/python -m py_compile` over every changed Python file.
2. `DJANGO_DEBUG=True ../.venv/bin/python manage.py makemigrations --check --dry-run` is clean.
3. `bash scripts/build_offline_db.sh $SP/final.sqlite3` completes and `verify_reference_parity --app=all` exits 0 against the result, proving a fixture-only offline database is buildable end to end.
4. `check_reference_natural_keys` exits 0 against that database.
5. `CI=true ... manage.py test api.tests.test_project_export api.tests.test_natural_keys api.tests.test_reference_parity --keepdb` passes.
6. `git diff develop --stat` touches no file under `math_model/` or `api/calculators.py`, and `git status --short` still shows `.planning/STATE.md` and `djangoexact/scripts/ipcc_dump.py` as unstaged.
7. `git branch --show-current` is still `fix/export-import-reference-data-identity`.

Full-suite and Postgres verification are a CI or PR gate, not a local one. Note in the SUMMARY that the migration in task 2 has been proven only against fixture data and the shipped offline snapshot, never against production Postgres, and that `check_reference_natural_keys` must be run against production via cloud-sql-proxy before the migration is deployed.
</verification>

<success_criteria>
- Three atomic conventional commits, one per task, in order.
- The offline database is buildable from `migrate` + `load_reference_data --app=all`, and the `release/offline-tool` actions are documented as an ordered checklist rather than performed.
- Every reference model reachable as a Project/Activity/Module FK has a natural key backed by a database uniqueness guarantee, `ipcc.GlobalWarmingPotential` included.
- Duplicate detection ran before the constraints were added, on two independent datasets.
- A v2 file imports correctly across skewed reference PKs; an unresolvable key hard-fails by name; a v1 file still imports.
- `compatibilityGroup` is 1, the public API contract is additive-only, and no calculation code was touched.
</success_criteria>

<output>
Create `.planning/quick/260813-fvj-when-import-exporting-from-online-tool-t/260813-fvj-SUMMARY.md` when done.

Carry forward into the SUMMARY:
- The measured cost of a sqlite `migrate` run, so the packaging owner can budget it.
- The exact `release/offline-tool` handoff steps that remain unperformed, and the fact that the packaging mechanism is still unconfirmed.
- That the uniqueness migration is unvalidated against production data (research assumption A3), with the cloud-sql-proxy command to validate it.
- The count of `.exactproject` files already in the wild from offline builds is still unknown (research open question 3), so v1 files keep importing by integer pk and will keep mis-resolving where reference data has drifted. Only re-exporting from a repaired offline build fixes those.
</output>
