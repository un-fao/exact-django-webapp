# Architecture Research

**Domain:** Brownfield hardening of a Django 5.2 + DRF GHG emissions calculator (EX-ACT)
**Researched:** 2026-07-08
**Confidence:** HIGH (existing codebase map + official Django docs); MEDIUM on CI-shape specifics (community best practice, no single canonical source)

This document does not propose a new architecture. EX-ACT already has a clean four-layer design (DRF API, calculator adapters, pure math, IPCC reference data), documented in `.planning/codebase/ARCHITECTURE.md`. The job here is to say, for each of the seven hardening integration points named in this milestone, which existing layer or file it belongs in, what talks to what, and in what order the work should land so nothing regresses.

## Standard Architecture (existing, unchanged)

### System Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                        REST API Layer (DRF)                          │
│  api/views.py, api/serializers.py, api/urls.py                       │
│  Structural/type validation only (validate_[field], serializer types)│
├─────────────────────────────────────────────────────────────────────┤
│              Adapter Layer (calculators/ package, was calculators.py)│
│  BaseCalculator, LandModuleCalculator, CalculatorFactory              │
│  NEW: scenario pre-flight validation lives here                       │
│  NEW: ScenarioType enum consumed here (defined in api/utilities.py)   │
├────────────────────────┬──────────────────────────────────────────────┤
│           Pure Math Layer (no_time_dependency_final/)                 │
│  annuals.py, livestock.py, forest_management.py, value_chains.py, ... │
│  No Django imports. NEW: primary home for golden-file regression tests│
├────────────────────────┬──────────────────────────────────────────────┤
│               Reference Data Layer (ipcc app + api/defaults.py)       │
│  DefaultsFactory (api/defaults.py)                                     │
│  NEW: lru_cache on lookup methods, per gunicorn worker                │
└─────────────────────────────────────────────────────────────────────┘

Cross-cutting, outside the four layers:
  - CI (.github/workflows/deploy.yaml): provisions Postgres, loads fixtures once,
    runs pytest + bandit + pip-audit + `manage.py check --deploy`, gates deploy.
  - Django system checks framework (new api/checks.py): DEBUG/CORS deploy assertions.
