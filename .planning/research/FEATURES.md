# Feature Research

**Domain:** Brownfield reliability/security/maintainability hardening for a Django 5.2 + DRF GHG-calculation API (EX-ACT)
**Researched:** 2026-07-08
**Confidence:** MEDIUM

Note: `.planning/codebase/CONCERNS.md` was referenced in PROJECT.md as the source audit but does not exist in this checkout (`.planning/codebase/` is empty). This research is grounded instead directly against the current code (`djangoexact/api/calculators.py`, `djangoexact/accounts/firebase.py`, `djangoexact/accounts/firebase_auth.py`, `djangoexact/accounts/views.py`, `djangoexact/djangoexact/settings.py`, `.github/workflows/deploy.yaml`) plus the nine target features already scoped in PROJECT.md's Active requirements, cross-checked against DRF/Django docs and general web sources. Treat feature-specific line numbers below as verified against the live repo on 2026-07-08; treat external "done right" claims as MEDIUM/LOW per source below.

## Feature Landscape

### Table Stakes (must have for the milestone to count as hardened)

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| CI runs pytest and blocks deploy on failure | The single `.github/workflows/deploy.yaml` job installs deps and deploys straight to App Engine with zero test/lint gate; a broken migration or serializer regression ships automatically. This is the most basic expectation of a "hardened" pipeline. | MEDIUM | Needs a Postgres service container (or cloud-sql-proxy against a throwaway DB) since the suite is Django `TestCase`/`APITestCase`, not sqlite-friendly `pytest-django`. Split into a separate `test` job; `deploy` gets `needs: [test]`. |
| CI runs bandit + pip-audit and blocks deploy on high-severity findings | `bandit -r djangoexact` and `pip-audit -r requirements.txt` are already documented as pre-PR expectations in CLAUDE.md but nothing enforces them. Both tools are cheap (seconds) and catch classes of bugs (hardcoded secrets, known CVEs in pinned deps) unrelated to functional tests. | LOW | Run as one combined step in the same `test` job (see GitHub Actions gating pattern below) so a single `needs:` edge protects deploy. Threshold to HIGH severity only, to avoid noisy low-severity findings blocking every deploy (matches `security_block_on: "high"` already set in `.planning/config.json`). |
| Fail-fast scenario input validation in `BaseCalculator` | Calculators currently rely on the math layer to blow up with a raw `KeyError`/`TypeError`/`AttributeError` stack trace when a required field is missing for one of the three scenarios (start/with/without), which is opaque to API clients and to whoever is debugging a 500 in production. | MEDIUM | Validate at the adapter layer (`api/calculators.py`), before calling into `math_model`, so the failure mode is a clear `ValidationError`/`ValueError` naming the missing field and the scenario it was missing for. Must run identically for all three scenarios, since a field can be present in `start` but missing in `with`/`without` (the exact bug class the audit flags). |
| Golden-file tests for the fragile calculation paths | The calculators.py module (8,270 lines) computes real GHG numbers used in FAO project appraisals; the CHANGELOG's repeated post-release fixes to `ActivityBuilderSerializer`, forest-management biomass matrices, and the three-scenario pipeline show these paths regress silently without a numeric baseline. | MEDIUM-HIGH | Golden files must be a means, not the mission: cover the three areas PROJECT.md flags (value chains energy+refrigerants, flooded-rice minor seasons with tier-2 overrides, forest-management biomass matrices), not every calculator. Snapshot `MathResult` output per scenario at TOTAL/ACTIVITY/GAS/ACTIVITY_GAS granularity, compared with `pytest.approx` (relative tolerance, not absolute) rather than exact float equality. |
| Fix (or explicitly guard) the three named tier-2 fallback bugs | PROJECT.md names these as known: aquaculture electricity default of 0, peat conversion factors, forestry start-value reuse across scenarios. These are correctness bugs already identified, not open-ended research. | MEDIUM | Each fix needs a golden-file regression test asserting the corrected behavior, written before or alongside the fix (see Dependencies). "Guard" is an acceptable substitute for "fix" only if the guard raises a loud validation error rather than silently defaulting. |
| Firebase auth sync integration tests | `FirebaseAuthentication.authenticate_credentials` (`accounts/firebase.py:28-38`) does `User.objects.get(firebase_uid=uid)` with no `DoesNotExist` handling of its own, falling through to a bare `except Exception as e: raise exceptions.AuthenticationFailed(str(e))` — this leaks whatever Django's ORM exception message says and gives every failure mode (expired token, no matching user, malformed header) the same generic 401 shape. Registration (`accounts/views.py:74-87`) creates the Firebase user first, then the local DB row, and rolls back by deleting the Firebase user on DB failure — a window where Firebase and Postgres can diverge. | MEDIUM-HIGH | Minimum test matrix: (1) valid Firebase token, no matching `firebase_uid` locally (UID mismatch/orphaned Firebase account), (2) Firebase email changed after local user created (local `CustomUser.email` now stale vs Firebase's), (3) two concurrent registration/login requests for the same email racing to create the Firebase user and/or local row. Use `unittest.mock` to fake `firebase_admin.auth.verify_id_token` / `create_user` rather than hitting real Firebase in CI. |
| Rate limiting on auth endpoints | `FirebaseAuthentication.authenticate` explicitly whitelists `/api/accounts/register/`, `/api/accounts/login/`, `/api/accounts/token/refresh/`, and `/api/accounts/password-reset/` as unauthenticated (`accounts/firebase.py:15`) — these are exactly the endpoints an attacker would brute-force, and they currently only get the blanket global `AnonRateThrottle` (`60/min`) configured in `settings.py:243-250`, not a tighter auth-specific limit. | LOW-MEDIUM | DRF's `ScopedRateThrottle` is the standard fit: give `LoginView`/`RegisterView`/`PasswordResetView` a `throttle_scope = "auth"` and a much tighter `DEFAULT_THROTTLE_RATES["auth"]` (e.g. `5/min`) than the global anon rate, keyed per IP since these requests are pre-authentication. |
| Deploy-time production config sanity checks | `settings.py` already computes `DEBUG` and `CORS_ALLOWED_ORIGINS` correctly (`DEBUG = os.getenv(...)`, `CORS_ORIGIN_ALLOW_ALL = DEBUG`, explicit allowlist parsed at `settings.py:57-59`) and already fails fast on missing `SECRET_KEY` when `DEBUG=False` (`settings.py:44-52`) -- but nothing currently asserts the *combination* (DEBUG=False AND CORS allowlist non-empty) before/during deploy for the production environment specifically. | LOW | A Django system check (`django.core.checks`) or a `manage.py check --deploy`-style custom check that raises if `APP_MODE == "production"` and (`DEBUG is True` or `CORS_ALLOWED_ORIGINS == []`) is the idiomatic Django mechanism; wire it into the CI `test`/`deploy` job so it runs against the templated settings before `python manage.py migrate` executes. |
| N+1 elimination on project/activity retrieval | Standard DRF nested-router serialization over related querysets (projects -> activities -> results) is the textbook N+1 trap; PROJECT.md flags this explicitly as a known gap. | LOW-MEDIUM | `select_related` for FK chains, `prefetch_related` for reverse FK/M2M, applied at the ViewSet `get_queryset()` level so it is not accidentally bypassed by serializer-level lazy access. |
| Query-count regression tests for the fixed N+1 paths | Fixing N+1 without a regression test means the next unrelated serializer change silently reintroduces it. | LOW | `self.assertNumQueries(N)` (Django `TestCase`, already available without pytest-django) around the exact ViewSet action, asserting a **constant** count as the number of related objects grows (create 1 vs 5 activities in the fixture, same query count expected) rather than just "fewer than before." |
| Immutable IPCC reference-table caching | IPCC tables are loaded once via fixtures and never change at runtime (`load_reference_data`/`dump_reference_data` round-trip, PK-stability guarded) -- repeated per-request DB round-trips for the same static lookup rows are pure waste. | LOW-MEDIUM | Module-level `functools.lru_cache` on the lookup functions (or a lazily-populated dict keyed by the natural key used in calculators) is the right tool, not Django's cross-process cache framework — App Engine Standard/gunicorn workers are separate processes anyway, `LocMemCache` would just duplicate the same per-process behavior with more moving parts, and the data only changes on a fixture reload that already requires a process restart. |
| Calculators.py decomposition, phase 1 (land module calculators split out) | An 8,270-line single file is the textbook "god object": every unrelated calculator change touches a file no reviewer can hold in their head, and `CalculatorFactory`'s dispatch logic is buried inside it. | HIGH | Must be preceded by golden-file coverage of the calculators being moved (see Dependencies) so a pure move-and-import-fix can be verified byte-for-byte against pre-refactor output. Backward-compatible re-export shims (`from api.calculators_land import AnnualCroplandCalculator` re-exported from the old `calculators.py` path) are required so nothing outside the module that imports `api.calculators.X` breaks mid-migration. |

