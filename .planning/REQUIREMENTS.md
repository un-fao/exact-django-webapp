# Requirements: EX-ACT Backend Reliability & Maintainability Hardening

**Defined:** 2026-07-08
**Core Value:** Emission calculations must be correct and reproducible across all activity types and all three scenarios, and the codebase must be safe to change without silently regressing those numbers.

## v1 Requirements

Requirements for this milestone. Each maps to roadmap phases.

### CI / Test Automation

- [ ] **CI-01**: CI runs the full pytest suite against a real Postgres (service container or proxied instance) on every push/PR, and the App Engine deploy job cannot start unless the test job passes (needs: gating in deploy.yaml)
- [ ] **CI-02**: CI runs bandit (HIGH-severity threshold) and pip-audit in the same gated job, so a high-severity finding or known CVE blocks deploy

### Calculation Correctness

- [ ] **CALC-01**: A calculator invoked with a missing required field for any scenario (start/with/without) raises a clear validation error naming the field and the scenario, before any math_model function is called
- [ ] **CALC-02**: Golden-file tests pin value-chain calculations (energy + refrigerants) across all three scenarios at TOTAL/ACTIVITY/GAS breakdowns, using tolerance-based float comparison (pytest.approx), not exact equality
- [ ] **CALC-03**: Golden-file tests pin flooded-rice minor-season calculations with tier-2 overrides across all three scenarios, using tolerance-based float comparison
- [ ] **CALC-04**: Golden-file tests pin forest-management biomass-matrix calculations across all three scenarios, using tolerance-based float comparison
- [ ] **CALC-05**: The aquaculture electricity default-to-0 fallback is fixed or replaced with a loud validation error, with a regression test that failed before the change and passes after
- [ ] **CALC-06**: The peat volume conversion-factor fallback is fixed or replaced with a loud validation error, with a regression test that failed before the change and passes after
- [ ] **CALC-07**: Forestry tier-2 start-value reuse across scenarios is corrected so with/without scenarios use their own values, with a regression test that failed before the change and passes after

### Auth & Security

- [ ] **SEC-01**: Integration tests cover the Firebase auth sync matrix: valid token with no matching local firebase_uid returns a clean 401 without leaking internal exception text; a Firebase-vs-local email mismatch is authenticated by UID with the mismatch behavior asserted; concurrent registrations for the same email leave no orphaned Firebase user
- [ ] **SEC-02**: Auth endpoints (register, login, password-reset, token-refresh) enforce a tighter per-IP rate than the global anon throttle, returning HTTP 429 beyond it, while non-auth endpoint rates stay unchanged
- [ ] **SEC-03**: A Django system check fails deploy/startup when APP_MODE is production and either DEBUG is True or CORS_ALLOWED_ORIGINS is empty, wired into CI so a bad production config never reaches App Engine

### Performance

- [ ] **PERF-01**: Project and activity retrieval endpoints execute a constant number of queries regardless of how many activities/modules exist, enforced by assertNumQueries regression tests that compare 1-object vs many-object fixtures
- [ ] **PERF-02**: Immutable IPCC reference-table lookups are cached per worker process (lru_cache or equivalent), with a test asserting repeated lookups hit the database only once per process

### Maintainability

- [ ] **MAINT-01**: calculators.py decomposition is begun: at least one domain (land modules or value chains, whichever gains golden coverage first) moves into an api/calculators/ package with a backward-compatible re-export shim, and all pre-existing imports plus golden-file tests pass unchanged
- [ ] **MAINT-02**: A ScenarioType enum (str subclass) replaces hardcoded "start_w" / "start_wo" / "w" / "wo" literals in the calculator modules touched by the decomposition
- [ ] **MAINT-03**: Scattered TODO/FIXME markers are migrated into the issue tracker (one issue per cluster) and the comments annotated with issue links or removed

## v2 Requirements

Deferred to future release. Tracked but not in current roadmap.

### CI / Test Automation

- **CI-V2-01**: Combined bandit + pip-audit findings surfaced as PR comment / job summary instead of bare pass/fail

### Maintainability

- **MAINT-V2-01**: Remaining calculator domains (livestock / aquaculture / energy / forest) split out of calculators.py
- **MAINT-V2-02**: Structured log line (activity id, scenario, missing field) emitted on every calculator validation rejection

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| New emission categories or IPCC methodologies | Hardening only; no new science this milestone |
| Public API contract changes | WebApp frontend and existing user projects depend on current endpoints, payloads, and result formats |
| Frontend / WebApp changes | Milestone is backend-only |
| Global test-coverage percentage CI gate | Coverage numbers do not protect the audit-flagged fragile paths; golden files target risk directly |
| DB-router split (per-app databases) | Scaffolding stays; single-DB model retained until multi-tenancy is an actual requirement |
| Firebase custom-wrapper replacement | Audited via SEC-01 tests only; full migration to plain Admin SDK is a future milestone |
| Distributed cache (Redis/Memcached) for reference data | Data is immutable per process lifetime; lru_cache suffices with zero new infrastructure |
| Plugin/strategy-pattern rewrite of calculators | Mechanical decomposition only; structural rewrite cannot be verified byte-for-byte against golden files |
| Migrating suite off TestCase/APITestCase to pytest-django fixtures | Large blast radius, no correctness benefit; keep existing Django test classes |
| Minitool permutation-engine rewrite | Real scaling risk but not on the correctness critical path; deferred |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| CI-01 | Phase 1 | Pending |
| CI-02 | Phase 1 | Pending |
| SEC-03 | Phase 1 | Pending |
| CALC-01 | Phase 2 | Pending |
| CALC-02 | Phase 2 | Pending |
| CALC-03 | Phase 2 | Pending |
| CALC-04 | Phase 2 | Pending |
| CALC-05 | Phase 2 | Pending |
| CALC-06 | Phase 2 | Pending |
| CALC-07 | Phase 2 | Pending |
| MAINT-01 | Phase 3 | Pending |
| MAINT-02 | Phase 3 | Pending |
| MAINT-03 | Phase 3 | Pending |
| PERF-01 | Phase 4 | Pending |
| PERF-02 | Phase 4 | Pending |
| SEC-01 | Phase 4 | Pending |
| SEC-02 | Phase 4 | Pending |

**Coverage:**
- v1 requirements: 17 total
- Mapped to phases: 17
- Unmapped: 0

---
*Requirements defined: 2026-07-08*
*Last updated: 2026-07-08 after roadmap creation*
