# Stack Research

**Domain:** Hardening an existing Django 5.2 / DRF 3.16 / Python 3.11 GHG calculator API (EX-ACT) for CI automation, correctness safety nets, auth/security, performance, and maintainability
**Researched:** 2026-07-08
**Confidence:** MEDIUM (library choices verified against current PyPI/official docs; exact GitHub Actions YAML and Firebase mock patterns are pattern-level, not project-tested, hence not HIGH)

## Recommended Stack

### Core Technologies

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| pytest-django | 4.12.0 | Bridges pytest and Django ORM/settings for the existing pytest 9.x suite | Adds `db`, `django_db_blocker`, and `django_assert_num_queries` fixtures without forcing a rewrite of existing `APITestCase`/`TestCase` classes. Its docs explicitly state pytest-django is compatible with standard Django test suites out of the box, so it layers on top rather than replacing anything. Requires only `pytest>=7.0.0`, so no conflict with pytest 9.0.3 already pinned. |
| GitHub Actions `postgres` service container | n/a (GH-hosted `postgres` Docker image, any recent tag e.g. `postgres:16`) | Provisions a real Postgres instance for the test job since local dev has no DB | This is the standard, zero-extra-cost way to get Postgres in GitHub Actions: declare a `services.postgres` block with `POSTGRES_PASSWORD`/`POSTGRES_DB` env vars, a `health-cmd: pg_isready` check, and `ports: ["5432:5432"]`; the job then talks to `127.0.0.1:5432`. No SQLite fallback is needed and none should be used, since production runs Postgres and SQLite silently hides Postgres-only bugs (JSONField queries, migrations, constraint behavior). |
| bandit | 1.9.4 | Static security linter, already used locally per README | Already a project convention; pin the version and move it into CI as a required job. Configure via `[tool.bandit]` in `pyproject.toml` (or keep the existing invocation flags) and gate on `-ll`/`-lll` (medium/high severity+confidence) in CI to avoid drowning the gate in low-confidence findings, while still running the full `-r djangoexact -x djangoexact/venv,djangoexact/node_modules` scan the README documents. |
| pip-audit | 2.10.1 | Dependency vulnerability scanning, already used locally per README | Use the official `pypa/gh-action-pip-audit` GitHub Action rather than hand-rolling a shell step; it exits non-zero on any known vulnerability by default (correct fail-closed behavior for a deploy gate) and supports `ignore-vulns` for specific CVEs the team has assessed and accepted, which is preferable to silencing the whole scan. |