### Differentiators (worth doing if cheap, not required to call the milestone done)

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| `ScenarioType` enum replacing `"start_w"`/`"start_wo"`/`"w"`/`"wo"` string literals | Removes an entire class of typo bugs in the three-scenario pipeline and makes `mypy`/IDE completion catch mismatches that string literals can't. | MEDIUM | Best done incrementally: introduce the enum, have it `str`-subclass (`class ScenarioType(str, Enum)`) so existing string comparisons and serialization keep working during the transition, then migrate call sites file by file. Natural companion to the calculators.py split (same files being touched anyway). |
| Combined bandit+pip-audit CI job with a single PR-comment/summary report | Cheap incremental polish once the gate exists: instead of a bare pass/fail, surface findings inline (e.g. patterns from `developmentseed/action-python-security-auditing`) so a failing PR shows *what* failed without digging into raw logs. | LOW | Purely a DX improvement on top of the table-stakes gate; do not build a custom reporting pipeline, use an existing composite action or plain `--format` flags feeding into the job summary. |
| Scattered TODO/FIXME migration into the issue tracker | Improves discoverability of known gaps but has zero effect on reliability/security/correctness by itself. | LOW | Mechanical: `grep -rn "TODO\|FIXME"`, file one issue per cluster (not one per occurrence), then delete or annotate the comment with the issue link. Do this last, after the higher-value clusters, since it is pure bookkeeping. |
| Full `calculators.py` decomposition (all six domains: land / livestock / aquaculture / energy / value chains / forest) | PROJECT.md only commits to "begun, starting with" the split — completing every domain in this milestone is a stretch goal, not a requirement. | HIGH | Sequence by churn/fragility: land and value-chains first (already flagged as needing golden tests anyway), aquaculture/energy/forest can follow in a later milestone if time runs out. Splitting more of it in this milestone is fine but should not block shipping the other eight features. |
| Firebase Admin SDK direct-usage cleanup (removing the custom `FirebaseAuth` REST wrapper in `accounts/firebase.py`) | The wrapper duplicates Firebase Admin SDK functionality via raw REST calls (`sign_in_with_email_and_password`, `refresh`, `delete_user_account`) — a maintenance burden and a place bugs hide. | HIGH | PROJECT.md explicitly defers this to a future milestone ("audit as part of auth tests, but full migration... is a future milestone"). Only in scope here as far as the integration *tests* covering current behavior; do not refactor the wrapper itself this milestone. |
| Structured logging/metrics around calculator validation failures | Once fail-fast validation exists, emitting a structured log line (activity id, scenario, missing field) on every validation rejection gives ops visibility into how often bad input reaches the API versus a client bug. | LOW | Nice instrumentation on top of validation; not required for the validation feature itself to be "done." |

