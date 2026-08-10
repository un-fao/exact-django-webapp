---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
current_phase: 1
current_phase_name: CI Test Gate & Production Config Guard
status: verifying
stopped_at: Phase 1 executed and verified (human_needed); awaiting first CI run observation
last_updated: "2026-07-24T09:21:09.083Z"
last_activity: 2026-07-24
last_activity_desc: "Completed quick task 260724-eut: additive Cloud Run deployment path for review (WhiteNoise, Dockerfile.web_service, cloudrun-service.yaml, deploy-cloudrun.yaml, operator guide)"
progress:
  total_phases: 1
  completed_phases: 1
  total_plans: 3
  completed_plans: 3
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-07-08)

**Core value:** Emission calculations must be correct and reproducible across all activity types and all three scenarios, and the codebase must be safe to change without silently regressing those numbers.
**Current focus:** Phase 1 — CI Test Gate & Production Config Guard

## Current Position

Phase: 1 (CI Test Gate & Production Config Guard) — EXECUTING
Plan: 3 of 3
Status: Phase complete — ready for verification
Last activity: 2026-08-05 - Completed quick task 260805-nsn: merged main into a review sync branch, resolved the three conflicts, and opened PR #266 to unblock PR #265

Progress: [░░░░░░░░░░] 0%

## Performance Metrics

**Velocity:**

- Total plans completed: 0
- Average duration: n/a
- Total execution time: 0 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| - | - | - | - |

**Recent Trend:**

- Last 5 plans: n/a
- Trend: n/a

*Updated after each plan completion*
| Phase 01 P01 | 8min | 3 tasks | 3 files |
| Phase 01 P02 | unknown | 4 tasks | 3 files |
| Phase 01 P03 | 12min | 2 tasks | 1 files |

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- Roadmap: CI gate (Phase 1) sequenced first; every later phase depends on a trustworthy gate running against real Postgres.
- Roadmap: Golden files plus fail-fast validation (Phase 2) precede the calculators.py decomposition (Phase 3) so the refactor has a regression net.
- Roadmap: PERF-01 N+1 fixes and PERF-02 IPCC caching grouped with auth hardening (Phase 4), after golden coverage exists to catch data-shape regressions.
- [Phase ?]: Used Error (not Warning) level for both check IDs so manage.py check --deploy fails at its default fail level, per D-11/D-12
- [Phase ?]: Read APP_MODE via os.getenv, not settings.APP_MODE, per Finding 5 (APP_MODE is a plain env var, never assigned as a Django setting)
- [Phase ?]: TEST.NAME on the non-GAE DATABASES branch reads DB_NAME so manage.py test --keepdb reuses the migrated and seeded database (Finding 2, D-05)
- [Phase ?]: Package legitimacy checkpoint approved: bandit==1.9.4 and pip-audit==2.10.1 confirmed via live PyPI verification as PyCQA/pypa canonical releases, neither yanked
- [Phase ?]: Phase 01: Split the 01-03 deploy.yaml diff into two atomic commits along the plan task boundary (test job first, deploy job gating second) even though both tasks touch the same file
- [Phase ?]: Phase 01: APP_MODE stays unset in the CI test job (D-07) since the suite does not need it and setting it to production would fail the smoke check --deploy step on test-env values

### Pending Todos

None yet.

### Blockers/Concerns

- Phase 1 (from research): confirm APP_MODE=test and .env.test loading in CI so migrations run against the test DB, not a fallback SQLite.
- Phase 4 (from research): confirm App Engine worker count, autoscaling, Memorystore/Redis availability, and DRF NUM_PROXIES before wiring shared-cache rate limiting.

### Quick Tasks Completed