```

### Component Responsibilities

| Component | Responsibility | Where it lives |
|-----------|----------------|------------------|
| Serializers | HTTP payload shape and type validation only | `api/serializers.py` (unchanged) |
| BaseCalculator | Scenario pre-flight validation, defaults resolution hand-off, math invocation | `api/calculators/base.py` (new package) |
| CalculatorFactory | Model class name to Calculator class resolution | `api/calculators/factory.py` (new package) |
| ScenarioType | Single source of truth for start_w/start_wo/w/wo | `api/utilities.py` (existing file, expanded) |
| DefaultsFactory | IPCC lookup resolution, now cached | `api/defaults.py` (unchanged location, new caching) |
| math_model functions | Pure calculation, golden-tested | `math_model/no_time_dependency_final/*.py` (unchanged) |
| Django deploy checks | DEBUG/CORS assertions | new `api/checks.py`, registered in `api/apps.py` |
| CI workflow | Test DB provisioning, fixture load, test/security gates | `.github/workflows/deploy.yaml` (extended) |

## Integration Point 1: Scenario-Level Input Validation

**Recommended placement: `BaseCalculator.calculate()` pre-flight, not the serializer layer.**

Serializers already have a job in this codebase: structural and type validation (`validate_[field]()`, FK existence, numeric ranges). They do not know, and should not need to know, which fields a module must have to be computable under `start`, `with`, or `without`. That knowledge already lives one layer down, inside `calculators.py`, in the `is_with()` / `is_without()` / `is_business_as_usual()` helpers that the existing codebase map flags as an anti-pattern (they inspect module attributes ad hoc instead of taking scenario as an explicit input). Putting scenario validation in the serializer would duplicate that logic in a second place and would still not prevent a deep math-layer stack trace on save-then-recalculate flows that bypass the serializer entirely (report generation, LUC batch jobs).

Concretely:
- Add `BaseCalculator.validate_scenario_inputs(scenario: ScenarioType) -> None` that raises a new `ScenarioValidationError` (subclass in `api/calculators/exceptions.py` or reuse DRF's `ValidationError`) listing every missing required field, its expected type, and the scenario it was required for.
- Call it at the top of `calculate()`, before any IPCC defaults are resolved or math functions invoked, so failures surface as a 400 with a precise message instead of an unguarded exception from deep inside `math_model`.
- This matches the existing error-handling convention already documented for the adapter layer: adapters raise, DRF's exception handler turns that into a 400.

**Component boundary:** Serializer layer validates "is this a well-formed request." Calculator layer validates "is this request complete enough to compute the requested scenario." Math layer never sees an incomplete input; it assumes validity.

**Build order implication:** This depends on the `ScenarioType` enum (Integration Point 4) existing first, since the validation rules are keyed by scenario, and it is safest done after golden-file tests exist (Integration Point 2), so any accidental behavior change introduced while adding pre-flight checks is caught immediately rather than discovered post-deploy.

## Integration Point 2: Golden-File Test Placement

**Recommended placement: primarily `math_model/no_time_dependency_final/`, with a thin secondary layer at the calculator adapter for marshalling-specific bugs.**

The math layer is the only layer with zero Django/DB dependency, so it is the only layer that can produce fast, deterministic, DB-free fixtures. A golden test here calls a math function directly with literal dict/dataclass inputs and asserts against a stored JSON/CSV of known-correct outputs, with no database, no fixtures, no `load_reference_data`. This is also where the existing test suite already has a (thin) precedent: `math_model/tests/repro_perennial_agb_max_zero.py`.

The calculator adapter layer is a poor place for the bulk of golden tests because every test there requires a populated test database (IPCC fixtures, factory-boy objects), which is slow and couples the golden values to reference-data state that, while PK-stability-guarded, is still mutable over time. Reserve adapter-layer tests for the small number of bugs that live in the marshalling itself, not in the math:

- Aquaculture electricity default hardcoded to 0 (`calculators.py` line ~3624)
- Peat conversion factor TODOs (`calculators.py` lines ~6808, 6906)
- Forestry start-value reuse across scenarios (`calculators.py` lines ~7265, 7399, 7476-7477)

These three are adapter-layer defects (wrong value fed into an otherwise-correct math function), so a math-layer golden test cannot catch them; only a calculator-layer test that exercises `CalculatorFactory.calculate_result()` against a real module instance will.

Priority order for new golden fixtures, per the audit's own fragility ranking: value chains (energy + refrigerants, flagged HIGH priority test gap), flooded-rice minor seasons with tier-2 overrides, forest-management biomass matrices.

**Component boundary:** `math_model/tests/` is DB-free and framework-agnostic, testable in complete isolation, and should be the majority of new golden coverage. `api/tests/` (adapter-layer) golden tests are TestCase/APITestCase-based, require fixtures, and should stay narrowly scoped to the three known marshalling bugs above plus any future one found the same way.

**Build order implication:** This is the first code-facing step in the milestone, ahead of the `calculators.py` split (Integration Point 3), the bug fixes, and the scenario validation work. It is the regression safety net the CONCERNS.md audit says is currently "partial." Nothing else in this milestone should land until the fragile paths it names have golden coverage, because every other change (split, caching, validation) touches the exact files where the known bugs live.

## Integration Point 3: Splitting `calculators.py` into a Package

**Recommended structure: `api/calculators/` package with a re-export shim, so every existing import keeps working unchanged.**

```
api/calculators/
├── __init__.py       # re-export shim: from .base import *, from .factory import CalculatorFactory, etc.
├── base.py           # BaseCalculator, LandModuleCalculator, shared scenario helpers
├── factory.py         # CalculatorFactory only; imports every domain module below to build its registry
├── land.py            # AnnualCropland/PerennialCropland/Grassland/ForestManagement/CoastalWetlands calculators
├── livestock.py        # Livestock + manure management calculators
├── aquaculture.py      # Fisheries and aquaculture calculators
├── energy.py           # Fuel, Electricity, Transport, Input calculators
└── value_chains.py     # ValueChain, Storage, Processing, Packaging, Refrigerant calculators
```

`api/calculators.py` (the 8,270-line file) becomes a directory. Because Python resolves `import api.calculators` and `from api.calculators import X` identically whether `calculators` is a module or a package, every one of the 60+ existing call sites in `api/views.py`, `api/reports/`, and `api/tests/` continues to work unmodified as long as `__init__.py` re-exports every public name the old module exposed. This is the re-export shim pattern: `__init__.py` does the importing, nothing else changes.

Domain files (`land.py`, `livestock.py`, etc.) should only import from `calculators/base.py`, `api/models.py`, `api/defaults.py`, and `math_model/`, never from each other. `factory.py` is the one place allowed to import across all domain files, since building the class-name-to-calculator registry is its sole job. This avoids recreating a second monolith of criss-crossing imports inside the new package.

The scenario helpers (`is_with()`, `is_without()`, `is_business_as_usual()`) flagged as an anti-pattern in the codebase map belong in `base.py` for this split; extracting them into a separate `api/services/scenario_resolution.py` service class is a larger, separate refactor not scoped to this milestone (it is not listed under Active requirements) and should not be conflated with the mechanical package split.

**Component boundary:** `api/calculators/__init__.py` is the only public surface. Nothing outside the package should ever do `from api.calculators.land import X` directly; that keeps the internal file layout free to change again later without breaking callers.

**Build order implication:** Do this only after golden-file tests exist (Integration Point 2), since it is the highest-risk mechanical change (moving 8,270 lines) and needs a regression net that does not itself live inside the file being moved. Do it as a pure extraction, no behavior change, in its own commit, verified by the golden tests plus the existing suite. Layer in the `ScenarioType` enum replacement (Integration Point 4), scenario validation (Integration Point 1), and the three known bug fixes afterward, one domain file at a time, now that each file is small enough to review safely in isolation. Splitting before fixing keeps "moved code" and "changed behavior" as separate, independently revertable commits.

## Integration Point 4: Where `ScenarioType` Should Live

**Recommended placement: `api/utilities.py`, expanding the existing (partial) `ScenarioTypes` already documented there.**

`api/utilities.py` is already the lowest node in the `api/` import graph: it holds helpers and constants and imports nothing from `api/models.py`, `api/calculators.py`, or `api/reports/`. Every other module in the four-layer stack that needs scenario information (calculators, models, serializers, views, reports) already imports things that themselves sit above `utilities.py`, so anything can import `utilities.py` without creating a cycle. This is also where the codebase's own naming convention already places it (`ScenarioTypes` is documented as living in `api/utilities.py`), so this is consolidation, not a new location.

Two locations were explicitly considered and rejected:
- `api/models.py`: works without a cycle (models.py has no dependents inside this stack that don't already depend on it), but ties a pure value type to a Django models file with migration-sensitive weight. No functional reason to put it there.
- Inside the new `api/calculators/` package: would work for `api/` and `api/reports/` (both already depend on calculators), but adds an unnecessary dependency direction: models.py and serializers.py should not need to import from the calculator/adapter layer just to get an enum value.

`math_model/` (pure math layer) does not need this enum. Looking at the existing data flow, math functions receive `with`/`without` input pairs already separated by the calculator before invocation; they do not branch on a scenario tag themselves. Keeping the enum out of `math_model/` preserves the layer's "zero Django/framework or app-layer dependency" invariant, since `api/utilities.py` is still an `api`-app file even though it's dependency-light.

**Component boundary:** `api/utilities.py` has zero inbound dependencies from other `api/` submodules and zero outbound dependencies on them either. It is a leaf that everything in `api/` and `api/reports/` can safely import.

**Build order implication:** This is cheap and foundational; it should land early, either just before or in the same phase as the `calculators.py` split, since the split is the natural moment to replace hardcoded scenario strings per-domain-file rather than doing a second full-codebase sweep later. It should exist before scenario validation (Integration Point 1) is added, since that validation is keyed by scenario value.

## Integration Point 5: IPCC Reference-Table Caching

**Recommended placement: `functools.lru_cache` on `DefaultsFactory`'s individual lookup methods in `api/defaults.py`, not a manually-populated module-level singleton dict.**

The production topology matters here: App Engine runs Gunicorn with `-w 4`, meaning four separate pre-forked worker processes, each with its own Python heap. Any caching strategy is per-worker regardless of shape; the question is only whether it is eager or lazy, and how it is keyed.

An eagerly-built module-level singleton (loading every IPCC table into a dict at import/startup time) adds cold-start query cost to every one of the four workers on every deploy or restart, and requires hand-rolled key construction for every table shape (region, climate, tier), which is exactly the kind of ad hoc pattern the codebase map already flags as scattered ("Calculator-specific Defaults Resolution" anti-pattern: some calculators call `defaults.py`, some run inline queries).

`functools.lru_cache` decorating `DefaultsFactory`'s existing `get_fi_data()`, `get_fmg_data()`, and similar methods is lazy (first call per worker populates it, no added cold-start cost), naturally keyed by the primitive arguments those methods already take (per the existing code at `calculators.py` lines ~263-269 and ~294-298, these already accept hashable IDs rather than QuerySets), and requires no new caching abstraction: `DefaultsFactory` already exists as the documented "module-level singleton" home for this concern. This is also literally what the audit itself proposes as the fix.

Because IPCC reference data is immutable in practice (loaded via `load_reference_data`, changed only through the guarded `dump_reference_data` round-trip), there is no cross-worker cache invalidation problem to solve: each worker's `lru_cache` simply reflects the data it read at first use, and any legitimate reference-data change already requires a full app redeploy (which recycles all workers) under the existing fixtures workflow. A shared cache (Redis/memcached) would be solving a staleness problem that does not exist for this data.

**Important sequencing note:** caching only fixes call sites that already go through `DefaultsFactory`. The audit separately flags that some calculators query IPCC tables inline instead of through `defaults.py`. Caching should be paired with consolidating those inline call sites onto `DefaultsFactory`, otherwise the N+1/repeated-query problem persists for the bypassing calculators and the milestone under-delivers on its own stated goal.

**Component boundary:** Caching lives entirely inside `api/defaults.py`. Neither the `api/calculators/` package nor `math_model/` should know caching exists; calculators keep calling `DefaultsFactory` exactly as before, math functions never touch the DB or cache at all.

**Build order implication:** Independent of the `calculators.py` split, but touches some of the same call sites (the inline-query consolidation), so it is efficient to do the consolidation after the split (smaller, per-domain files are easier to audit for stray inline queries) but the `lru_cache` decoration itself has no hard dependency on the split completing first. Golden-file tests (Integration Point 2) should exist before this lands, since they are the mechanism that proves caching does not change any computed number, only how often it is fetched.

## Integration Point 6: CI Test Database Provisioning and Fixture Loading

**Recommended placement: a Postgres service container in `.github/workflows/deploy.yaml`, with `load_reference_data` run exactly once per CI job as a fixed setup cost, ahead of the test run.**

Use a real Postgres service container, not SQLite, in GitHub Actions. Production runs Cloud SQL Postgres via `psycopg2-binary`; testing against SQLite risks passing tests that would fail against Postgres-specific behavior (this is the standard "test against what you deploy" guidance for Django CI, not something specific to this codebase).

The 30-plus-second `load_reference_data` cost, called out explicitly in this project's own fixtures guide, should be paid once per CI job run, as an explicit workflow step (`python manage.py migrate` then `python manage.py load_reference_data --app=all`), before `pytest` (or `manage.py test`) executes. GitHub-hosted runners are ephemeral VMs; there is no reliable way to persist a warmed Postgres data directory across separate workflow runs without material extra infrastructure (self-hosted runners, external cache volumes), so treating the fixture load as a fixed per-run setup cost is the pragmatic choice rather than trying to cache the database state itself. What should be cached is the pip dependency install (`actions/setup-python`'s built-in `cache: pip`, keyed on `requirements.txt`), since that is the larger and genuinely cacheable cost on a cold runner.

Because `TestCase`-based tests roll back per-test transactions, and fixture rows are committed to the test database before the suite starts (outside any individual test's transaction), every test in the run starts from that same seeded baseline for free; there is no need for `pytest-django`'s per-session fixtures (already excluded per this project's testing constraints, since `pytest-django` is not installed) or a custom `conftest.py` fixture. This matches the codebase's own documented pattern of calling `call_command("load_reference_data", "--app=all", verbosity=0)` once ahead of test execution.

Recommended job shape:
```yaml
services:
  postgres:15 (with matching DB_* env vars)
steps:
  - checkout
  - setup-python 3.11, cache: pip
  - pip install -r djangoexact/requirements.txt
  - python manage.py migrate
  - python manage.py load_reference_data --app=all     # ~30s, paid once
  - pytest                                              # or manage.py test
  - bandit -r djangoexact -x djangoexact/venv,djangoexact/node_modules
  - pip-audit -r djangoexact/requirements.txt
  - python manage.py check --deploy --fail-level WARNING --settings=<production settings>
  # any non-zero exit above blocks the subsequent deploy job/step
```

**Component boundary:** this is entirely outside the four application layers; it is workflow configuration that invokes existing management commands (`migrate`, `load_reference_data`) and existing tools (`pytest`, `bandit`, `pip-audit`) unchanged. No application code is touched.

**Build order implication:** This has no code dependency on any other item in this milestone and should be built first. Every other change in this milestone (validation, golden tests, the split, caching, bug fixes) is only trustworthy once there is a CI gate that actually runs the test suite before deploy; today neither GitHub Actions nor Bitbucket does. CI first means every subsequent phase's commits are gated automatically as they land, rather than retrofitting a gate after the fact.

## Integration Point 7: DEBUG/CORS Pre-Deploy Assertions

**Recommended placement: both, doing different jobs. The Django system checks framework owns the rule; the CI script owns invoking it and enforcing the exit code.**

Confirmed against current Django documentation: the system checks framework's `deploy=True` mechanism (`@register(Tags.security, deploy=True)`, registered inside an `AppConfig.ready()`) is exactly Django's built-in extension point for "only run this check when deploying," invoked via `django-admin check --deploy --settings=<production_settings>`. This is where the actual assertion belongs, as a new custom check in `api/checks.py` (registered from `api/apps.py`) asserting the project-specific pattern this audit already flagged: `CORS_ORIGIN_ALLOW_ALL = DEBUG` in `settings.py`, meaning a DEBUG=True slip in production silently opens CORS to every origin. The custom check should assert `DEBUG is False` and `CORS_ALLOWED_ORIGINS` is a non-empty list; Django's own built-in deploy checks already cover many general security settings, so this new check only needs to add the project-specific CORS-tied-to-DEBUG assertion, not duplicate Django's existing ones.

One detail confirmed via the Django docs that changes how CI must invoke this: `django-admin check` only exits non-zero by default for messages at `ERROR` level or above; a check that returns a `Warning` (the type shown in Django's own documented example for custom deploy checks) will print but not fail the command, and would silently let CI proceed anyway. Django's `check` command exposes `--fail-level {CRITICAL,ERROR,WARNING,INFO,DEBUG}` specifically for this. The CI step must invoke `python manage.py check --deploy --fail-level WARNING --settings=<production_settings>` (or define the new check using `Error` instead of `Warning`, forcing failure at the default level) for this to actually block a bad deploy rather than just log a message nobody reads.

**Component boundary:** the check definition (`api/checks.py`) is Django-framework-integrated application code, versioned with the rest of the app, testable in isolation (call the check function directly with `override_settings`). The CI script's role is one line invoking the existing `manage.py check --deploy` command with the right settings module and fail-level; it does not encode any of the assertion logic itself.

**Build order implication:** This depends only on CI existing (Integration Point 6) to have somewhere to run it, since a check with no CI step to invoke it is dead code. It has no dependency on any of the calculator/math-layer work (Integration Points 1 through 5) and can be built in parallel with them, right after CI lands.

## Recommended Build Order (dependency-driven)

1. **CI pipeline** (Integration Point 6): Postgres service container, one-time fixture load, pytest + bandit + pip-audit gate. No code dependency on anything else; unblocks trustworthy verification for every later step.
2. **Deploy checks** (Integration Point 7): custom `api/checks.py` plus the `manage.py check --deploy --fail-level WARNING` CI step. Depends only on step 1 existing to run in.
3. **Golden-file tests** (Integration Point 2): math-layer fixtures for value chains, flooded-rice minor seasons, forest-management matrices, plus the three adapter-layer marshalling-bug tests. This is the regression net every subsequent step below relies on.
4. **`ScenarioType` enum** (Integration Point 4): consolidate into `api/utilities.py`. Cheap, foundational, low risk once golden tests exist to confirm no behavior drift from the string-to-enum swap.
5. **`calculators.py` package split** (Integration Point 3): pure mechanical extraction into `api/calculators/`, re-export shim, verified against golden tests plus the existing suite, no behavior change in this commit.
6. **Scenario pre-flight validation** (Integration Point 1) and **known tier-2 bug fixes** (aquaculture electricity default, peat conversion factors, forestry start-value reuse): now landed per-domain-file inside the split package, one file at a time, each independently reviewable and each verified against golden tests.
7. **IPCC caching** (Integration Point 5): `lru_cache` on `DefaultsFactory` lookups, paired with consolidating any remaining inline IPCC queries onto `DefaultsFactory`. Independent of steps 3-6 but easiest once the split (step 5) has made the call sites smaller to audit.

Steps 1-2 have no dependency on the math/calculator work and can run as their own early phase. Steps 3-6 are strictly ordered (each is the safety net or foundation for the next). Step 7 can run in parallel with steps 4-6 once step 3 (golden tests) exists, but is easiest sequenced after step 5 (the split) for review-ability.

## Anti-Patterns to Avoid During This Hardening Work

### Anti-Pattern 1: Adding validation logic to the serializer because "that's where validation goes"

**What people do:** Put scenario-required-field checks into `ActivityBuilderSerializer` or module serializers' `validate()` methods.
**Why it's wrong:** Scenario eligibility logic already lives in the calculator layer (`is_with()`/`is_without()`/`is_business_as_usual()`); duplicating it in serializers creates two sources of truth that will drift, and does not protect non-serializer call paths (report generation, LUC batch recompute) that skip the serializer entirely.
**Do this instead:** Validate in `BaseCalculator.calculate()`, the one place every computation path (API request, report generation, batch job) already funnels through.

### Anti-Pattern 2: Splitting `calculators.py` and fixing bugs/adding validation in the same commit

**What people do:** Use the file-split as an opportunity to also fix the aquaculture/peat/forestry bugs and add scenario validation, all at once, since "you're already in there."
**Why it's wrong:** An 8,270-line mechanical move is already the highest-risk single change in this milestone; bundling behavior changes into the same diff makes it impossible to bisect a regression to "the move" versus "the fix."
**Do this instead:** Split first as a pure extraction (verified by golden tests plus the existing suite, no behavior change), then land fixes and validation per-domain-file in separate, smaller commits.

### Anti-Pattern 3: Eagerly loading all IPCC tables into a hand-built module-level cache at app startup

**What people do:** Build a single dict cache populated by a startup hook, keyed by ad hoc tuples.
**Why it's wrong:** Adds cold-start query cost to all four Gunicorn workers on every restart, requires hand-rolled cache-key construction, and solves a staleness problem (concurrent reference-data updates) that does not exist for genuinely immutable, fixture-loaded data.
**Do this instead:** `functools.lru_cache` on `DefaultsFactory`'s existing lookup methods; lazy, per-worker, keyed automatically by the primitive arguments those methods already accept.

### Anti-Pattern 4: Treating a `Warning`-level Django deploy check as sufficient for CI gating

**What people do:** Register the DEBUG/CORS check with Django's documented example pattern (`Warning`) and assume `manage.py check --deploy` in CI will fail the build if it fires.
**Why it's wrong:** Django's `check` command only exits non-zero for `ERROR` level and above by default; a `Warning` prints but does not fail the command, so CI would appear green even with DEBUG=True in the checked settings.
**Do this instead:** Either register the check as `Error`, or invoke CI with `python manage.py check --deploy --fail-level WARNING`.

## Sources

- `.planning/codebase/ARCHITECTURE.md` (project codebase map, refreshed 2026-07-08) - HIGH confidence, primary source for existing four-layer design, data flow, and documented anti-patterns.
- `.planning/codebase/STRUCTURE.md` (project codebase map, refreshed 2026-07-08) - HIGH confidence, primary source for file layout and naming conventions (including existing partial `ScenarioTypes` location).
- `.planning/codebase/CONCERNS.md` (project codebase map, refreshed 2026-07-08) - HIGH confidence, source of the specific known bugs (aquaculture electricity default, peat conversion factors, forestry start-value reuse), the fragile-area fix approaches, and the CI/caching gaps this milestone addresses.
- `.planning/codebase/STACK.md` and `.planning/codebase/TESTING.md` (project codebase map, refreshed 2026-07-08) - HIGH confidence, Gunicorn worker count, pytest-django exclusion, existing test patterns.
- Django official documentation, "How to write and use system checks" and `django-admin` reference, `/websites/djangoproject_en_5_2` via Context7 - HIGH confidence, confirms `@register(Tags.security, deploy=True)` pattern, `check --deploy`, and the `--fail-level` default-is-ERROR behavior.
- Community sources on Django + GitHub Actions + Postgres CI setup (Simon Willison's TIL, Hacksoft blog, Loopwerk, healthchecks.io blog) - MEDIUM confidence, general best-practice consensus (test against real Postgres, cache pip installs, treat migrations/fixture loading as a fixed per-run cost), no single canonical source, cross-checked across multiple independent write-ups reaching the same conclusions.

---
*Architecture research for: EX-ACT backend hardening milestone*
*Researched: 2026-07-08*