### Anti-Features (commonly requested, deliberately out of scope for this milestone)

| Feature | Why Requested | Why Problematic Here | Alternative |
|---------|---------------|-----------------------|-------------|
| Mandating a global test-coverage percentage (e.g. "80% coverage") as a CI gate | Coverage numbers feel like an objective, easy-to-enforce quality bar. | Coverage percentage says nothing about whether the *fragile, audit-flagged* paths (value chains, flooded rice, forest management) are covered; a team can hit 80% by testing trivial serializers while the actual risk area (three-scenario calculator pipeline) stays untested. Also risks becoming a second, competing gate alongside the golden-file tests, adding CI time without adding confidence. | Target golden-file/regression coverage explicitly at the fragile paths named in PROJECT.md; let coverage be observational, not a blocking gate. |
| Splitting the single Postgres database into per-app databases now that `AppSpecificDatabaseRouter` scaffolding exists | The routers are already there, looking "ready to use." | PROJECT.md explicitly puts this Out of Scope ("Completing the DB-router split... single-DB model retained until multi-tenancy is actually needed"). No current requirement forces it, and it is a large, risky change orthogonal to hardening. | Leave the routers as scaffolding; revisit only when multi-tenancy becomes an actual requirement. |
| Rewriting `FirebaseAuthentication`/`FirebaseAuth` wholesale as part of "hardening the auth flow" | Adding integration tests naturally surfaces how ugly the current exception handling and REST wrapper are, tempting a full rewrite while already in the file. | PROJECT.md explicitly scopes this milestone to *tests* for the sync behavior, deferring "Firebase custom-wrapper replacement" to a future milestone; a rewrite here risks breaking the live auth flow the WebApp depends on with no corresponding spec/plan for it. | Fix the specific leaky-exception bug if it is trivial and covered by the new tests (e.g. catch `CustomUser.DoesNotExist` explicitly and return a clean 401), but do not restructure the wrapper's public shape. |
| A distributed cache (Redis/Memcached) for IPCC reference data "to be scalable" | Reference-data caching often defaults people to reaching for a shared cache backend because that is the "proper" production pattern. | The data is genuinely immutable within a process's lifetime and small; introducing a new infra dependency (Redis/Memcached instance, connection config, invalidation logic) adds operational surface area with no corresponding benefit over `lru_cache`, and Django's own docs flag `LocMemCache` (the in-process analog) as unsuitable for cross-process needs precisely because App Engine/gunicorn workers don't share memory anyway — a distributed cache only pays off if the data needs cross-process invalidation, which static fixture data does not. | Module-level `lru_cache` per worker process; if reference data ever becomes dynamically editable at runtime, revisit then. |
| Big-bang rewrite of `calculators.py` into a plugin/strategy-pattern architecture | Once inside an 8k-line file, it's tempting to "do it properly" with a fully pluggable calculator registry, dependency injection, etc. | High risk of introducing behavior changes in FAO's live emissions numbers with no corresponding spec; PROJECT.md's constraint is explicit that "calculation results for currently-correct paths must not change." A structural rewrite is much harder to verify byte-for-byte against golden files than a pure module split. | Mechanical decomposition only: move classes into domain-named modules, keep `CalculatorFactory` dispatch logic and class internals unchanged, re-export from the old path for compatibility. |
| Retrofitting `pytest-django` fixtures/plugin wholesale to replace Django `TestCase`/`APITestCase` | pytest-django's fixtures (`db`, `client`, `django_assert_num_queries`) are more ergonomic than `TestCase` boilerplate. | CLAUDE.md and PROJECT.md are explicit: `pytest-django` is not installed, and the existing suite bootstraps Django via `TestCase`/`APITestCase` classes; swapping the test runner mid-hardening-milestone is an unrelated, large-blast-radius change that risks breaking hundreds of existing tests for no correctness/security benefit. | Use `self.assertNumQueries(...)` (built into Django's own `TestCase`), not `django_assert_num_queries`; keep golden-file tests as plain `TestCase`/`APITestCase` subclasses consistent with the existing suite. |

