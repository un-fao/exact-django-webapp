---
status: testing
phase: 01-ci-test-gate-production-config-guard
source: [01-VERIFICATION.md]
started: 2026-07-09T09:00:00Z
updated: 2026-07-09T09:00:00Z
---

## Current Test

number: 1
name: First PR runs the test job against real Postgres
expected: |
  Open a PR to develop (this phase's branch is a natural candidate). The test job runs:
  Postgres service container healthy, manage.py migrate + load_reference_data + loaddata
  test_seed_data complete, the explicit 38-label suite executes with a plausible test count,
  and load_reference_data visibly takes 30+ seconds in the job log (proof fixtures loaded,
  not a red-herring green). test_reference_bootstrap passes.
awaiting: user response

## Tests

### 1. First PR runs the test job against real Postgres
expected: Test job green on a PR; job log shows migrate, 30s+ load_reference_data, loaddata test_seed_data, and the full explicit-label suite running (not 0 tests); test_reference_bootstrap passes.
result: [pending]

### 2. Security scans execute for real in the same gated job
expected: bandit (HIGH severity threshold) and pip-audit steps both execute against the CI dependency tree and pass (or fail loudly on genuine findings); the negative smoke step proves check --deploy fires under APP_MODE=production (api.E001 trips with DEBUG=True).
result: [pending]

### 3. First push to main is gated end-to-end
expected: deploy job waits on needs: test and starts only after test passes; with GitHub vars.CORS_ALLOWED_ORIGINS configured, manage.py check --deploy passes on real production values BEFORE migrate runs; deploy proceeds. (A deliberately broken test on a throwaway branch push may be used to observe the deploy job being skipped.)
result: [pending]

## Summary

total: 3
passed: 0
issues: 0
pending: 3
skipped: 0
blocked: 0

## Gaps
