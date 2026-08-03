# Project Research Summary

**Project:** EX-ACT Backend: Reliability & Maintainability Hardening
**Domain:** Brownfield Django 5.2 + DRF GHG emissions calculator (backend hardening, no new features)
**Researched:** 2026-07-08
**Confidence:** MEDIUM-HIGH (existing codebase well-documented; stack/architecture patterns verified against official docs; CI/pitfalls grounded in production environment specifics)

## Executive Summary

EX-ACT is a live GHG emissions calculator wrapped in a Django REST Framework API, deployed to App Engine Standard with a Postgres backend and Firebase auth. The codebase is functionally sound but lacks critical hardening: CI deploys without running tests, calculators are scattered across an 8,270-line "god object" module, and golden-file regression coverage is partial. This research recommends a four-phase hardening strategy (CI foundation, correctness safety-net, maintainability refactors, performance plus auth hardening) executed in strict dependency order: CI first (foundation for all other work), then correctness safety-nets, then refactoring. The approach avoids common brownfield pitfalls (SQLite-vs-Postgres drift, silent scenario-dispatch regressions, reference-data cache staleness) by sequencing work strictly to dependencies and running full regression coverage after each change.

The recommended stack is minimal and low-risk: layering pytest-django on top of the existing Django TestCase classes (not replacing them), adding syrupy for golden-file snapshots with tolerance-aware float comparison, and wiring GitHub Actions to run a real Postgres service container with fixture loading before deploy. This is not a large rewrite: the goal is to make the existing, mostly-correct code safe to change by closing the regression-detection gaps the audit flagged. Success looks like: CI blocks deploys on test failure, fragile calculator paths are covered by golden files, the three known tier-2 bugs are fixed, and the codebase can be refactored (calculators.py split) with confidence that numeric results cannot drift undetected.

## Key Findings

### Recommended Stack

The stack is pragmatic and conservative, avoiding large dependencies or test-framework migrations. Key technologies from STACK.md:

**Core technologies:**
- **pytest-django 4.12.0** (bridges pytest and Django ORM without forcing a migration off existing TestCase classes): Adds fixtures like `db` and `django_assert_num_queries` that layer on top of the existing APITestCase suite. Zero risk of breaking existing tests since Django's own TestCase/APITestCase remain the base. Compatibility verified against pytest 9.0.3 already pinned.
- **syrupy 5.5.2** (golden-file/snapshot testing for calculator output): JSONSnapshotExtension serializes MathResult dicts, `path_type` matchers exclude non-deterministic fields. Zero runtime dependencies. Preferred over pytest-regressions or hand-rolled comparison scripts for its broader adoption and JSON-native format.
- **pytest.approx** (built into pytest 9.0.3, no new dependency): Wraps numeric expected values with explicit relative tolerance (e.g., `rel=1e-6` for emissions totals). Prevents flaky tests from IEEE-754 accumulation differences across numpy/BLAS versions.
- **django-zeal 2.2.1** (N+1 query detection): Actively maintained Django fork of the original nplusone (unmaintained since 2020). Detects missing select_related/prefetch_related. Configurable per-test, no production overhead.
- **GitHub Actions Postgres service container** (production-matching test database): Real Postgres matching Cloud SQL in production, not SQLite. Catches JSONField, constraint, and migration behavior that SQLite hides. No additional Action or marketplace integration needed.
- **bandit 1.9.4 + pip-audit 2.10.1** (security scanning): Already used locally per README. CI integration via `pypa/gh-action-pip-audit` official Action. Gate deploy on HIGH severity/confidence findings only to avoid noisy low-severity gates.

Full stack details, alternatives considered, and version compatibility are in `.planning/research/STACK.md`. No experimental or unproven libraries; everything is stable and widely adopted.

### Expected Features

The milestone has nine target features across five clusters, codified as a dependency graph in FEATURES.md. All are table-stakes for calling the milestone "hardened":