## Feature Dependencies

```
[Golden-file tests for fragile calculators]
    └──must precede──> [calculators.py decomposition]
                            (a pure move is only verifiable if pre-refactor
                             numeric output is already pinned)

[Golden-file tests for fragile calculators]
    └──must precede or accompany──> [Fix tier-2 fallback bugs]
                            (aquaculture electricity default, peat factors,
                             forestry start-value reuse — write the test
                             capturing WRONG behavior first, then fix, then
                             assert CORRECT behavior, so the fix is provably
                             a fix and not a silent behavior change)

[Fail-fast scenario validation in BaseCalculator]
    └──enhances──> [Golden-file tests]
                            (validation turns "silent wrong number" failure
                             modes into loud errors that golden tests can't
                             accidentally mask; do validation first so golden
                             tests assert against clean inputs, not garbage-in)

[CI runs pytest]
    └──requires──> [Postgres available in CI]
                            (no pytest-django/sqlite fallback; suite needs a
                             real or cloud-sql-proxy'd Postgres instance)

[CI runs pytest, bandit, pip-audit]
    └──requires──> [Deploy job gated via `needs:`]
                            (the test job existing is necessary but not
                             sufficient — deploy.yaml must also be edited to
                             depend on it, or the gate does nothing)

[Production config sanity check]
    └──enhances──> [CI deploy gate]
                            (natural to run as an additional CI/deploy-time
                             check right alongside the pytest/bandit/pip-audit
                             gate, same `needs:` wiring)

[ScenarioType enum]
    └──enhances──> [calculators.py decomposition]
                            (touching every calculator file to move it is a
                             natural moment to also replace scenario string
                             literals with the enum; doing both separately
                             means touching the same files twice)

[N+1 elimination]
    └──requires──> [Query-count regression test]
                            (a fix without assertNumQueries is not "done" —
                             it will silently regress on the next serializer
                             change with no signal)

[Firebase auth sync integration tests]
    └──independent of──> [Rate limiting on auth endpoints]
                            (both touch accounts/ views but are orthogonal:
                             one is about correctness of UID/email sync, the
                             other is about request-volume defense; can ship
                             in either order or in parallel)

[IPCC reference-table caching]
    └──independent of──> [everything else]
                            (contained to ipcc/ app lookups, no ordering
                             constraint with the other eight features)
```