### Supporting Libraries

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| syrupy | 5.5.2 | Golden-file/snapshot testing for numeric calculation pipelines | Use for the flagged fragile paths (value chains energy/refrigerants, flooded-rice minor seasons with tier-2 overrides, forest-management biomass matrices). Its `JSONSnapshotExtension` serializes the `MathResult`/scenario dicts the calculators already return into diffable `.json` snapshot files under `__snapshots__/`, and `path_type` matchers let you exclude non-deterministic fields (timestamps, PKs) from the comparison. Zero runtime dependencies, so it does not bloat `requirements.txt`. Prefer this over hand-rolled `json.dump`-and-diff scripts: syrupy gives you `pytest --snapshot-update` for reviewed, intentional updates and fails loudly (with a diff) on unreviewed drift, which a hand-rolled comparison would need to reimplement. |
| pytest.approx (built into pytest, no new dependency) | pytest 9.0.3 (already pinned) | Floating-point tolerance for the numeric assertions inside golden-file/unit tests | Do not assert exact float equality on emission totals; wrap expected numeric values in `pytest.approx(expected, rel=1e-6)` (or a looser `rel=1e-4` for values that pass through more accumulation steps, e.g. multi-scenario totals). Combine with syrupy for structural/shape snapshotting and `pytest.approx` for the tolerance-sensitive leaf values, since syrupy's own diff is exact-match by default. |
| django-zeal | 2.2.1 | N+1 query detection during tests and (optionally) in review deployments | Actively maintained, Django-specific fork lineage of the original `nplusone` (unmaintained since 2020). Raises on N+1 patterns (missing `select_related`/`prefetch_related`) including `.defer()`/`.only()` misuse, with configurable thresholds so it can be dropped into `TEST` settings only and left off in production. This is a better fit than the abandoned `nplusone` package or the newer `nplus1` rewrite (which targets multi-ORM/SQLAlchemy use cases the project does not have). |
| `django_assert_num_queries` (from pytest-django) | bundled with pytest-django 4.12.0 | Regression tests that pin exact query counts for hot paths (project/activity retrieval) | Add explicit `with django_assert_num_queries(N):` tests around the endpoints being fixed for N+1 (project list, activity detail) so a future regression fails CI immediately, not just when django-zeal happens to be enabled. This is the standard pytest-django idiom for query-count regression testing and needs no new dependency since it ships with pytest-django. |
| `unittest.mock.patch` on `firebase_admin.auth.verify_id_token` (stdlib, no new dependency) | Python 3.11 stdlib | Firebase auth integration tests (UID mismatch, email change, concurrent auth events) | The `firebase-admin-python` project's own test suite mocks HTTP calls to Google's public-key and token endpoints and patches `firebase_admin.auth.verify_id_token` directly rather than hitting real Firebase; apply the same pattern to `accounts.firebase.FirebaseAuthentication` so the new integration tests are deterministic, hermetic, and do not require live Firebase credentials in CI. Do not add a Firebase emulator or a mocking library like `firebase-mock` for this; the stdlib patch is sufficient for testing the DRF authentication class in isolation. |
| `django.core.checks` custom deploy checks (Django built-in, no new dependency) | Django 5.2.14 (already pinned) | Pre-deploy sanity check for `DEBUG=False` and non-empty `CORS_ALLOWED_ORIGINS` | Register checks with `@register(Tags.security, deploy=True)` in an `api/checks.py` (or similar) module, then run `python manage.py check --deploy --fail-level WARNING` as a required CI step before the App Engine deploy step in `deploy.yaml`. This reuses Django's own check framework instead of writing an ad hoc shell/grep script, and the checks are also usable locally by any developer running `--deploy`. |
| DRF `ScopedRateThrottle` (already available in installed `djangorestframework==3.16.1`, no new dependency) | 3.16.1 (already pinned) | Rate limiting on auth endpoints | The project's `REST_FRAMEWORK` settings already configure `AnonRateThrottle`/`UserRateThrottle` with `DEFAULT_THROTTLE_RATES`. Add `ScopedRateThrottle` to `DEFAULT_THROTTLE_CLASSES`, give the token-obtain/login views a `throttle_scope = "auth"`, and set a strict rate (e.g. `"auth": "5/min"`) in `DEFAULT_THROTTLE_RATES`. This is strictly additive to the existing throttle config and needs no new package. |

### Development Tools

| Tool | Purpose | Notes |
|------|---------|-------|
| GitHub Actions `services:` block (built into GitHub Actions, no marketplace Action needed) | Postgres provisioning for the pytest job | Add a `test` job (separate from the existing `deploy` job in `.github/workflows/deploy.yaml`) with `services: { postgres: { image: postgres:16, env: {POSTGRES_PASSWORD: postgres, POSTGRES_DB: exact_test}, ports: ["5432:5432"], options: --health-cmd=pg_isready --health-interval=10s --health-timeout=5s --health-retries=5 } }`. Point Django's `DATABASES` at `127.0.0.1:5432` via the existing `APP_MODE=test` / `.env.test` convention rather than hardcoding CI-only settings. |
| `needs:` job dependency graph (built into GitHub Actions) | Blocks deploy on test/bandit/pip-audit success | Structure `deploy.yaml` as parallel `test`, `bandit`, `pip-audit` jobs feeding a `deploy: needs: [test, bandit, pip-audit]` job. This is the standard GitHub Actions gating idiom (a job with `needs` only starts after every listed job succeeds) and requires no third-party gate action. Currently `deploy.yaml` has no such job at all, so this is the biggest structural change, not a library choice. |
| `pypa/gh-action-pip-audit` (GitHub Marketplace Action) | Wraps pip-audit invocation for the requirements.txt scan | Prefer the official `pypa` action over a hand-rolled `pip install pip-audit && pip-audit -r requirements.txt` step: it standardizes flag handling (`ignore-vulns`, `require-hashes`) and is maintained by the same org as `pip-audit` itself. |
| `factory-boy` (already pinned, 3.3.3, latest) | Test data construction for scenario-level validation and golden-file tests | Already in `requirements.txt` and used under `api/tests/factories.py`; no change needed, but new validation/golden-file tests should reuse the existing factories rather than hand-building model instances, to keep fixture drift from becoming its own maintenance burden. |

