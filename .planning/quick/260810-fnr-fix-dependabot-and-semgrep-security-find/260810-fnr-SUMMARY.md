---
phase: quick-260810-fnr
plan: 01
subsystem: infra
tags: [dependabot, django, cloud-function, pip, security]

requires: []
provides:
  - gcp-deployment/cloud-function/requirements.txt moved off end-of-life Django 4.2 to Django 5.2.17
  - Five other drifted pins in that manifest aligned to djangoexact/requirements.txt (the production reference)
  - An in-file comment recording the shared-pin alignment invariant, since dependabot.yml does not watch this path
affects: [security, cloud-function-deploy]

actuals:
  tokens: 333
  tasks: 2
  commits: 2

tech-stack:
  added: []
  patterns:
    - "Shared-pin alignment invariant between two independently deployed requirements.txt manifests, enforced by a runnable drift gate rather than by dependabot.yml (which watches only /djangoexact)."

key-files:
  created: []
  modified:
    - gcp-deployment/cloud-function/requirements.txt

key-decisions:
  - "Targeted Django 5.2.17 (and the five other bumped pins) by copying the exact versions already running in production in djangoexact/requirements.txt, rather than picking new versions independently, so the resulting matrix is proven rather than invented."
  - "Recorded the shared-pin invariant as a comment in the manifest itself (Task 2) instead of a CI check, because dependabot.yml does not watch gcp-deployment/cloud-function and the locked scope was a single file."

patterns-established:
  - "When two requirements.txt files intentionally overlap, treat one as canonical and record that relationship in-file plus prove it with a parseable drift gate."

requirements-completed: [DEPENDABOT-175, DEPENDABOT-176, DEPENDABOT-177, DEPENDABOT-178, DEPENDABOT-179, DEPENDABOT-180]

coverage:
  - id: D1
    description: "Six Dependabot alerts (175-180) on gcp-deployment/cloud-function/requirements.txt cleared by moving Django from 4.2.30 to 5.2.17, above every advisory's fixed floor."
    requirement: "DEPENDABOT-175"
    verification:
      - kind: other
        ref: "python3 pip-requirements parse gate (Task 1 automated verify) — asserts all six pins exact"
        status: pass
    human_judgment: true
    rationale: "Alerts auto-close only once develop reaches main (GitHub scans the default branch); the parse gate proves the pin is correct but cannot itself confirm GitHub closed the alert. The plan's Task 1 human-check also flags that the cloud function's main.py is absent from this checkout and untestable here, so a human must confirm one permutation job in the review environment before production."
  - id: D2
    description: "Zero residual drift across all 16 packages shared between the cloud-function manifest and djangoexact/requirements.txt, proving the six-package matrix was complete."
    verification:
      - kind: other
        ref: "python3 drift-comparison gate (Task 2 automated verify) — printed shared=16 drifted=0"
        status: pass
    human_judgment: false

duration: 6min
completed: 2026-08-10
status: complete
---

# Quick Task 260810-fnr: Fix Dependabot and Semgrep Security Findings Summary

**Moved `gcp-deployment/cloud-function/requirements.txt` off end-of-life Django 4.2.30 to Django 5.2.17, closing six open Dependabot alerts and eliminating all drift against the production manifest.**

## Performance

- **Duration:** 6 min
- **Started:** 2026-08-10T09:20:00Z
- **Completed:** 2026-08-10T09:26:35Z
- **Tasks:** 2
- **Files modified:** 1

## Accomplishments
- Bumped six pins in `gcp-deployment/cloud-function/requirements.txt` (Django, djangorestframework, django-filter, django-cors-headers, django-environ, PyYAML) to the exact versions already running in production in `djangoexact/requirements.txt`, clearing Dependabot alerts 175 through 180.
- Recorded an in-file alignment invariant comment noting that this manifest is not watched by `.github/dependabot.yml` and must be kept in sync with `djangoexact/requirements.txt` by review.
- Proved zero residual drift across all 16 shared packages with a runnable gate, confirming the six-package matrix from CONTEXT.md was the complete set.

## Task Commits

Each task was committed atomically:

1. **Task 1: Move the cloud function manifest to the Django 5.2 series** - `f50cf483` (fix)
2. **Task 2: Record the alignment invariant and prove zero residual drift** - `bf788724` (docs)

_No plan-metadata-only commit was needed beyond these two; both are the plan's full deliverable._

## Files Created/Modified
- `gcp-deployment/cloud-function/requirements.txt` - Six pins bumped off Django 4.2.30 to 5.2.17 (plus djangorestframework, django-filter, django-cors-headers, django-environ, PyYAML); comment header extended with the shared-pin alignment invariant.

## Decisions Made
- Copied every target version verbatim from `djangoexact/requirements.txt` rather than choosing new versions, since that file already runs this exact set against Django 5.2.17 in production.
- Left the drift invariant as an in-file comment rather than a checked-in test, since the plan was locked to a single modified file (`gcp-deployment/cloud-function/requirements.txt`).

## Deviations from Plan

None - plan executed exactly as written. Both automated verify gates were red before the change (per the planner's proof) and green after:

**Task 1 gate output:**
```
PARSED 18 requirements
ALL SIX PINS OK
```

**Task 2 gate output:**
```
shared=16 drifted=0
```

## Issues Encountered
`git add gcp-deployment/cloud-function/requirements.txt` printed a gitignore warning both times, because the `gcp-deployment/` directory as a whole is gitignored while this one file inside it is deliberately tracked. The warning did not block staging; the file staged and committed correctly both times, confirmed via `git diff --cached --stat` and the resulting commits. No fix needed, not a deviation from the plan.

## User Setup Required
**Before this reaches production:** deploy the cloud function to the review environment and confirm one permutation job completes successfully. This is a Django 4.2 to 5.2 major version upgrade applied to function source (`main.py`) that is gitignored and absent from this checkout, so the jump could not be exercised here. The code the function imports (`minitool`, `PermutationComputer`) already runs under Django 5.2.17 in the main app, which bounds the risk, and rollback is a one-line revert of commit `f50cf483`.

## Notes carried from the plan (out of scope, no action taken)
- Adding `/gcp-deployment/cloud-function` to `.github/dependabot.yml` was considered and deliberately skipped: `open-pull-requests-limit: 0` disables version-update PRs repo-wide as of commit `581091fd`, and security alerts already fire for unwatched manifests regardless.
- A checked-in regression test asserting the drift invariant (Task 2's gate, made permanent in CI) is a worthwhile follow-up quick task. It was out of scope here because it needs a new file under `djangoexact/api/tests/`, and this plan was locked to one modified path.
- The six alerts (175-180) stay open on `develop` until `develop` reaches `main`, because Dependabot scans the default branch only. That lag is expected, not a failure, and matches the same pattern documented for prior quick task `260805-n82`.

## Next Phase Readiness
- No outstanding Dependabot or Semgrep work remains per the locked CONTEXT.md reconciliation: all CSV rows were already closed by `260805-l5b`, all Semgrep findings were already resolved on `develop`, and this task's six alerts have no affected pin left in the repo.
- Blocked on human verification (see User Setup Required) before this manifest is safe to deploy to production.

---
*Quick task: 260810-fnr*
*Completed: 2026-08-10*