### Dependency Notes

- **Golden-file tests must precede calculators.py decomposition:** the whole point of golden files here is to let a mechanical file-split be verified as behavior-preserving. Splitting first and testing after means any bug introduced during the move (a missed import, a subtly different `CalculatorFactory` registration) has no baseline to be caught against.
- **Golden-file tests must precede or accompany the three named tier-2 bug fixes:** the audit already knows these are wrong (aquaculture electricity defaulting to 0, peat conversion factors, forestry start-value reuse across scenarios). Writing the golden test first, confirming it captures the *current* (wrong) output, then changing the code and confirming the test now captures *correct* output, is the only way to prove the fix actually changed what it was supposed to and nothing else.
- **Fail-fast validation should land before or alongside golden-file tests, not after:** if validation ships after golden files are written, the golden files may have been fixture-fed with silently-defaulted garbage values (e.g. the aquaculture electricity=0 bug) baked into the "expected" snapshot, then re-baselining every golden file when validation later rejects that same input.
- **CI test job must exist before the deploy gate can reference it:** trivial but often gets sequenced backward in practice — the `needs:` edit to `deploy.yaml` is a one-line change but is only meaningful once a `test` job producing a real pass/fail exists.
- **N+1 fixes need their regression test in the same commit/PR, not a follow-up:** an unguarded fix is not "hardening," it is a one-time cleanup that will regress silently.
- **Firebase auth sync tests and auth rate limiting are independent and can be parallelized** across two different contributors/PRs without conflict, since they touch different concerns (correctness of the UID/email sync path vs. `throttle_scope` additions to the same views).
- **IPCC caching has no dependency on any other feature** and is the lowest-risk, most isolated item in this milestone -- good candidate to ship first or in parallel while the calculators.py work is being planned.

## MVP Definition (this milestone's "done")

### Must Ship (all nine target features, table-stakes items only)

- [ ] CI test job (pytest against a real/proxied Postgres) blocking the existing deploy job via `needs:`
- [ ] CI bandit + pip-audit step (HIGH-severity threshold) in the same gated job
- [ ] `BaseCalculator` scenario-level validation raising a named, field-specific error for start/with/without
- [ ] Golden-file tests for value chains (energy + refrigerants), flooded-rice minor seasons (tier-2 overrides), forest-management biomass matrices
- [ ] The three named tier-2 fallback bugs fixed or explicitly guarded, each with a regression test
- [ ] Firebase auth sync integration tests: UID mismatch, email change, concurrent auth events
- [ ] `ScopedRateThrottle` (or equivalent) on register/login/password-reset/token-refresh with a tighter-than-global rate
- [ ] Deploy-time (or CI-time) assertion that production config has `DEBUG=False` and non-empty `CORS_ALLOWED_ORIGINS`
- [ ] `select_related`/`prefetch_related` applied to project/activity retrieval ViewSets, each with an `assertNumQueries` regression test
- [ ] Module-level `lru_cache` (or equivalent) on IPCC reference-table lookups
- [ ] calculators.py decomposition "begun" -- at minimum the land-module calculators (or value-chains, whichever has golden coverage first) split into a separate module with a backward-compatible re-export shim