## Installation

```bash
# From djangoexact/ — add to requirements.txt (pin exact versions to match project convention)
pytest-django==4.12.0
syrupy==5.5.2
django-zeal==2.2.1

# CI-only tools (not needed in requirements.txt if invoked via `pip install` in the workflow step,
# but pinning them in requirements.txt keeps local/CI bandit and pip-audit versions identical)
bandit==1.9.4
pip-audit==2.10.1

pip install -r requirements.txt
```

No `npm install` changes are needed; none of these hardening capabilities touch the webpack/frontend asset pipeline.

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| Keep Django `TestCase`/`APITestCase` as the base for existing tests, add pytest-django only for new fixtures | Migrate the whole suite to pure pytest style (plain `def test_x():` functions with fixtures) | Only worth it if the team commits to a multi-sprint rewrite; the constraint explicitly says no pytest-django was chosen for a reason (no DB locally), and a full migration is unnecessary churn against a stated goal of not touching working code. Layering pytest-django under the existing classes gets the query-count and fixture benefits with zero rewrite risk. |
| syrupy for golden-file/snapshot tests | Hand-rolled `json.dump(expected, open(...))` + manual diffing script | Only if the team wants zero new dependencies at all costs; hand-rolling forfeits `--snapshot-update`, matcher-based field exclusion, and readable diffs, all of which syrupy provides for a zero-runtime-dependency package. Not recommended here. |
| syrupy for structural snapshots + `pytest.approx` for float tolerance | `pytest-regressions` (`num_regression`, `data_regression`) | `pytest-regressions` is also a credible choice for this exact use case (it directly supports tolerance-aware numeric regression via `num_regression.check(..., default_tolerance=...)`) and could replace syrupy if the team prefers a testing-focused package over a snapshot-focused one. Either is reasonable; syrupy is recommended here for its broader adoption and JSON-native format, which maps cleanly onto the `MathResult`/scenario dict shapes already in the codebase. |
| DRF `ScopedRateThrottle` for auth-endpoint rate limiting | `django-ratelimit` 4.1.0 | Use `django-ratelimit` only if a rate limit is needed on a non-DRF view (e.g. a plain Django view or admin action) since DRF throttling only applies inside DRF's request/response cycle. All of this project's auth endpoints are DRF views (SimpleJWT token views, Firebase-backed viewsets), so the built-in scoped throttle is the fit; adding django-ratelimit alongside would mean maintaining two separate rate-limit configuration systems for no benefit. |
| django-zeal for N+1 detection | `nplus1` 1.1.5 | `nplus1` is a newer, actively maintained rewrite, but it targets multi-ORM support (SQLAlchemy, Peewee) that this Django-only codebase does not need; django-zeal is Django-specific and lighter to reason about. Consider `nplus1` only if the project later adds a second ORM/data layer. |
| django-zeal for N+1 detection | Original `nplusone` (jmcarp) | Do not use; unmaintained since 2020. Listed only to rule it out explicitly since it is what most search results and Stack Overflow answers still point to. |
| Django's low-level cache API (`cache.get_or_set`) with the default `LocMemCache` for IPCC reference-table caching | `django-cacheops` or Redis-backed caching | Only justified if reference-table lookups become a measured bottleneck across many workers/instances needing a shared cache, or if the team later introduces Redis for other reasons (e.g. Celery). For read-only, immutable IPCC defaults, per-process `LocMemCache` (or even a plain module-level `functools.lru_cache` wrapping the queryset-fetching function) is sufficient and adds no new infrastructure to an App Engine Standard deployment that does not currently run Redis/Memcached. |
| Official `pypa/gh-action-pip-audit` Action | Raw `pip install pip-audit && pip-audit -r requirements.txt` shell step | Equivalent in practice; the Action is preferred only for maintenance convenience (version pinning via Action tag, standardized `ignore-vulns` input) not because the raw shell command doesn't work. Either is acceptable; recommend the Action for consistency with how `bandit` may eventually get an Action wrapper too. |

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| Migrating the entire test suite off Django `TestCase`/`APITestCase` to pure pytest style | Explicit project constraint; large surface area for regressions in a codebase whose whole current risk profile is "silent numeric drift"; no functional benefit proportional to the risk for this milestone | pytest-django layered on top of the existing classes (see Core Technologies) |
| SQLite as a CI-only test database "for speed" | Production runs Postgres; SQLite diverges on JSONField queries, constraint enforcement, and migration behavior, which would make the new CI gate test against a different database engine than production, defeating the purpose of adding a safety net | GitHub Actions Postgres service container (matches Cloud SQL Postgres in production) |
| Original `nplusone` package | Unmaintained since 2020; will not track newer Django ORM internals | `django-zeal` 2.2.1 |
| `django-ratelimit` as the primary/only rate-limiting mechanism for a fully-DRF API | Duplicates throttling logic the project already has via DRF's `DEFAULT_THROTTLE_CLASSES`; two independent rate-limit systems is a maintenance and audit burden, and DRF throttling is explicitly documented as a usage-policy tool, not a brute-force defense, so neither alone is a complete security control | DRF `ScopedRateThrottle` for endpoint-specific limits; if genuine brute-force/DoS protection is required, that is an infrastructure-layer concern (e.g. Cloud Armor/App Engine firewall rules), not a library choice, and out of scope for this research |
| Exact float equality (`==`) in golden-file/snapshot assertions on emission totals | IEEE-754 accumulation differences across Python/NumPy versions or refactors will cause flaky, non-actionable test failures unrelated to real regressions | `pytest.approx(expected, rel=1e-6)` (or looser, tuned per calculation path) wrapped around the numeric leaves; syrupy for the surrounding structure |
| Hand-written regex/`sed`-based "DEBUG check" scripts in CI | Reimplements what Django's own check framework already does robustly, and does not compose with `manage.py check --deploy`'s existing security checks (secure cookies, `SECURE_HSTS_SECONDS`, etc.) that Django ships out of the box | `django.core.checks` custom deploy check + `python manage.py check --deploy` |
| Introducing Redis/Memcached solely to cache IPCC reference tables | Adds new infrastructure (a managed Redis instance, new App Engine/Cloud Run wiring, new failure mode) for data that is read-only and small enough to fit in per-process memory | Django `LocMemCache` via the low-level cache API, or a module-level `functools.lru_cache` |