**Must have (table stakes):**
1. CI test automation (pytest gates deploys, bandit/pip-audit block on HIGH findings, Postgres service container with `load_reference_data`)
2. Fail-fast scenario validation (BaseCalculator validates upfront before any math invocation)
3. Golden-file tests (syrupy snapshots for value-chains, flooded-rice, forest-management; tolerance-aware assertions)
4. Tier-2 fallback bug fixes (aquaculture electricity default of 0, peat conversion factors, forestry cross-scenario reuse)
5. Firebase auth sync tests (UID mismatch, email divergence, concurrent registration; mocked firebase_admin)
6. Rate limiting on auth endpoints (DRF ScopedRateThrottle: 5/min on auth endpoints vs 60/min global)
7. Production config sanity check (Django system check asserting DEBUG=False and non-empty CORS_ALLOWED_ORIGINS)
8. N+1 elimination plus regression tests (select_related/prefetch_related with assertNumQueries)
9. IPCC reference-table caching (functools.lru_cache on DefaultsFactory lookups)
10. calculators.py decomposition phase 1 (land-module or value-chains split into api/calculators/ package with re-export shim)

Feature dependencies (golden files must precede calculators split, validation before or alongside golden files, CI before everything else) are detailed in FEATURES.md.

### Architecture Approach

The existing four-layer architecture (DRF API -> calculator adapters -> pure math -> IPCC reference data) is sound and stays unchanged. From ARCHITECTURE.md, the hardening work maps to seven integration points within this structure:

**Major components and their integration points:**
1. **REST API Layer (DRF)** - Structural/type validation only (unchanged). Scenario validation moves to adapter layer.
2. **Adapter Layer (calculators)** - NEW: BaseCalculator.validate_scenario_inputs() runs upfront. NEW: ScenarioType enum consumed here. Split into api/calculators/ package by domain with re-export shim. Three known marshalling bugs fixed here.
3. **Pure Math Layer** - Framework-agnostic, DB-free. PRIMARY home for golden-file regression tests via syrupy snapshots. No logic changes.
4. **Reference Data Layer** - NEW: lru_cache on DefaultsFactory methods. Per-worker, lazy, no cross-worker invalidation risk.

Cross-cutting:
- **CI workflow** (.github/workflows/deploy.yaml) - Postgres service container, fixture load, pytest + bandit + pip-audit gate, blocks deploy.
- **Django system checks** (new api/checks.py) - DEBUG/CORS pre-deploy assertions, invoked via `manage.py check --deploy --fail-level WARNING`.

Recommended build order: CI first (no code dependency, unblocks verification for all others), then deploy checks, then golden files, then ScenarioType enum, then calculators split, then validation/bug fixes, then IPCC caching.

### Critical Pitfalls

Five top pitfalls from PITFALLS.md with prevention strategies:

1. **CI gate ships red-herring green because it never ran against production-like data** (Pitfall 1): Prevent by provisioning a real Postgres service container, running `load_reference_data --app=all` as an explicit CI step, failing the job if fixtures timeout, running `test_reference_bootstrap.py`'s round-trip check. Warning: CI test run completes in under 30 seconds (fixtures never loaded).

2. **Fail-fast calculator validation breaks existing user projects that relied on lenient defaults** (Pitfall 3): Prevent by auditing the three known lenient paths before writing validation, classifying each as "keep the default" or "fix the data model", running validation tests against a real-project-shaped fixture, rolling out as warning/log-only first.

3. **Golden-file tests assert exact floating-point equality and become permanently flaky or stale** (Pitfall 4): Prevent by using assertAlmostEqual with explicit documented tolerance (e.g., `rel=1e-6`), pinning numpy/pandas versions, treating golden-file regeneration as a reviewed change, cross-checking audit-flagged paths against excel_reference_version/ mirror.

4. **God-object refactor of calculators.py silently changes scenario dispatch behavior** (Pitfall 5): Prevent by sequencing the refactor strictly after golden-file coverage exists, doing one domain at a time with each move as its own commit/PR, grepping for cross-references before moving, running the full test suite between each move, explicitly verifying CalculatorFactory's model-to-calculator mapping.

5. **Rate limiting on App Engine Standard silently no-ops across instances or locks out the frontend** (Pitfall 7): Prevent by configuring a shared cache backend (Memorystore/Redis) for the throttle cache alias (verified by multi-instance smoke test), setting DRF's NUM_PROXIES to the actual verified proxy hop count, load-testing against a realistic multi-instance burst.

Full pitfall details, recovery strategies, and a "looks done but isn't" verification checklist are in PITFALLS.md.

## Implications for Roadmap

Based on dependencies discovered in research, the milestone should be executed in four phases:

### Phase 1: CI Foundation & Deploy Checks
**Rationale:** This has no code dependency on anything else and unblocks trustworthy verification for every later phase.

