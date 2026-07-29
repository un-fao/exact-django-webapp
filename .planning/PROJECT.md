# EX-ACT Backend: Reliability & Maintainability Hardening

## What This Is

EX-ACT is FAO's greenhouse-gas and emissions calculator, exposed as a Django 5.2 + Django REST Framework API. It computes CO2e emissions for agricultural and land-use activities across three scenarios (start / with / without) using IPCC emission factors, and generates WeasyPrint PDF reports for project appraisals. This milestone hardens the existing backend: it closes the reliability, security, and maintainability gaps surfaced by the 2026-07-08 codebase audit without changing the public API or the science.

## Core Value

Emission calculations must be correct and reproducible across all activity types and all three scenarios, and the codebase must be safe to change without silently regressing those numbers.

## Requirements

### Validated

<!-- Existing, shipped capability inferred from .planning/codebase/ map. -->

- ✓ Four-layer GHG calculation engine (DRF API -> calculator adapters -> pure math -> IPCC reference data) - existing
- ✓ 60+ calculator classes covering annual/perennial cropland, flooded rice, livestock, forest management, grassland, coastal wetlands, fisheries/aquaculture, value chains, energy, and inputs - existing
- ✓ Three-scenario (start/with/without) results with TOTAL/ACTIVITY/GAS/ACTIVITY_GAS breakdowns - existing
- ✓ Nested DRF routing under /api/projects/{id}/... with Firebase + SimpleJWT authentication - existing
- ✓ WeasyPrint PDF report generation per project/activity - existing
- ✓ IPCC reference-data pipeline (load_reference_data / dump_reference_data with PK-stability guard) - existing
- ✓ Cloud Run LUC batch computation with subprocess fallback - existing
- ✓ Auditlog + simple-history change tracking; i18n (en/es/fr/ru) - existing

### Active

<!-- This milestone. Grouped by cluster; all are hypotheses until shipped. -->

**CI / test automation (HIGH)**
- [ ] CI runs the test suite automatically before any deploy (currently neither GitHub Actions nor Bitbucket runs pytest)
- [ ] CI runs bandit and pip-audit gates in the same step; deploy is blocked on failure

**Correctness safety-net for fragile calculators (HIGH)**
- [ ] Scenario-level input validation in BaseCalculator so missing required fields fail fast with a clear message instead of a deep math-layer stack trace
- [ ] Golden-file tests for audit-flagged fragile paths: value chains (energy + refrigerants), flooded-rice minor seasons with tier-2 overrides, forest-management biomass matrices
- [ ] Known tier-2 fallback bugs fixed or guarded: aquaculture electricity default of 0, peat conversion factors, forestry start-value reuse across scenarios

**Auth & security hardening (HIGH)**
- [ ] Integration tests for Firebase auth sync (UID mismatch, email change, concurrent auth events)
- [ ] Pre-deploy sanity check asserting DEBUG=False and non-empty CORS_ALLOWED_ORIGINS in production; no reliance on blanket CORS_ORIGIN_ALLOW_ALL
- [ ] Rate limiting on auth endpoints

**Performance (MEDIUM)**
- [ ] N+1 queries eliminated in project/activity retrieval via select_related / prefetch_related
- [ ] Immutable IPCC reference-table lookups cached (module-level cache or lru_cache)

**Maintainability refactors (MEDIUM)**
- [ ] God-object decomposition begun, starting with calculators.py (8,270 lines) split by domain (land / livestock / aquaculture / energy / value chains)
- [ ] ScenarioType enum replaces hardcoded "start_w" / "start_wo" / "w" / "wo" strings
- [ ] Scattered TODO/FIXME markers migrated into the issue tracker

### Out of Scope

- New emission categories or new IPCC methodologies - hardening only, no new science
- Public API contract changes - endpoints, payload shapes, and result formats stay stable so the WebApp frontend is unaffected
- Frontend / WebApp changes - this milestone is backend-only
- Completing the DB-router split - scaffolding stays as-is; single-DB model retained until multi-tenancy is actually needed
- Minitool permutation-engine rewrite - a real scaling risk, but deferred; not on the critical path for correctness
- Firebase custom-wrapper replacement - audit as part of auth tests, but full migration to plain Admin SDK is a future milestone

## Context

- Brownfield: the app is live (App Engine Standard + Cloud Run jobs + Cloud SQL Postgres + Firebase auth). A full codebase map exists at `.planning/codebase/` (ARCHITECTURE, STACK, STRUCTURE, CONVENTIONS, TESTING, INTEGRATIONS, CONCERNS; refreshed 2026-07-08).
- The CONCERNS.md audit is the source of this milestone's scope: it is an evidence-backed backlog with file/line references for every issue listed under Active requirements.
- Known fragile areas with repeated post-release fixes in the CHANGELOG: ActivityBuilderSerializer (module add/remove), forest-management biomass matrices, three-scenario calculator pipeline.
- Tests exist (pytest + Django APITestCase, factory-boy) but run only locally as a PR gate; CI deploys without executing them.
- Reference data is database-truth, fixtures-derived; the dump command guards PK stability. Round-trip enforced by `api/tests/test_reference_bootstrap.py`.

## Constraints

- **Tech stack**: Python 3.11, Django 5.2.14, DRF 3.16.1, pinned requirements.txt - production platform is App Engine Standard python311
- **Testing**: no pytest-django; Django-dependent tests must use Django TestCase / APITestCase - suite bootstraps Django via those classes
- **Local environment**: dev sandbox has no Postgres/Docker; the full suite runs only in CI or on DB-equipped machines - py_compile is the only reliable local gate
- **Data integrity**: JSON fixtures are never hand-edited; changes go through dump_reference_data with the PK-stability guard
- **Compatibility**: public API contract and calculation results for currently-correct paths must not change - the WebApp frontend and existing user projects depend on both
- **Workflow**: conventional commits (commitizen), feature branches off develop, PRs target develop; version numbers managed by tooling
- **Style**: never use em-dashes anywhere in this repo (project rule)

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Scope this milestone to hardening (all five audit clusters) rather than correctness-only or security-only | User chose the broad option; the audit's HIGH items span CI, correctness, and auth, and deferring any of them leaves known regression paths open | - Pending |
| Seed project context from the existing codebase map instead of fresh questioning | Map was refreshed the same day (2026-07-08) and CONCERNS.md is already an evidence-backed backlog | - Pending |
| Keep single-DB model; do not implement router split | Routers are scaffolding only; no current multi-tenancy requirement | - Pending |
| Split calculators.py first among the god objects | Largest file (8,270 lines), highest churn, and the seat of the fragile three-scenario logic | - Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? -> Move to Out of Scope with reason
2. Requirements validated? -> Move to Validated with phase reference
3. New requirements emerged? -> Add to Active
4. Decisions to log? -> Add to Key Decisions
5. "What This Is" still accurate? -> Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check - still the right priority?
3. Audit Out of Scope - reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-07-08 after initialization*
