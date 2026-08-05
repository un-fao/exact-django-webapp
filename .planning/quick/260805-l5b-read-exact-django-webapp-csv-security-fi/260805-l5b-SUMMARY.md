---
phase: quick-260805-l5b
plan: 01
subsystem: security
tags: [npm-audit, pip, requirements.txt, github-actions, weasyprint, dependabot, semgrep]

requires: []
provides:
  - Zero remaining npm audit vulnerabilities in djangoexact (fast-uri, brace-expansion, postcss transitive dev deps)
  - httplib2 0.32.0, pyparsing 3.3.2 and Django 5.2.17 pinned in requirements.txt
  - Both docker/setup-buildx-action references SHA-pinned in .github/workflows
  - DB-free regression test guarding the WeasyPrint CVE-2026-49452 not-affected exemption
affects: [ci, deploy, reports]

actuals:
  tokens: 2055
  tasks: 4
  commits: 4

tech-stack:
  added: []
  patterns: []

key-files:
  created:
    - djangoexact/api/tests/test_weasyprint_presentational_hints_guard.py
  modified:
    - djangoexact/package-lock.json
    - djangoexact/requirements.txt
    - .github/workflows/deploy.yaml
    - .github/workflows/deploy-cloudrun.yaml

key-decisions:
  - "npm audit fix --package-lock-only kept package.json byte-identical; only lockfile-resolved transitive entries (fast-uri, brace-expansion, postcss, and postcss's own nanoid requirement) moved"
  - "httplib2 and pyparsing both bumped together since httplib2 0.32.0 declares pyparsing<4,>=3.1; neither package is imported anywhere in djangoexact/"
  - "Django bumped to 5.2.17 (not just 5.2.15) to pick up all LTS security fixes through the current patch while staying inside the 5.2 line"
  - "docker/setup-buildx-action pinned to v3.12.0's SHA rather than jumping to v4, matching the plan's minimal-change directive"
  - "weasyprint stays at 68.0; CVE-2026-49452 only fires when presentational_hints is enabled, which this codebase never does, so the fix is a documented exemption plus a regression guard test instead of a major-version bump"
  - "Finding D (stale 'Token refresh failed' Semgrep hit) required no task; it was already removed from accounts/views.py on develop and was a false positive besides"

patterns-established: []

requirements-completed: [DEP-NPM-01, DEP-PY-01, CI-PIN-01, WEASY-01]

coverage:
  - id: D1
    description: "npm audit reports zero vulnerabilities after resolving fast-uri, brace-expansion and postcss in the lockfile, with package.json unchanged"
    requirement: "DEP-NPM-01"
    verification:
      - kind: other
        ref: "cd djangoexact && npm audit --audit-level=low"
        status: pass
    human_judgment: false
  - id: D2
    description: "requirements.txt pins httplib2 0.32.0, pyparsing 3.3.2 and Django 5.2.17; weasyprint stays at 68.0 with a CVE-2026-49452 exemption comment"
    requirement: "DEP-PY-01"
    verification:
      - kind: other
        ref: "grep -c '^httplib2==0.32.0$|^pyparsing==3.3.2$|^Django==5.2.17$|^weasyprint==68.0$|CVE-2026-49452' djangoexact/requirements.txt"
        status: pass
    human_judgment: false
  - id: D3
    description: "Both docker/setup-buildx-action uses: references are SHA-pinned; zero unpinned uses: references remain in .github/workflows"
    requirement: "CI-PIN-01"
    verification:
      - kind: other
        ref: "grep -rEn 'uses:[[:space:]]+[^ ]+@v[0-9]' .github/workflows/ | wc -l"
        status: pass
    human_judgment: false
  - id: D4
    description: "DB-free SimpleTestCase guards the WeasyPrint not-affected claim (scans >200 files, no offending presentational_hints usage found)"
    requirement: "WEASY-01"
    verification:
      - kind: unit
        ref: "djangoexact/api/tests/test_weasyprint_presentational_hints_guard.py#WeasyPrintPresentationalHintsGuardTests"
        status: pass
    human_judgment: false
  - id: D5
    description: "Dismiss the weasyprint 68.0 Dependabot alert (CVE-2026-49452) in GitHub Security as not affected"
    verification: []
    human_judgment: true
    rationale: "Dashboard action on GitHub Dependabot; cannot be performed or verified via tooling and requires a human with repo admin access"

duration: 15min
completed: 2026-08-05
status: complete
---

# Quick Task 260805-l5b: Security Findings Remediation Summary

**Resolved all four actionable CSV findings: npm lockfile advisories, three Python pin bumps with a documented WeasyPrint exemption, two SHA-pinned GitHub Actions, and a regression test protecting the exemption.**

## Performance

- **Duration:** 15 min (approximate)
- **Tasks:** 4
- **Files modified:** 5 (4 modified, 1 created)

## Accomplishments