### Add If Time Allows (differentiators)

- [ ] `ScenarioType` enum replacing scenario string literals, scoped to whichever calculator files are already being touched for the decomposition
- [ ] Combined bandit+pip-audit job summary/PR-comment reporting
- [ ] Additional calculators.py domains split beyond the first (livestock / aquaculture / energy / forest)

### Explicitly Deferred (do not attempt this milestone)

- [ ] Global test-coverage percentage gate
- [ ] DB-router multi-tenancy split
- [ ] Firebase custom-wrapper (`accounts/firebase.py`) replacement with plain Admin SDK
- [ ] Distributed cache (Redis/Memcached) for reference data
- [ ] Full plugin/strategy-pattern rewrite of the calculator architecture
- [ ] Migrating the test suite off `TestCase`/`APITestCase` onto `pytest-django`
- [ ] TODO/FIXME-to-issue-tracker migration (do last if time remains; zero reliability/security value)

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| CI pytest + bandit + pip-audit deploy gate | HIGH | MEDIUM | P1 |
| Fail-fast scenario validation | HIGH | MEDIUM | P1 |
| Golden-file tests (3 fragile paths) | HIGH | MEDIUM-HIGH | P1 |
| Fix 3 named tier-2 bugs | HIGH | MEDIUM | P1 |
| Firebase auth sync integration tests | HIGH | MEDIUM-HIGH | P1 |
| Rate limiting on auth endpoints | MEDIUM | LOW | P1 |
| Production config sanity check | MEDIUM | LOW | P1 |
| N+1 elimination + query-count tests | MEDIUM | LOW-MEDIUM | P1 |
| IPCC reference-data caching | LOW-MEDIUM | LOW-MEDIUM | P1 |
| calculators.py decomposition (phase 1) | MEDIUM | HIGH | P1 |
| ScenarioType enum | MEDIUM | MEDIUM | P2 |
| Combined security-scan reporting | LOW | LOW | P2 |
| Further calculators.py decomposition | LOW-MEDIUM | HIGH | P2/P3 |
| TODO/FIXME migration to issue tracker | LOW | LOW | P3 |

**Priority key:**
- P1: Must have -- this is what "hardened" means for this milestone
- P2: Should have, add when the P1 work in the same file/area is already done
- P3: Nice to have, defer without regret

## Acceptance Criteria a Verifier Could Check (per feature)