**Delivers:**
- GitHub Actions test job with real Postgres service container (postgres:16, matching production)
- One-time fixture load: `python manage.py migrate` then `python manage.py load_reference_data --app=all` (30+ seconds)
- `pytest` gating deploy on failure
- `bandit` and `pip-audit` gating deploy on HIGH severity+confidence findings only
- Custom Django system check in new `api/checks.py` asserting `DEBUG is False` and `CORS_ALLOWED_ORIGINS` is non-empty
- `.github/workflows/deploy.yaml` restructured with `needs:` job dependency

**Avoids pitfalls:** Pitfall 1, Pitfall 2 (SQLite-vs-Postgres drift)
**Timeline:** P1 (low risk, foundational)

### Phase 2: Correctness Safety-Net
**Rationale:** Golden files are the regression foundation that every later phase (refactoring, bug fixes) depends on.

**Delivers:**
- Golden-file tests (syrupy snapshots with pytest.approx tolerance): value-chains energy/refrigerants, flooded-rice minor-seasons, forest-management biomass matrices
- Scenario-level input validation in BaseCalculator.calculate()
- Tier-2 bug fixes with before/after regression tests
- ScenarioType enum in api/utilities.py (str-subclass for backward compatibility)

**Avoids pitfalls:** Pitfall 3 (validation breaks lenient defaults), Pitfall 4 (golden-file brittleness)
**Timeline:** P1 (medium risk but critical foundation)

### Phase 3: Maintainability Refactors
**Rationale:** Only sequenced after Phase 2 (golden-file coverage exists to catch regressions). Highest-risk mechanical change, golden files are the regression detector.

**Delivers:**
- calculators.py decomposition phase 1: land-module (or value-chains, whichever has golden coverage first) split into api/calculators/ package with re-export shim
- Re-export shim ensures every existing import still works unchanged
- Pure extraction first (no behavior change), verified by golden-file suite plus existing suite
- Each domain's move is its own commit/PR, with full test suite run between each move

**Avoids pitfalls:** Pitfall 5 (god-object refactor regression)
**Timeline:** P1 (high risk, but golden files mitigate it)

### Phase 4: Performance & Auth Hardening
**Rationale:** Sequenced after Phase 2 (golden files exist to catch silent data-shape regressions).

**Delivers:**
- N+1 elimination plus regression tests: select_related/prefetch_related on project/activity ViewSets, assertNumQueries regression tests
- IPCC reference-table caching: functools.lru_cache on DefaultsFactory methods, lazy per-worker, explicit invalidation hook
- Firebase auth sync integration tests: UID mismatch, email divergence, concurrent auth events (mocked firebase_admin)
- Rate limiting on auth endpoints: DRF ScopedRateThrottle (5/min auth scope), shared cache backend (Memorystore/Redis)

**Avoids pitfalls:** Pitfall 7 (rate limiting per-instance no-op), Pitfall 8 (reference-data cache staleness), Pitfall 9 (N+1 fix changes data semantics)
**Timeline:** P1 (lower risk than Phase 3, but rate limiting needs infrastructure setup)

### Phase Ordering Rationale

1. **CI first** (Phase 1): Zero code dependency on anything else. Every later phase is only verifiable once CI gate exists.
2. **Correctness safety-net second** (Phase 2): Golden files are the regression detector for all downstream work. Must exist before refactoring or any bug fixes.
3. **Refactoring third** (Phase 3): Only safe after golden-file coverage exists. Splitting calculators.py is the highest-risk mechanical change and needs the safest regression net.
4. **Performance/Auth fourth** (Phase 4): Depends on Phase 2 (golden files catch N+1 data-shape regressions). Can parallelize N+1 work with IPCC caching with auth/rate-limiting work.

This order respects the Feature dependencies graph in FEATURES.md and the Integration Point build-order recommendations from ARCHITECTURE.md.

### Research Flags

Phases requiring deeper research during planning:
- **Phase 1 (CI)**: MEDIUM research needed - APP_MODE=test env var setup and .env.test loading should be verified against this codebase to ensure migrations run against the test DB, not a fallback SQLite.
- **Phase 2 (Correctness)**: LOW research needed - golden-file pattern is well-documented; cross-check audit-flagged values against excel_reference_version/ for ground truth.
- **Phase 3 (Refactoring)**: LOW research needed - re-export shim pattern is standard Python; risk is execution discipline, not missing information.
- **Phase 4 (Performance/Auth)**: MEDIUM research needed - App Engine Standard -w 4 worker count, autoscaling behavior, and Memorystore/Redis configuration should be confirmed against current app.yaml; DRF NUM_PROXIES setup needs verification against live App Engine request headers.