- `djangoexact/package-lock.json` moved fast-uri, brace-expansion and postcss (plus postcss's transitive nanoid requirement) to non-vulnerable versions via `npm audit fix --package-lock-only`; `package.json` untouched; `npm audit` now reports zero vulnerabilities
- `djangoexact/requirements.txt` bumped httplib2 to 0.32.0 (CVE-2026-59939), pyparsing to 3.3.2 (forced constraint), and Django to 5.2.17 (STARTTLS CVE plus five further LTS security fixes), and gained a four-line comment documenting why weasyprint stays at 68.0
- `.github/workflows/deploy.yaml` and `.github/workflows/deploy-cloudrun.yaml` both now pin `docker/setup-buildx-action` to commit `8d2750c68a42422c14e847fe6c8ac0403b4cbd6f` (v3.12.0) instead of the mutable `@v3` tag; zero unpinned `uses:` references remain in the repo
- New `djangoexact/api/tests/test_weasyprint_presentational_hints_guard.py`, a DB-free `SimpleTestCase` that scans the Django tree for any use of `presentational_hints` (excluding itself and vendored/generated directories), asserting both that none exists and that the scan actually visited a meaningful number of files (>200), so the not-affected claim cannot silently rot

## Task Commits

Each task was committed atomically:

1. **Task 1: Resolve the three npm transitive advisories in the lockfile only** - `2e91b058` (fix)
2. **Task 2: Bump the vulnerable Python pins and document the WeasyPrint exemption** - `b9b4b16c` (fix)
3. **Task 3: SHA-pin the two remaining unpinned GitHub Action references** - `75a26938` (fix)
4. **Task 4: Add a DB-free guard test protecting the WeasyPrint not-affected claim** - `b97b53c6` (test)

## Files Created/Modified

- `djangoexact/package-lock.json` - fast-uri, brace-expansion, postcss (and postcss's nanoid requirement) moved to patched resolved versions
- `djangoexact/requirements.txt` - httplib2, pyparsing and Django pins bumped; four-line CVE-2026-49452 exemption comment added above the weasyprint pin
- `.github/workflows/deploy.yaml` - `docker/setup-buildx-action` SHA-pinned (line 350)
- `.github/workflows/deploy-cloudrun.yaml` - `docker/setup-buildx-action` SHA-pinned (line 188)
- `djangoexact/api/tests/test_weasyprint_presentational_hints_guard.py` (new) - DB-free regression guard for the WeasyPrint exemption

## Decisions Made

- Grouped commits by remediation surface (npm lockfile, Python pins, workflow pinning, WeasyPrint guard test) per the plan's Claude's Discretion note, rather than one commit per CVE
- Kept httplib2 and pyparsing pinned rather than removing them even though both are unused in the codebase, so pip dependency resolution stays deterministic
- Django went to 5.2.17 rather than stopping at 5.2.15 (the minimum needed for the CSV's STARTTLS finding), picking up all subsequent 5.2 LTS security patches while staying inside the LTS line
- WeasyPrint stays at 68.0; the guard test enforces the not-affected claim mechanically instead of relying on a comment alone

## Deviations from Plan

None - plan executed exactly as written. Both no-code-change items called out in the plan's `<output>` section were confirmed and required no code changes:

1. **Finding D is stale.** The Semgrep hit "Token refresh failed: %s" at `accounts/views.py:263` exists only on `origin/main`. `git grep "Token refresh failed" HEAD` on `develop` returns nothing; `TokenRefreshView` in the current `accounts/views.py` (239 lines) has no such logger call. It was also a false positive on `origin/main`: the flagged string is a log message, and the interpolated value was an exception object, not a hardcoded secret. Resolved-on-develop; no task covers it and none was needed.
2. **WeasyPrint Dependabot alert (CVE-2026-49452) needs manual dismissal.** No code path in this codebase enables `presentational_hints` (verified by grep and now enforced by the new guard test), so the vulnerable path is unreachable. This cannot be dismissed via tooling; see "User Setup Required" below.

## Issues Encountered

None. All four automated verify gates specified in the plan passed on the first attempt:
- `npm audit --audit-level=low` exits 0 with zero vulnerabilities
- All five expected files (and only those five) appear in `git diff --name-only origin/develop...HEAD` relative to this plan's changes (a sixth file, `djangoexact/scripts/foo.py`, also appears in that diff, but it belongs to a prior unrelated commit `4958d22c` that was already on local `develop` before this plan started and is not part of this plan's `files_modified`)
- `manage.py test api.tests.test_weasyprint_presentational_hints_guard api.tests.test_production_config_check` reports `Ran 7 tests` / `OK` with no database
- Both workflow files parse as YAML and zero unpinned `uses:@vN` references remain
- No em-dashes found in any changed file or in any commit message

## User Setup Required

**One manual GitHub Dependabot action is required and cannot be performed by tooling:**

- **Service:** GitHub Dependabot
- **Why:** The WeasyPrint alert (CVE-2026-49452) must be dismissed as not affected by a human; there is no code change for it, since the vulnerable `presentational_hints` code path is never reached by this codebase.
- **Action:** In the GitHub repo, go to Security -> Dependabot alerts, find the weasyprint 68.0 alert for CVE-2026-49452, and dismiss it with reason "Vulnerable code is not actually used". Cite `djangoexact/requirements.txt`'s exemption comment (above the `weasyprint==68.0` pin) and `djangoexact/api/tests/test_weasyprint_presentational_hints_guard.py` as the supporting evidence.

## Next Phase Readiness

- All four actionable CSV findings are closed; the CSV's remaining rows (Finding D, and the WeasyPrint alert pending manual dismissal) are both accounted for above.
- No blockers for further work. The four commits are self-contained and independent of any in-flight phase work.

---
*Quick task: 260805-l5b*
*Completed: 2026-08-05*

## Self-Check: PASSED

All created/modified files confirmed present on disk; all four task commit hashes (2e91b058, b9b4b16c, 75a26938, b97b53c6) confirmed present in git log.