1. **CI deploy gate:** `.github/workflows/deploy.yaml`'s `deploy` job has a `needs:` entry referencing a `test` (or similarly named) job; that job runs `pytest`, `bandit -r djangoexact -x djangoexact/venv,djangoexact/node_modules`, and `pip-audit -r djangoexact/requirements.txt`; a deliberately broken test/lint/dependency triggers a failed CI run with the deploy job never starting.
2. **Fail-fast validation:** feeding a scenario dict missing a required field (for any of start/with/without) to a calculator raises a `ValidationError`/`ValueError` naming the missing field and scenario, before any `math_model` function is called; verified by a unit test per calculator category that omits one required field at a time.
3. **Golden-file tests:** for each of the three named fragile paths, a fixture-driven test asserts the full `MathResult` output (TOTAL/ACTIVITY/GAS/ACTIVITY_GAS, all three scenarios) against a checked-in expected value using `pytest.approx` with an explicit relative tolerance; changing any input to the golden fixture without updating the golden file makes the test fail.
4. **Tier-2 bug fixes:** each of the three named bugs (aquaculture electricity default, peat conversion factors, forestry start-value reuse) has a test that fails against the pre-fix code and passes against the post-fix code; the fix does not change output for any other, unrelated calculator's golden-file test.
5. **Firebase auth sync tests:** three tests exist and pass: (a) valid signed token with a `uid` that has no matching `CustomUser.firebase_uid` returns a 401 with a message that does not leak an internal exception string; (b) a user whose Firebase email differs from the local `CustomUser.email` is still authenticated by UID, and there is an assertion about whether/how the mismatch is surfaced; (c) two near-simultaneous registration calls for the same email do not leave a Firebase user with no corresponding local row (or the rollback path is exercised and asserted).
6. **Rate limiting:** a test hitting the login (or password-reset) endpoint more than the configured `auth` scope rate returns HTTP 429; the global anon/user throttle rates in `settings.py` remain unchanged for non-auth endpoints.
7. **Production config sanity check:** a Django system check (or equivalent) fails startup/deploy when `APP_MODE == "production"` and either `DEBUG is True` or `CORS_ALLOWED_ORIGINS` is empty; a test simulates production env vars and asserts the check raises.
8. **N+1 elimination:** `self.assertNumQueries(N)` around the project-list and activity-list ViewSet actions passes with a constant `N` regardless of whether the fixture has 1 or 5 activities/results.
9. **IPCC caching:** a test asserts that two calls to the cached lookup function return the same object (or that a DB-query counter shows only one query across repeated calls within a process); no test asserts cross-process cache sharing, since that is explicitly not the design.
10. **calculators.py decomposition:** `import api.calculators` still exposes every previously-public calculator class name (re-export shim); `python -c "from api.calculators import AnnualCroplandCalculator"` (or whichever calculators moved) succeeds unchanged; the new domain module's calculators pass the same golden-file tests as before the move with zero changes to expected values.

## Sources

- [.planning/PROJECT.md](file:///home/sirvosterzo/Developer/FAO/EXACT/exact-django-webapp/.planning/PROJECT.md) -- milestone scope, active requirements, constraints (primary source; `.planning/codebase/CONCERNS.md` referenced there does not exist in this checkout)
- Direct code inspection: `djangoexact/api/calculators.py` (8,270 lines, verified via `wc -l`), `djangoexact/accounts/firebase.py`, `djangoexact/accounts/firebase_auth.py`, `djangoexact/accounts/views.py`, `djangoexact/djangoexact/settings.py` (REST_FRAMEWORK, CORS, DEBUG blocks), `.github/workflows/deploy.yaml`, `djangoexact/requirements.txt` -- HIGH confidence (primary source, read directly)
- [Django REST Framework -- Throttling (ScopedRateThrottle)](https://github.com/encode/django-rest-framework/blob/main/docs/api-guide/throttling.md) via Context7 -- MEDIUM confidence
- [Django -- Cache framework (LocMemCache, low-level cache API, cached_property)](https://github.com/django/django/blob/main/docs/topics/cache.md) via Context7 -- MEDIUM confidence
- [Counting queries: basic performance testing in Django -- Vinta](https://www.vinta.com.br/blog/2020/counting-queries-basic-performance-testing-in-django/) -- LOW confidence (web search, not independently verified)
- [Automating Performance Testing in Django -- TestDriven.io](https://testdriven.io/blog/django-performance-testing/) -- LOW confidence
- [A Comprehensive Guide to Pytest Approx -- pytest-with-eric](https://pytest-with-eric.com/pytest-advanced/pytest-approx/) -- LOW confidence
- [Stop Flaky Float Tests with pytest.approx() -- CodeCut](https://codecut.ai/stop-flaky-float-tests-with-pytest-approx/) -- LOW confidence
- [action-python-security-auditing (bandit + pip-audit composite GitHub Action)](https://github.com/developmentseed/action-python-security-auditing) -- LOW confidence
- [pip-audit](https://github.com/pypa/pip-audit) -- LOW confidence
- [Firebase Authentication -- Verify ID Tokens (Admin SDK)](https://firebase.google.com/docs/auth/admin/verify-id-tokens) -- LOW confidence (not independently verified against current SDK version)

---
*Feature research for: Django/DRF backend hardening milestone (EX-ACT)*
*Researched: 2026-07-08*
