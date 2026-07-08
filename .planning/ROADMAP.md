# Roadmap: EX-ACT Backend Reliability & Maintainability Hardening

## Overview

This milestone hardens the live EX-ACT backend in strict dependency order, without changing the public API or the science. Phase 1 stands up a CI gate that runs the full test suite against a real Postgres, blocks deploys on high-severity security findings, and refuses a bad production config. Phase 2 builds the correctness safety-net (fail-fast scenario validation, tolerance-based golden files, and fixes for three known tier-2 bugs) that every later change relies on. Phase 3 uses that safety-net to begin decomposing the 8,270-line calculators.py and to replace hardcoded scenario strings with an enum. Phase 4 closes the performance and auth gaps (N+1 elimination, IPCC caching, Firebase auth-sync tests, auth rate limiting) once golden files exist to catch silent regressions.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [ ] **Phase 1: CI Test Gate & Production Config Guard** - Every deploy is blocked unless the full suite passes on real Postgres, security scans are clean, and production config is safe
- [ ] **Phase 2: Calculator Correctness Safety-Net** - Fragile calculator paths are pinned by golden files, missing inputs fail fast, and three known tier-2 bugs are fixed
- [ ] **Phase 3: Calculators Decomposition & ScenarioType Enum** - One calculator domain moves into an api/calculators/ package behind a re-export shim, with scenario literals replaced by an enum and no numeric drift
- [ ] **Phase 4: Performance & Auth Hardening** - Retrieval endpoints run constant queries, IPCC lookups cache per worker, and auth endpoints gain sync tests plus per-IP rate limiting

## Phase Details

### Phase 1: CI Test Gate & Production Config Guard
**Goal**: A failing test, a high-severity security finding, or a misconfigured production deploy is blocked before it reaches App Engine.
**Mode:** mvp
**Depends on**: Nothing (first phase)
**Requirements**: CI-01, CI-02, SEC-03
**Success Criteria** (what must be TRUE):
  1. A pull request whose pytest suite fails cannot start the App Engine deploy job, because the deploy job declares a `needs:` dependency on a passing test job.
  2. The CI test job runs pytest against a real Postgres service container after `manage.py migrate` and `manage.py load_reference_data --app=all`, and `test_reference_bootstrap.py` passes (job runtime exceeds 30 seconds, confirming fixtures actually loaded, not a red-herring green).
  3. A HIGH-severity bandit finding or a known-CVE pip-audit result in the same gated job blocks the deploy.
  4. `manage.py check --deploy` exits non-zero when APP_MODE is production and either DEBUG is True or CORS_ALLOWED_ORIGINS is empty, and CI invokes that check so a bad production config never reaches App Engine.
**Plans**: TBD

### Phase 2: Calculator Correctness Safety-Net
**Goal**: Audit-flagged fragile calculator paths are pinned by tolerance-based golden files, missing scenario inputs fail fast, and the three known tier-2 bugs are fixed with regression tests.
**Mode:** mvp
**Depends on**: Phase 1
**Requirements**: CALC-01, CALC-02, CALC-03, CALC-04, CALC-05, CALC-06, CALC-07
**Success Criteria** (what must be TRUE):
  1. A calculator invoked with a missing required field for any scenario (start/with/without) raises a clear validation error naming the field and the scenario before any math_model function is called.
  2. Golden-file tests pin value-chains (energy plus refrigerants), flooded-rice minor-season tier-2 overrides, and forest-management biomass matrices across all three scenarios at TOTAL/ACTIVITY/GAS breakdowns using pytest.approx tolerance, and a changed snapshot value makes the test fail.
  3. Each of the three tier-2 bugs (aquaculture electricity default-to-0, peat volume conversion factor, forestry start-value cross-scenario reuse) has a regression test that failed before the fix and passes after it.
**Plans**: TBD

### Phase 3: Calculators Decomposition & ScenarioType Enum
**Goal**: One calculator domain moves out of the 8,270-line calculators.py into an api/calculators/ package behind a re-export shim, hardcoded scenario literals become a ScenarioType enum, and no numeric result changes.
**Mode:** mvp
**Depends on**: Phase 2
**Requirements**: MAINT-01, MAINT-02, MAINT-03
**Success Criteria** (what must be TRUE):
  1. At least one calculator domain (land modules or value chains, whichever gained golden coverage first) lives in a new api/calculators/ package, every pre-existing import still resolves through a backward-compatible re-export shim, and the full test suite plus the Phase 2 golden files pass unchanged.
  2. A ScenarioType str-subclass enum replaces the hardcoded "start_w" / "start_wo" / "w" / "wo" literals in the decomposed modules, and equality against the old string values still holds.
  3. Scattered TODO/FIXME markers are migrated into the issue tracker (one issue per cluster) and each source comment is annotated with its issue link or removed.
**Plans**: TBD

### Phase 4: Performance & Auth Hardening
**Goal**: Project and activity retrieval run a constant number of queries, IPCC lookups hit the database once per worker, and auth endpoints gain sync-integration tests plus per-IP rate limiting.
**Mode:** mvp
**Depends on**: Phase 2
**Requirements**: PERF-01, PERF-02, SEC-01, SEC-02
**Success Criteria** (what must be TRUE):
  1. Project and activity retrieval endpoints execute a constant number of queries regardless of activity/module count, proven by assertNumQueries tests that compare a 1-object fixture against a many-object fixture.
  2. Repeated IPCC reference-table lookups hit the database only once per worker process, proven by a test asserting a single query across repeated calls.
  3. Firebase auth-sync integration tests assert that an unknown firebase_uid returns a clean 401 with no leaked exception text, an email mismatch is authenticated by UID with the mismatch behavior asserted, and concurrent same-email registration leaves no orphaned Firebase user.
  4. Auth endpoints (register, login, password-reset, token-refresh) return HTTP 429 beyond a per-IP rate tighter than the global anon throttle, while non-auth endpoint rates stay unchanged.
**Plans**: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 -> 2 -> 3 -> 4

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. CI Test Gate & Production Config Guard | 0/TBD | Not started | - |
| 2. Calculator Correctness Safety-Net | 0/TBD | Not started | - |
| 3. Calculators Decomposition & ScenarioType Enum | 0/TBD | Not started | - |
| 4. Performance & Auth Hardening | 0/TBD | Not started | - |