| # | Description | Date | Commit | Directory |
|---|-------------|------|--------|-----------|
| 260709-ear | Fix Excel report rice metadata: minor season used hardcoded IPCC default (113 days) instead of the Tier-2 override, and the rice metadata block was unlabeled and misaligned vs other activities | 2026-07-09 | 23ee2769 | [260709-ear-fix-excel-report-rice-metadata-second-cr](./quick/260709-ear-fix-excel-report-rice-metadata-second-cr/) |
| 260716-g2x | Memoize IPCC/ModuleType/StatusType reference lookups and single-Result construction to speed up Excel/PDF report generation | 2026-07-16 | 15790cb0 | [260716-g2x-the-excel-report-generation-is-painfully](./quick/260716-g2x-the-excel-report-generation-is-painfully/) |
| 260716-gu0 | Applied R3: opt-in per-instance Activity module-list memoization plus select_related("status"), shared across the Excel readiness pre-pass/compute and the PDF template context | 2026-07-16 | fe5323fe | [260716-gu0-apply-r3-fetch-modules-once-per-activity](./quick/260716-gu0-apply-r3-fetch-modules-once-per-activity/) |
| 260716-fast | Fix Gemini PR #211 finding: strip empty values from activities query param before pk__in at 4 sites (api+public results/report) | 2026-07-16 | ba719cdb | n/a (inline fast task) |
| 260716-cap | Cap max activities per project to 50 across create, build, and copy paths | 2026-07-16 | eb9011e5 | n/a (inline fast task) |
| 260717-fkc | Report perf round 4: drop 2 redundant deepcopies in Result balance (N1), select_related land_use_change for land modules (N3), batch cold-path cache writes via bulk_update (R6). Researched R4-R8 + new wins; deferred profiling/N2/R5/R8 | 2026-07-17 | a68e9fa8 | [260717-fkc-the-project-report-generation-is-still-q](./quick/260717-fkc-the-project-report-generation-is-still-q/) |
| 20260721-eco | Async report emails the requester a signed 24h download link on completion (tokenized backend URL, no login); cleanup_expired_reports deletes the GCS file + clears gcs_path after 24h; docs + lifecycle-rule backstop | 2026-07-21 | 08258909 | [20260721-async-report-email-link](./quick/20260721-async-report-email-link/) |
| 260723-jas | Feasibility review: migrating the web API from App Engine to Cloud Run. Evaluation only, no code changed. Verdict: feasible and largely de-risked by the existing Cloud Run Job image; sequence behind Secret Manager migration and an FAO IT answer on ingress/domain | 2026-07-23 | (docs) | [260723-jas-cloud-run-migration-feasibility](./quick/260723-jas-cloud-run-migration-feasibility/) |
| 260724-eut | Additive Cloud Run deployment path for review: WhiteNoise static serving, forked web-service Dockerfile, Knative service manifest, review-only GitHub Actions workflow, and operator setup guide. App Engine and existing computation Job untouched | 2026-07-24 | 7dec6f85 | [260724-eut-prepare-the-api-to-be-deployed-to-cloud-](./quick/260724-eut-prepare-the-api-to-be-deployed-to-cloud-/) |
| 260729-exi | Removed the residual Staff auth Group (id=5) and its traces from the review environment DB via cloud-sql-proxy. Inspection found zero linked users, memberships, or invitations; deleted the group row plus its 1253 auth_group_permissions links inside one transaction. All 7 verification checks passed; users and is_staff flags untouched | 2026-07-29 | (docs) | [260729-exi-remove-staff-role-and-membership-traces-](./quick/260729-exi-remove-staff-role-and-membership-traces-/) |
| 260729-k8y | Relabel Inventory IPCC Category names per 1-results-report.xlsx via presentation-layer mapping (api/inventory_labels.py, keyed on module class with Aquaculture overrides for N2O Field/Electricity); wired into module results API and Excel report live+cached paths; ActivityTypes untouched | 2026-07-29 | 63d8b004 | [260729-k8y-relabel-inventory-result-categories-via-](./quick/260729-k8y-relabel-inventory-result-categories-via-/) |
| 260803-gxo | Moved all three GitHub Actions jobs off the self-hosted gcp-temporary label onto GitHub-hosted ubuntu-22.04. The label had registered no runner since 2026-07-30, leaving 22 Deploy runs queued indefinitely including the production push to main. WIF auth and cloud-sql-proxy without --private-ip meant no job depended on running inside GCP; stale self-hosted-runner comments corrected | 2026-08-03 | 0d58b04e | [260803-gxo-move-ci-off-offline-gcp-temporary-self-h](./quick/260803-gxo-move-ci-off-offline-gcp-temporary-self-h/) |
| 260805-l5b | Applied the Dependabot + Semgrep findings CSV: npm audit fix for fast-uri/brace-expansion/postcss (lockfile only, npm audit now clean), bumped httplib2 0.32.0 + pyparsing 3.3.2 + Django 5.2.17, SHA-pinned both docker/setup-buildx-action refs. WeasyPrint held at 68.0 as not-affected (presentational_hints never enabled) with a guard test; the accounts/views.py logger finding was stale on develop | 2026-08-05 | b97b53c6 | [260805-l5b-read-exact-django-webapp-csv-security-fi](./quick/260805-l5b-read-exact-django-webapp-csv-security-fi/) |
| 260805-mmh | Replaced the `json.loads(e.strerror)` idiom in accounts auth error handling with typed FirebaseError exceptions parsed inside FirebaseAuth. Transport failures, non-JSON bodies and unexpected response shapes were turning handled 400s into unhandled 500s on TokenRefreshView. Frontend-visible responses unchanged; 27 DB-free tests added. Flags VerifyUserEmail as a dead AllowAny endpoint that needs auth before its typo is fixed | 2026-08-05 | 1d5c6405 | [260805-mmh-fix-the-foo-json-loads-e-strerror-error-](./quick/260805-mmh-fix-the-foo-json-loads-e-strerror-error-/) |
| 260805-n82 | Audited the 7 remaining open Dependabot alerts (fast-uri x2, brace-expansion x2, postcss on npm; httplib2, django on pip) against the Dependabot API patched versions. All 7 are already patched on develop by 260805-l5b; they stay open only because scanning runs against main, which is 14 commits behind and still pins the vulnerable versions. No code change: every installed version already exceeds first_patched_version. Alerts close when develop reaches main | 2026-08-05 | (docs) | [260805-n82-fix-remaining-dependabot-alerts-fast-uri](./quick/260805-n82-fix-remaining-dependabot-alerts-fast-uri/) |
| 260805-ncv | Fixed the Gemini PR finding in LoginExistingUserView: the orphaned-account cleanup passed user["localId"] to auth.delete_user_account, which posts {"idToken": ...} to the Identity Toolkit accounts:delete endpoint, so Firebase rejected every call and the orphan was never deleted (masked by the best-effort guard, client still saw 404). One-key fix plus 2 DB-free regression tests that drive the branch via post.__wrapped__ to bypass @transaction.atomic. Gemini's suggested diff was mis-anchored and would not have parsed | 2026-08-05 | 8f426740 | [260805-ncv-fix-loginexistinguserview-orphan-cleanup](./quick/260805-ncv-fix-loginexistinguserview-orphan-cleanup/) |
| 260805-nsn | Unblocked PR #265 (review -> main), which was CONFLICTING because review lacked main's 4 CI-runner commits. The org ruleset "FAO Security Checks (review)" forbids direct pushes to review with no bypass, so GitHub's web conflict editor cannot be used; the resolution was made on chore/sync-review-with-main and offered to review as PR #266. Three conflicts: both deploy workflows kept main's corrected Buildx comment plus review's SHA-pinned setup-buildx-action ref (taking main's floating @v3 would have reverted the 260805-l5b security fix), and STATE.md was a keep-both merge. A verify gate asserting gcp-temporary appears nowhere was wrong and was narrowed to runs-on lines, since the label legitimately survives in main's explanatory comments | 2026-08-05 | bce38c33 | [260805-nsn-merge-main-into-review-on-a-sync-branch-](./quick/260805-nsn-merge-main-into-review-on-a-sync-branch-/) |
| 260810-fnr | Cleared the 6 open Dependabot alerts (175-180, all Django) by moving gcp-deployment/cloud-function/requirements.txt off the EOL Django 4.2.30 to 5.2.17. No 4.2.x patch exists, so the 5.2 series was the only escape; DRF 3.16.1, django-filter 24.3, django-cors-headers 4.4.0, django-environ 0.11.2 and PyYAML 6.0.2 came along because their old pins predate Django 5.2 support. Manifest now has zero drift across all 16 packages shared with djangoexact/requirements.txt. The linked dashboard CSV was entirely stale: all 7 of its Dependabot rows are fixed or dismissed on GitHub and all 3 Semgrep rows are already resolved on develop, so no Semgrep work existed | 2026-08-10 | bf788724 | [260810-fnr-fix-dependabot-and-semgrep-security-find](./quick/260810-fnr-fix-dependabot-and-semgrep-security-find/) |

## Deferred Items

Items acknowledged and carried forward from previous milestone close:

| Category | Item | Status | Deferred At |
|----------|------|--------|-------------|
| *(none)* | | | |

## Session Continuity

Last session: 2026-07-09T08:03:04.655Z
Stopped at: Phase 1 executed and verified (human_needed); awaiting first CI run observation
Resume file: .planning/phases/01-ci-test-gate-production-config-guard/01-UAT.md
