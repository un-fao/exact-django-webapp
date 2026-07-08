# Pitfalls Research

**Domain:** Hardening a live Django 5.2 + DRF GHG-calculation API (EX-ACT) - CI gates, calculator validation, golden-file tests, god-object refactor, rate limiting, reference-data caching, N+1 fixes
**Researched:** 2026-07-08
**Confidence:** MEDIUM (grounded in this repo's CONCERNS.md/TESTING.md audit plus cross-checked official docs and community sources for the App Engine, DRF, prefetch_related, and simple-history specifics)

## Critical Pitfalls

### Pitfall 1: CI gate ships red-herring green because it never ran against production-like data

**What goes wrong:**
The team wires pytest into GitHub Actions, it turns green on day one, and deploys keep flowing - but the suite silently skips everything that needs `load_reference_data` or a real Postgres connection, because CI defaults to SQLite and nobody set `APP_MODE=test` or provisioned the fixtures. Tests that pass locally (where the developer already has Postgres + loaded fixtures from months of local dev) fail or silently no-op in CI. The gate becomes theater: green build, unverified suite.

**Why it happens:**
This repo has no `pytest-django`, no `pytest.ini`, and no `conftest.py` - test discovery and Django bootstrap depend on which `TestCase` subclass is imported and on `.env.test` being loaded correctly. CI has never run pytest before (per `CONCERNS.md`: neither GitHub Actions nor Bitbucket runs it), so there is no prior evidence of what breaks when the suite runs somewhere other than a developer's machine, and reference-data loading takes 30+ seconds per the fixtures guide, an easy candidate for a timeout or "just skip it for speed" shortcut under CI time pressure.

**How to avoid:**
- Add a Postgres service container in CI (matching production's engine, not SQLite) and run `load_reference_data --app=all` as an explicit CI step, asserting its exit code and duration are logged.
- Run the full local suite once inside the CI container image manually before trusting the "green" result, and diff local vs CI failures - any CI-only pass on a test that fails locally against Postgres is a signal the CI DB config is fake.
- Fail the CI job (not just log a warning) if `test_reference_bootstrap.py`'s round-trip check fails, since that test is the canary for fixture/DB divergence.
- Gate merges on the same command documented in CLAUDE.md (`pytest` from `djangoexact/`), not a hand-rolled CI-only subset.

**Warning signs:**
- CI test run completes suspiciously fast (under 30 seconds total) - a sign fixtures never loaded.
- CI logs show `DJANGO_SETTINGS_MODULE` or `APP_MODE` warnings, or fall back to SQLite despite Postgres being intended.
- A previously-failing-locally test (e.g., one of the audit-flagged fragile paths) passes in CI without any code change.

**Phase to address:**
CI / test automation phase (must be the first phase - every other hardening phase depends on a trustworthy gate).

---

### Pitfall 2: SQLite-vs-Postgres behavioral drift hides in the "works in CI" result

**What goes wrong:**
If CI is configured with SQLite for speed (no Docker/Postgres needed), tests can pass while masking Postgres-only behavior: case-sensitivity differences in string matching (`__contains`/`__iexact`), lack of `ArrayField`/`HStoreField` support, whole-database write locking that hides concurrency bugs (relevant to `admin_scripts` job dispatch using `select_for_update()`), and JSONField requiring the JSON1 extension. A migration that mixes schema-altering operations with `RunPython` in one file can pass on SQLite but raise `OperationalError: cannot ALTER TABLE ... because it has pending trigger events` on Postgres.

**Why it happens:**
SQLite is the path of least resistance in a sandbox with no Docker (this repo's own constraints note "dev sandbox has no Postgres/Docker; the full suite runs only in CI or on DB-equipped machines"). It is tempting to let CI mirror that same shortcut for speed and simplicity, especially with no `pytest-django` layer smoothing over the differences.

**How to avoid:**
- CI must run against Postgres (the production engine), full stop - use a `postgres:` service container in GitHub Actions matching the production major version.
- Any migration that both alters schema and runs `RunPython` in the same file should be split into two migrations, verified against Postgres in CI, not just SQLite locally.
- If any test suite intentionally uses `SimpleTestCase` or SQLite-only speed tricks, document it explicitly as "no DB assertions here" so its pass/fail is not mistaken for reference-data correctness.

**Warning signs:**
- CI config file specifies `django.db.backends.sqlite3` while `settings.py`/`.env.production` specifies `postgresql`.
- select_for_update-based tests (`admin_scripts` job dispatcher) pass in CI but the underlying locking semantics were never exercised because SQLite serializes all writes anyway.

**Phase to address:**
CI / test automation phase.

---

### Pitfall 3: Fail-fast calculator validation breaks existing user projects that relied on lenient defaults

**What goes wrong:**
Adding upfront `ValidationError`s to `BaseCalculator` for "missing required fields" is exactly right for new data, but this codebase has documented, intentional lenient fallbacks already in production: `ELECTRICITY_USED_DEFAULT` hardcoded to 0 for aquaculture, peat conversion factors defaulting to 1, and forest-management tier-2 values silently reused across scenarios. If validation is added as a blanket "required field must be present" check without first classifying which fields are legitimately optional-with-a-known-default versus accidentally-missing, existing saved projects (created under the old lenient behavior) will start throwing 400/500s on retrieval or recalculation, even though nothing about the project's data changed. This is worse than the bug it's meant to fix: silently-wrong numbers become loudly-broken pages for real FAO users mid-appraisal.

**Why it happens:**
"Fail fast" is normally the right instinct, but on a brownfield system the same missing-field condition can mean two different things: a genuine data-entry gap (should fail) or a known category where a default has always stood in (should not suddenly fail). The validation layer cannot distinguish these without an explicit allowlist, because both look identical at the "field is None" check.

**How to avoid:**
- Before writing validation, enumerate the known lenient-default paths from `CONCERNS.md` (aquaculture electricity, peat conversion factors, flooded-rice tier-2 cultivation days, forestry cross-scenario reuse) and decide per-path: keep the default explicitly (with a comment and a test proving the default value), or fix the underlying data model so the field is never actually optional going forward.
- Implement validation as a pre-flight check that runs against a snapshot of currently-stored production-like project data (a fixture derived from real project shapes, not synthetic "everything filled in" test data) before enabling it as a hard failure, to catch anything not on the allowlist.
- Make validation errors return the same recoverable shape the frontend already handles (avoid changing the public API contract per the milestone's out-of-scope constraint) - a fail-fast validation error must still be a normal DRF `ValidationError` response, not a 500.
- Roll out as a warning/log-only mode first (log which projects would fail validation) before flipping to hard-fail, so the blast radius is known before it's enforced.

**Warning signs:**
- Any drop in successful `results` endpoint calls immediately after deploying validation, especially concentrated on aquaculture, flooded rice, forestry, or value-chain modules (the audit's flagged fragile paths).
- Support/bug reports referencing projects that "used to work."

**Phase to address:**
Correctness safety-net phase - but sequence the known-lenient-default audit (list every intentional default) as a discrete first step within that phase, before the validation itself is written.

---

### Pitfall 4: Golden-file tests assert exact floating-point equality and become permanently flaky or permanently stale

**What goes wrong:**
Golden-file tests for the math layer (value chains, flooded-rice tier-2 overrides, forest-management biomass matrices) get written comparing calculator output to a fixed expected value with `assertEqual`. Two failure modes follow: either the test is brittle and fails on innocuous platform/numpy-version differences (turning into a "just re-run CI" ritual that erodes trust in the gate), or - worse - a developer "fixes" the flakiness by loosening the fixture to match whatever the code currently outputs, silently baking in a wrong number as the new "golden" truth, defeating the entire purpose of the test.

**Why it happens:**
IEEE-754 floating point summation is not associative; different numpy/BLAS versions, different CPU architectures, or even different iteration order in a loop can produce bit-different results at the last few decimal digits. A test suite with no established tolerance convention will default to exact equality because it is the easiest thing to write first, and nobody notices the risk until CI is flaky in production.

**How to avoid:**
- Every golden-file assertion must use `assertAlmostEqual` (or a numpy-aware equivalent) with an explicit, documented tolerance chosen per quantity - not one global epsilon. Emissions totals in tonnes CO2e likely tolerate `1e-6` relative tolerance; per-activity fractional multipliers may need tighter bounds.
- Pin the `numpy`/`pandas` versions used to generate the golden files (already pinned in `requirements.txt` per repo convention) and note in the test file which library versions the fixture was generated against.
- Treat golden-file regeneration as a reviewed, diffed change (like the fixtures-guide's PK-stability guard for reference data) - never regenerate golden files as a "fix" for a failing CI run without a human comparing old vs new numbers and understanding why they moved.
- For the specifically audit-flagged paths (value chains energy/refrigerants, flooded-rice minor seasons, forest biomass matrices), cross-check golden values against the `excel_reference_version/` mirror mentioned in CLAUDE.md's architecture section, since that is the closest thing to independently-verified ground truth in this codebase.

**Warning signs:**
- A golden-file test fails intermittently in CI with no code change (classic sign of an over-tight tolerance or unpinned numpy).
- Git history shows repeated commits that only touch expected-value constants in test fixtures with no accompanying explanation of what the underlying calculation change was.

**Phase to address:**
Correctness safety-net phase.

---

### Pitfall 5: God-object refactor of calculators.py silently changes scenario dispatch behavior

**What goes wrong:**
Splitting the 8,270-line `calculators.py` by domain (land / livestock / aquaculture / energy / value chains) is the right move, but this file's core danger is exactly the thing that makes it hard to split safely: the three-scenario (`start`/`with`/`without`) pipeline has scattered conditional logic and hardcoded string comparisons ("start_w", "start_wo", "w", "wo") rather than one clean dispatch point. A mechanical "cut this class out, paste it in a new file" refactor can easily miss a shared helper function, a module-level constant, or an import-order dependency that only mattered because everything lived in one file - and the failure mode is not an import error (which CI would catch) but a silently different numeric result for one scenario combination, which only a golden-file test (not yet written for most paths) would catch.

**Why it happens:**
Large single-file modules accumulate implicit coupling: helper functions defined "for" one calculator get reused by another; module-level state (like the IPCC data-loading calls flagged as uncached in `CONCERNS.md`) gets instantiated once and shared; `CalculatorFactory`'s registration mapping is easy to miss updating when a class moves files. None of this shows up as an import error - Python happily imports a moved class - so a refactor without corresponding coverage looks successful (imports fine, app boots) while quietly changing behavior for edge-case scenario combinations.

**How to avoid:**
- Sequence the refactor strictly after golden-file test coverage exists for the calculators being moved, not before or in parallel - the golden files are the regression detector for the refactor itself, not just for future logic changes.
- Refactor one calculator domain at a time, with each domain's move as its own commit/PR, running the full test suite (and specifically the golden-file suite) between each move - not one giant restructuring commit.
- Grep for cross-references before moving anything: any function or constant used by more than one calculator class must be explicitly extracted to a shared module first, not left to accidentally still work via a wildcard or relative import.
- Do not touch the `ScenarioType` enum work and the file-split work in the same change - replacing hardcoded scenario strings is itself a correctness-risk change (a typo'd enum value silently falls through to a different branch) and should get its own test coverage and its own PR, sequenced either strictly before or strictly after the file split, never simultaneously.
- Explicitly verify `CalculatorFactory`'s model-to-calculator mapping after each move (a unit test that asserts every registered model type resolves to a calculator instance) since this factory pattern is the seam most likely to be forgotten when classes move files.

**Warning signs:**
- Any diff where a class body is unchanged but its file location changes and the PR is large ("just moving things") - large "just moving things" diffs are exactly where reviewers stop reading carefully.
- Golden-file test suite not run (or not yet existing) for a calculator domain before its file is moved.
- Import errors are the only thing checked as "does the refactor work" (imports succeeding proves nothing about scenario correctness).

**Phase to address:**
Maintainability refactors phase - but only after Correctness safety-net phase has landed golden-file coverage for the same domains being moved. This is a hard sequencing dependency, not just a suggestion.

---

### Pitfall 6: Moving models during the refactor breaks auditlog/simple-history registration and migration history

**What goes wrong:**
This codebase uses both `django-auditlog` and `django-simple-history` for change tracking, and models.py itself (3,396 lines) is flagged as a future god-object split candidate alongside calculators.py. If model classes are ever moved between files/apps as part of the broader refactor effort, historical models (which live in the same app as the tracked model by default) do not automatically follow - moving a model to a different app without updating its history registration can raise `MultipleRegistrationsError`, and any `populate_history`-style data migration becomes invalid if a later schema migration changes the model without a matching update to the historical model's migration state. Auditlog middleware registration (referenced in `settings.py`) is similarly keyed to specific model paths and needs explicit updates if models relocate.

**Why it happens:**
`simple_history.register()` and auditlog's `auditlog.register()` calls are typically written once, near app startup or in an `apps.py`/`admin.py`, and are easy to forget when a model is later moved as part of an unrelated refactor - especially because the failure (a duplicate registration or an inconsistent history migration) may not surface until a migration is actually run, not at import time.

**How to avoid:**
- Treat any model file move as a two-step change: (1) update the model's file location, and (2) explicitly search for and update every `register()` call (auditlog and simple-history) and every place the model is imported by name, verifying with `makemigrations --check --dry-run` that no unexpected migration is generated.
- If a model changes apps (not just files within the same app), pin its historical model's app explicitly via simple-history's `app` parameter rather than relying on the default same-app behavior, and regenerate/inspect the resulting migration by hand before applying it.
- Since this milestone's stated scope is calculators.py first (not models.py), defer any models.py split to a later milestone specifically so this risk does not compound with the calculator refactor in the same window - but flag it now as a known trap for whoever does tackle models.py.

**Warning signs:**
- `python manage.py makemigrations --check` reports unexpected pending migrations after a routine file move that "shouldn't" have changed any schema.
- `MultipleRegistrationsError` or similar exceptions on app startup after a model relocation.
- Historical/audit records for a model go silent (no new history rows created) after a refactor, with no error raised - the most dangerous variant because it fails silently.

**Phase to address:**
Maintainability refactors phase (as a watch-item / guardrail, since models.py itself is explicitly out of scope for the initial split per PROJECT.md - but the calculators.py split may still touch model imports in `calculators.py`, so verify no incidental model-registration disruption occurs even from the in-scope work).

---

### Pitfall 7: Rate limiting on App Engine Standard silently no-ops across instances or locks out the frontend

**What goes wrong:**
DRF's built-in throttle classes and packages like `django-ratelimit` store their counters in Django's cache framework. If the cache backend is left at the default `LocMemCache` (in-process memory), each App Engine Standard instance (and each of the 4 gunicorn workers per instance, per `app.yaml`'s `-w 4`) keeps its own independent counter. The practical effect is that a rate limit configured as "10 requests/minute" can actually allow 10 x (number of live instances x workers) requests/minute in production, because App Engine autoscales instance count under load - exactly when the limit matters most. Separately, if the throttle key is derived from client IP without correctly configuring DRF's `NUM_PROXIES` for App Engine's actual proxy chain, either every request appears to come from the load balancer's IP (all users share one bucket, locking out the whole frontend after a burst of legitimate traffic) or the client IP is trivially spoofable via the `X-Forwarded-For` header (defeating the limit entirely for unauthenticated endpoints).

**Why it happens:**
`LocMemCache` is Django's zero-configuration default and works fine in local development and even in a single-instance staging environment, masking the problem until production autoscaling actually spins up multiple instances. The IP-detection issue happens because the correct proxy count depends on GCP's specific infrastructure (App Engine's load balancer plus any additional reverse proxies), which is easy to get wrong by guessing rather than verifying against actual request headers in the target environment.

**How to avoid:**
- Configure a shared cache backend (Memorystore/Redis, or App Engine Memcache) for the throttle/rate-limit cache alias specifically, verified by a smoke test that hits the endpoint from two different App Engine instances (or simulated via forcing multiple gunicorn workers locally) and confirms the counter is shared.
- Set DRF's `NUM_PROXIES` to the actual, verified proxy hop count in front of the app on App Engine, confirmed by logging the raw `X-Forwarded-For` header value on a real deployed request rather than assuming a number.
- Do not rate-limit the frontend's own known service traffic (or authenticated same-org requests) at the same threshold as anonymous public traffic - since this app's frontend is a known first-party client, scope aggressive limits to unauthenticated endpoints (login, registration, password reset) first, per the milestone's stated focus on "auth endpoints."
- Load-test the rate limit configuration against a realistic burst (simulating App Engine scaling up instances) before enabling in production, not just against a single local dev server.

**Warning signs:**
- Rate limit thresholds that "never seem to trigger" in production despite the traffic pattern that should trigger them (classic sign of per-instance counters never accumulating high enough).
- Legitimate frontend users occasionally get throttled in bursts (classic sign of shared-bucket-by-proxy-IP mis-detection).
- No explicit `CACHES` alias or backend change accompanies the rate-limiting PR.

**Phase to address:**
Auth & security hardening phase.

---

### Pitfall 8: Caching "immutable" IPCC reference data goes stale after load_reference_data reruns, or duplicates across workers

**What goes wrong:**
Caching IPCC lookups (countries, climate types, GWP coefficients, `FIData`, `FMGData`) via `functools.lru_cache` or a module-level cache is the right fix for the audit-flagged "calculators load IPCC tables every time" bottleneck, but it introduces two new failure modes if done naively: (1) if `load_reference_data` is ever rerun against a live environment (e.g., a legitimate reference-data update, or a `--force` PK rename like "Turkey to Türkiye") without a corresponding cache invalidation, the app keeps serving pre-update values from memory until every worker process restarts - producing wrong calculation results with no error raised; (2) with App Engine's `-w 4` gunicorn workers (and multiple autoscaled instances), an `lru_cache` decorator caches per-process, so the same "immutable" table gets loaded and held in memory redundantly across every worker and instance, multiplying memory footprint without actually reducing total database load proportionally to what a shared cache would achieve.

**Why it happens:**
"Reference data is immutable" is true in the sense that end users cannot modify it, but it is not actually immutable at the infrastructure level - the whole point of `dump_reference_data`/`load_reference_data` is that this data does get intentionally updated over time (new countries, corrected GWP coefficients, IPCC methodology revisions). A cache with no invalidation hook conflates "users can't write to this" with "this never changes," which is a stronger and false assumption.

**How to avoid:**
- Prefer a cache with an explicit TTL or an explicit invalidation call wired into the `load_reference_data` management command itself (e.g., clear the relevant cache keys/call `cache.clear()` for the reference-data cache alias at the end of a successful load), rather than an unbounded `lru_cache` with no invalidation path.
- If `lru_cache` is used for pure-Python lookups within a single process (acceptable for reducing per-request DB round-trips within that process's lifetime), document explicitly that a full worker restart (already routine on every deploy) is the invalidation mechanism, and never rerun `load_reference_data` against a running production environment without also triggering a restart/redeploy of the app.
- For data genuinely worth sharing across workers/instances (large tables queried on nearly every request, like GWP coefficients), use the same shared cache backend chosen for rate limiting (Memorystore/Redis) rather than in-process caching, so a single invalidation event actually reaches every worker.
- Add a smoke test that runs `load_reference_data` in a test environment, changes a known value, and asserts the next calculator call reflects the new value (not a stale cached one) - this is the regression test for cache invalidation, and it does not exist today because caching does not exist today.

**Warning signs:**
- A production reference-data update (new fixture data loaded) does not take effect until the next deploy, and nobody can explain why without checking whether a restart happened to occur incidentally.
- Memory usage per App Engine instance climbs after adding caching, disproportionate to the actual size of the reference tables (sign of per-worker duplication with no ceiling).

**Phase to address:**
Performance phase - but the invalidation hook must be designed and tested before the caching itself is turned on, not bolted on afterward.

---

### Pitfall 9: N+1 fixes via prefetch_related silently break calculator data access patterns that filter or mutate the related manager

**What goes wrong:**
Adding `select_related`/`prefetch_related` to project/activity retrieval views (the audit flags `views.py` lines with minimal or empty prefetch) is the correct fix for N+1 queries, but the calculator layer already accesses related objects like `activity.modules` and processes them per scenario. If any of that downstream code calls `.filter()`, `.exclude()`, `.order_by()`, or any other queryset method directly on a manager that was prefetched by the view (e.g., `activity.modules.filter(module_type=...)` inside a calculator), Django silently discards the prefetched cache and issues a brand-new, unprefetched query for that call - which not only reintroduces the N+1 problem for that specific access pattern (now doing extra queries on top of the ones already run), it can also return a queryset that no longer matches what the calculator's existing logic implicitly assumed was already loaded (e.g., ordering, or a superset/subset of instances), risking calculation results built from a subtly different module set than the calculator was written against. The same applies to `.add()`/`.create()`/`.remove()`/`.clear()`/`.set()` on the prefetched relation, which clear the prefetch cache entirely.
This is exactly the kind of change that passes tests focused on "does the endpoint return 200" while silently changing which rows feed a downstream calculation - the audit's own "complex three-scenario calculation pipeline" fragile-area notes that missing scenario handling causes silent wrong results, and an accidentally-refetched, differently-filtered module queryset is a new way to trigger that same class of bug.

**Why it happens:**
`prefetch_related` optimizes the common case (iterate all related objects), but any narrowing operation on that manager looks identical in code to the unprefetched version - there is no visible syntax difference between "iterate the prefetched cache" and "issue a brand-new filtered query," so a developer adding `prefetch_related` to a view has no easy way to know, without grepping the whole calculator layer, whether any downstream code calls `.filter()` on the now-prefetched relation.

**How to avoid:**
- Before adding `prefetch_related('modules')` (or similar) to a view queryset, grep the calculator/serializer code paths reachable from that view for any `.filter()`/`.exclude()`/`.order_by()`/mutation call on the same relation name, and either refactor those calls to work against the already-fetched Python list (e.g., `[m for m in activity.modules.all() if m.module_type == x]`) or use Django's `Prefetch(queryset=..., to_attr='filtered_modules')` to create a distinct, explicitly-filtered attribute rather than relying on the base manager staying prefetched.
- Add a query-count assertion (`assertNumQueries` or `django.test.utils.CaptureQueriesContext`) to the calculator/view tests for the paths being optimized, both before and after the prefetch change, to prove the query count actually dropped rather than trusting visual code review alone.
- Roll out prefetch changes one relation/view at a time with the golden-file/calculator test suite run in between, since a data-shape change here (subtly different module set feeding a calculator) is a correctness risk, not just a performance one, and needs the same regression coverage as the god-object refactor.

**Warning signs:**
- Query count in tests does not actually decrease after adding `prefetch_related` (proof that something downstream is still re-querying).
- Any calculator or serializer code that does `<related_manager>.filter(...)` where `<related_manager>` is also the target of a view-level `prefetch_related` call.
- Calculation results change for any project after a "performance-only" N+1 fix deploy, however slightly - this should be treated as a correctness regression, not an acceptable side effect.

**Phase to address:**
Performance phase - but require the same golden-file coverage from the Correctness safety-net phase as a precondition, since this pitfall's failure mode is a correctness bug wearing a performance-fix costume.

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|-----------------|-----------------|
| Running CI against SQLite instead of Postgres for speed | Faster CI, no service container setup | Masks Postgres-only bugs (case sensitivity, JSONField, locking, migration ordering) until production | Never for this project - production is Postgres |
| Adding calculator validation as blanket "all fields required" without an allowlist of known lenient defaults | Fast to write, catches the most obvious gaps | Breaks existing live projects that depend on documented lenient fallbacks (aquaculture electricity, peat factors) | Never - always audit known defaults first |
| Golden-file tests with exact-equality assertions | Simple to write, obviously "passes" today | Becomes flaky across numpy/platform versions or gets "fixed" by baking in wrong values | Never - always use explicit tolerance |
| One giant PR moving all of calculators.py at once | Feels like faster progress, single review pass | Reviewers cannot meaningfully verify scenario correctness across an 8,270-line diff; any silent behavior change is nearly undetectable | Never for calculators.py - always split by domain, incrementally |
| `lru_cache` on reference-data lookups with no invalidation hook | Immediate query reduction, near-zero code change | Serves stale data after any live `load_reference_data` rerun until a full restart | Acceptable only if paired with a documented "any reference-data reload requires a redeploy" runbook entry |
| Adding `prefetch_related` to a view without auditing downstream `.filter()` calls on the same relation | Query count visibly drops in the one endpoint tested | Reintroduces N+1 (and possible data-shape drift) wherever the calculator layer filters the prefetched manager | Never - always grep downstream usage first |

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|-----------------|-------------------|
| App Engine Standard (gunicorn -w 4, autoscaled instances) rate limiting | Using default `LocMemCache` for throttle counters, assuming single-process behavior | Configure a shared cache backend (Memorystore/Redis) explicitly for the throttle cache alias, and load-test with simulated multi-instance scaling |
| App Engine reverse proxy chain and client IP detection | Assuming `REMOTE_ADDR` or the full `X-Forwarded-For` header is the real client IP | Set DRF's `NUM_PROXIES` to the verified real hop count for App Engine's load balancer, confirmed by logging actual header values from a deployed request |
| GitHub Actions CI database | Running tests against SQLite because it needs no setup | Add a Postgres service container matching production's engine version |
| `load_reference_data` reference-data reload in a cached environment | Assuming the cache clears itself when fixtures are reloaded | Wire an explicit cache-invalidation call into the management command, or document that a redeploy/restart is mandatory after any reload |
| `django-simple-history` / `django-auditlog` during file/app moves | Moving a model class without checking its `register()` call or migration state | Update registration explicitly, run `makemigrations --check --dry-run`, and hand-inspect any generated migration before applying |

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|-----------------|
| Per-process rate-limit counters on autoscaled App Engine | Rate limits "never trigger" in production despite matching traffic patterns | Shared cache backend (Redis/Memorystore) for throttle keys | Breaks as soon as App Engine scales beyond 1 instance under load - i.e., routinely |
| `lru_cache`/module-level reference-data cache duplicated per gunicorn worker | Memory usage per instance grows disproportionate to reference-table size | Prefer a shared cache for large, frequently-hit tables; keep in-process caching only for small, cheap-to-duplicate lookups | Breaks as worker count (`-w 4`) x instance count grows, or as reference tables grow with new IPCC methodologies |
| `prefetch_related` added to a view whose downstream calculator code calls `.filter()` on the same relation | Query count does not actually drop; extra queries appear in profiling despite the "optimization" | Audit downstream filter calls before adding prefetch; use `Prefetch(..., to_attr=...)` for filtered subsets | Breaks immediately - it is not a scale threshold, it is a logic error that happens to look like a performance non-improvement |
| Minitool permutation generation (flagged in CONCERNS.md, out of scope this milestone but adjacent) | OOM on large parameter ranges | Stream permutations lazily; cap worker pool | Breaks at 20+ land modules x 5+ scenarios per CONCERNS.md estimate - not addressed by this milestone but do not let caching/N+1 work touch this path incidentally |

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| Treating DRF/`django-ratelimit` throttling as a real anti-abuse/DoS control | Both DRF's own docs and the known IP-spoofing issue in DRF confirm application-level throttling is not a substitute for infrastructure-level protection (WAF, Cloud Armor) - relying on it alone for auth-endpoint protection under-protects against a determined attacker | Pair application throttling with GCP-level protections (Cloud Armor rate limiting) for auth endpoints specifically; treat DRF throttling as a courtesy limit for accidental abuse, not a security boundary |
| Rate-limiting keyed on the full raw `X-Forwarded-For` header without `NUM_PROXIES` configured | Trivially bypassed by an attacker appending arbitrary IPs to the header for unauthenticated endpoints (documented DRF behavior) | Set `NUM_PROXIES` correctly for App Engine's actual proxy chain so only the last, trusted-added IP segment is used |
| Fail-fast calculator validation returning verbose stack-trace-style error messages | Could leak internal field names, model structure, or IPCC data-table internals to API consumers if validation errors are not shaped through the standard DRF error serializer | Route all new validation errors through DRF's standard `ValidationError`/exception handler, matching existing error response shape, no raw exception text in responses |
| Reference-data cache invalidation gaps used as an accidental attack surface | Not a classic security bug, but a stale-data window after a legitimate correction (e.g., a GWP coefficient fix) means wrong emissions numbers could be reported as "current" for the cache's lifetime with no user-visible warning | Treat cache invalidation testing as part of the security/correctness gate, not purely a performance nice-to-have |

## "Looks Done But Isn't" Checklist

- [ ] **CI test gate:** Green build achieved - verify it actually ran against Postgres with `load_reference_data` executed, not SQLite with fixtures skipped; check the job log for the actual fixture-load duration (should be 30+ seconds per the fixtures guide).
- [ ] **Calculator validation:** Validation errors added and passing new tests - verify every documented lenient-default path (aquaculture electricity, peat conversion, forestry cross-scenario reuse, flooded-rice tier-2) was explicitly reviewed and either preserved or deliberately changed, not accidentally broken.
- [ ] **Golden-file tests:** Tests exist and pass - verify they use tolerance-based assertions (not exact equality) and that the expected values were cross-checked against the `excel_reference_version/` mirror or another independent source, not just "whatever the code currently outputs."
- [ ] **calculators.py split:** File split into domain modules, app still imports and boots - verify `CalculatorFactory`'s registration mapping was tested explicitly (every model type resolves to the right calculator), and that golden-file tests were run and green both before and after each domain's move.
- [ ] **Rate limiting:** Throttle classes configured and returning 429s in manual testing - verify the cache backend is shared (not `LocMemCache`) and that a simulated multi-instance test confirms the limit is enforced cumulatively, not per-process.
- [ ] **Reference-data caching:** Cache added, fewer DB queries observed - verify there is an explicit invalidation path tied to `load_reference_data`, and that a test proves a reference-data update takes effect without requiring undocumented tribal knowledge about restarts.
- [ ] **N+1 fixes:** `prefetch_related`/`select_related` added, query count drops in the tested view - verify no calculator/serializer code downstream calls `.filter()` or mutates the same relation (which would silently undo the fix and possibly change calculation inputs), confirmed via `assertNumQueries` in tests, not visual inspection alone.

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|-----------------|-----------------|
| CI gate turns out to have been running against SQLite/no fixtures | LOW | Reconfigure the CI job to use a Postgres service container and run `load_reference_data`; re-run the full suite once against the corrected config and treat any newly-surfaced failures as real bugs, not CI flakiness |
| Fail-fast validation broke existing projects in production | MEDIUM-HIGH | Roll back the hard-fail behavior to warning/log-only immediately; audit logged validation failures to build the missing lenient-default allowlist; re-enable hard-fail only for confirmed genuine-gap cases |
| Golden-file test discovered to have baked in a wrong value after a "fix the flaky test" shortcut | MEDIUM | Cross-check the disputed value against the `excel_reference_version/` mirror or an independent recomputation; if the golden file is wrong, correct it with a commit message explaining the discrepancy and the source of truth used, and audit git history for other silent golden-file "fixes" |
| calculators.py split introduced a silent scenario-dispatch regression | HIGH | Revert the specific domain's file move (not the whole refactor); add the missing golden-file test for the regressed scenario combination first; redo the move only once that test is green against both old and new file locations |
| Rate limiting locked out the frontend due to shared-IP proxy misconfiguration | LOW-MEDIUM | Immediately raise or disable the threshold for the affected endpoint via config (not code deploy, if the throttle rate is settings-driven); fix `NUM_PROXIES`/cache backend; re-enable gradually |
| Reference-data cache served stale values after a legitimate fixture update | LOW | Trigger a redeploy/restart to clear in-process caches immediately as a stopgap; then implement the missing explicit invalidation hook so this does not require a manual restart going forward |
| N+1 fix changed calculation results via an accidentally-refetched, differently-filtered module set | HIGH | Revert the specific `prefetch_related` addition on the affected view; add the missing golden-file/query-count test for that access path; reapply only after confirming the downstream `.filter()` call sites were fixed to use `to_attr` or in-memory filtering |

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|-------------------|---------------|
| CI runs against fake/skipped data (Pitfall 1) | CI / test automation phase | CI job log shows Postgres connection and 30+ second fixture load; `test_reference_bootstrap.py` gates the merge |
| SQLite-vs-Postgres behavioral drift (Pitfall 2) | CI / test automation phase | CI config pinned to `postgresql` backend; migration review checklist includes "schema change + RunPython in same file?" |
| Fail-fast validation breaks lenient defaults (Pitfall 3) | Correctness safety-net phase | Warning/log-only rollout period completed with zero unexpected validation failures against a real-project-shaped fixture set before hard-fail is enabled |
| Golden-file brittleness/staleness (Pitfall 4) | Correctness safety-net phase | Every golden-file assertion uses documented tolerance; any golden-file value change is a reviewed, explained commit |
| God-object refactor scenario-dispatch regression (Pitfall 5) | Maintainability refactors phase (after Correctness safety-net) | Golden-file suite green before and after each domain's move; `CalculatorFactory` mapping has explicit test coverage |
| History/audit registration breakage during model moves (Pitfall 6) | Maintainability refactors phase (guardrail even for calculators.py-only scope) | `makemigrations --check --dry-run` clean after any file move touching model imports |
| Rate limiting per-instance no-op or IP-spoofable (Pitfall 7) | Auth & security hardening phase | Shared cache backend confirmed via multi-instance/multi-worker test; `NUM_PROXIES` verified against real deployed header values |
| Reference-data cache staleness/duplication (Pitfall 8) | Performance phase | Test proves a `load_reference_data` update is reflected without requiring an undocumented restart; per-worker memory growth measured and bounded |
| N+1 fix changes calculator data semantics (Pitfall 9) | Performance phase (after Correctness safety-net golden files exist) | `assertNumQueries` confirms real query reduction; golden-file suite green after each prefetch change |

## Sources

- `.planning/codebase/CONCERNS.md` (this repo's 2026-07-08 audit - primary source for known bugs, fragile areas, and scaling limits referenced throughout)
- `.planning/codebase/TESTING.md` (this repo's 2026-07-08 testing-patterns map - primary source for CI/test infrastructure gaps)
- `.planning/PROJECT.md` (milestone scope and constraints)
- [Throttling - Django REST framework](https://www.django-rest-framework.org/api-guide/throttling/) - official docs on cache-backed throttling and `NUM_PROXIES`
- [Bypass Throttling based on source ip address - encode/django-rest-framework#7813](https://github.com/encode/django-rest-framework/issues/7813) - documented IP-spoofing limitation of DRF throttling
- [Django Ratelimit documentation - security considerations](https://django-ratelimit.readthedocs.io/en/stable/security.html) - cache backend requirements (atomic increment) and spoofing caveats
- [Django ticket #23805 - query `first` method clears cached queryset for prefetch_related](https://code.djangoproject.com/ticket/23805) and [Django ticket #30355](https://code.djangoproject.com/ticket/30355) - documented prefetch-cache-clearing gotchas
- [django-simple-history - Common Issues](https://django-simple-history.readthedocs.io/en/stable/common_issues.html) and [Advanced Usage](https://django-simple-history.readthedocs.io/en/2.0/advanced.html) - historical model app placement and migration behavior
- [Django documentation - Databases](https://docs.djangoproject.com/en/6.0/ref/databases/) and community write-ups on SQLite-vs-Postgres behavioral differences (case sensitivity, JSON1 extension, DDL transaction handling)
- Community discussion on golden-file/numeric test tolerance conventions (floating-point non-associativity across platforms/BLAS backends)

---
*Pitfalls research for: Django/DRF brownfield hardening (EX-ACT GHG calculator)*
*Researched: 2026-07-08*