## Stack Patterns by Variant

**If the team wants stricter brute-force protection on login beyond DRF throttling:**
- Treat it as an infrastructure-layer control (Cloud Armor rate-limiting rules in front of App Engine, or Google Cloud's built-in App Engine firewall) rather than adding another Python library.
- Because DRF's own docs describe its throttling as a usage-policy mechanism, not a security control; a determined attacker distributing requests across many source IPs defeats any in-process throttle regardless of which Python library implements it.

**If `calculators.py` decomposition later needs automated tooling rather than manual extraction:**
- Consider `libcst` (Meta's concrete syntax tree library) to script the extraction of classes into domain submodules while preserving imports/formatting, if the manual approach proves too error-prone for an 8,270-line file.
- Because manual extraction of 60+ calculator classes risks copy-paste errors and merge conflicts across a single milestone; `libcst`-based codemods can move classes and inject re-export shims mechanically. This is optional tooling, not a required dependency, and should only be reached for if the manual `__init__.py` re-export pattern proves unwieldy in practice.

## Version Compatibility

| Package A | Compatible With | Notes |
|-----------|-----------------|-------|
| pytest-django 4.12.0 | pytest 9.0.3 (already pinned) | pytest-django's own `requires_dist` only pins `pytest>=7.0.0`, no upper bound, so it is compatible with the project's already-installed pytest 9.x. |
| syrupy 5.5.2 | Python 3.11 (already pinned), pytest 9.0.3 | Requires Python `>=3.10`; zero runtime dependencies beyond pytest itself. |
| django-zeal 2.2.1 | Django 5.2.14, DRF 3.16.1 | Requires Python `>=3.9`; hooks Django's ORM signal/query layer, framework-agnostic to DRF vs plain Django views. |
| bandit 1.9.4 | Python 3.11 | Requires Python `>=3.10`; config via `[tool.bandit]` works even though this repo has no `pyproject.toml` for the app yet (a minimal `pyproject.toml` with just `[tool.bandit]` is sufficient, no build-system section required). |
| pip-audit 2.10.1 | pinned `requirements.txt` (no Poetry/lockfile) | Directly supports scanning a `requirements.txt` file (`pip-audit -r requirements.txt`); requires `>=3.10`. |
| DRF `ScopedRateThrottle` | djangorestframework 3.16.1 (already pinned) | No version change needed; feature has existed in DRF for many major versions and is present in 3.16.1. |
| Django custom deploy checks (`Tags.security`, `deploy=True`) | Django 5.2.14 (already pinned) | Stable Django API since early Django 1.x; no version risk. |

## Sources

- Context7 `/pytest-dev/pytest-django` — configuration and Django TestCase compatibility (MEDIUM confidence)
- Context7 `/syrupy-project/syrupy` — JSONSnapshotExtension, matchers, `--snapshot-update` (MEDIUM confidence)
- Context7 `/encode/django-rest-framework` — `ScopedRateThrottle` configuration (MEDIUM confidence)
- Context7 `/websites/djangoproject_en_5_2` — `django.core.checks` deploy checks, low-level cache API (MEDIUM confidence)
- PyPI JSON API (pytest-django, syrupy, bandit, pip-audit, django-zeal, nplus1, django-ratelimit, factory-boy) — exact current version numbers, verified directly (HIGH confidence for version numbers specifically)
- Web search: GitHub Actions + Postgres service container patterns (Simon Willison's TILs, Loopwerk, codingforentrepreneurs.com) — LOW confidence, pattern-level, not project-verified
- Web search: Bandit CI/pyproject.toml configuration (bandit.readthedocs.io, PyCQA/bandit) — LOW confidence
- Web search: `pypa/gh-action-pip-audit` behavior (github.com/pypa/pip-audit, github.com/pypa/gh-action-pip-audit) — LOW confidence
- Web search: django-zeal vs nplusone vs nplus1 maintenance status (github.com/taobojlen/django-zeal, github.com/huynguyengl99/nplus1) — LOW confidence
- Web search: firebase-admin-python test suite mocking patterns (github.com/firebase/firebase-admin-python) — LOW confidence
- Web search: Python module-to-package backward-compatible re-export pattern (testdriven.io) — LOW confidence
- Web search: `pytest.approx` tolerance semantics (docs.pytest.org, codecut.ai) — LOW confidence but cross-checked against pytest's own reference docs

---
*Stack research for: Django/DRF backend hardening (CI, correctness, security, performance, maintainability)*
*Researched: 2026-07-08*