Phases with standard patterns (skip research-phase):
- All four phases use well-established patterns once the Phase 1 and Phase 4 GCP/App Engine specifics are confirmed.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| **Stack** | HIGH | All technologies verified against official PyPI/docs. Version compatibility verified. GitHub Actions Postgres pattern is standard community consensus, cross-checked across multiple sources. |
| **Features** | MEDIUM-HIGH | Feature list grounded directly in CONCERNS.md audit (primary source, site-specific evidence). Dependencies graph verified by reading and cross-referencing code. MVP definition matches PROJECT.md's Active requirements. |
| **Architecture** | HIGH | Existing four-layer design is documented in `.planning/codebase/ARCHITECTURE.md` (primary source, refreshed 2026-07-08). Integration points mapped directly to code locations. Build order grounded in actual file dependencies and Django patterns. |
| **Pitfalls** | MEDIUM | Nine pitfalls derived from CONCERNS.md + TESTING.md audit + official Django/DRF/App Engine documentation + community sources. Each pitfall has prevention/recovery strategies with rationale. Some App Engine rate-limiting specifics should be confirmed during Phase 1 planning. |

**Overall confidence:** MEDIUM-HIGH

The recommendation is sound and execution-ready for phases 1-3. Phase 4 has higher execution risk around App Engine infrastructure setup but the mitigation strategies are clear. No unknown unknowns identified; all dependencies are understood.

### Gaps to Address

1. **Confirm APP_MODE=test env var and .env.test loading in CI context** (Phase 1 planning): CI job must set APP_MODE=test before invoking pytest, and migrations must run against the correct test database. Documented in CLAUDE.md but should be verified during Phase 1 execution.

2. **Cross-check audit-flagged golden-file values against excel_reference_version/ mirror** (Phase 2 execution): The three fragile calculator paths should have expected golden-file values validated against the `excel_reference_version/` codebase mirror mentioned in CLAUDE.md.

3. **Verify App Engine runtime environment for Phase 4** (rate limiting plus caching): The current app.yaml and gcp-deployment/ configs should be reviewed during Phase 4 planning to confirm gunicorn worker count, autoscaling configuration, Memorystore/Redis availability, and the actual X-Forwarded-For header proxy chain.

4. **Determine which calculator domain to split first in Phase 3**: ARCHITECTURE.md recommends "whichever has golden coverage first" but PROJECT.md lists "land module calculators" as the starting point. Phase 2 execution will determine this.

5. **Clarify the three tier-2 bug fixes: are they all fixable, or do some need to be "guarded"?** (Phase 2 planning): For aquaculture electricity and peat conversion, the intent is clear (these are bugs). For forestry start-value reuse, the CONCERNS.md audit should be reviewed to understand whether this is a bug or a documented fallback.

## Sources

### Primary (HIGH confidence)

- `.planning/codebase/ARCHITECTURE.md` (2026-07-08) - four-layer design, integration points, build order
- `.planning/codebase/CONCERNS.md` (2026-07-08) - known bugs with file/line references, fragile areas, caching/N+1 gaps
- `.planning/PROJECT.md` (2026-07-08) - milestone scope, constraints, existing tech stack
- Django official documentation (via Context7) - System checks framework, Databases, REST Framework throttling

### Secondary (MEDIUM confidence)

- Context7: `/pytest-dev/pytest-django`, `/syrupy-project/syrupy`, `/encode/django-rest-framework`, `/websites/djangoproject_en_5_2`
- Community sources on GitHub Actions + Django + Postgres CI - service container setup, fixture loading patterns
- PyPI JSON API - exact version numbers verified 2026-07-08
- PyCQA/bandit, pypa/pip-audit repositories - configuration patterns

### Tertiary (LOW confidence, pattern-level)

- Web search: django-zeal maintenance status (should be verified before Phase 4 execution)
- Web search: firebase-admin-python test suite mocking (should be tested against exact pinned version)
- Web search: App Engine Standard rate limiting patterns (should be confirmed against current app.yaml)
- Community discussion: floating-point tolerance conventions (1e-6 is a starting point; exact tolerance per path should be empirical)

---

*Research completed: 2026-07-08*
*Ready for roadmap creation: yes*
