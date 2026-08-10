# Quick Task 260810-fnr: Fix dependabot and semgrep security findings - Context

**Gathered:** 2026-08-10
**Status:** Ready for planning

<domain>
## Task Boundary

Fix all issues surfaced by Dependabot and Semgrep for `un-fao/exact-django-webapp`.

The user pointed at the FAO GitHub security dashboard
(`github-security-user-dashboard-...run.app/inventory?repo=un-fao/exact-django-webapp`)
and supplied its CSV export at `~/Downloads/gh_security_findings_extraction.csv`.

**Critical scoping fact: that CSV is stale. It is not the work list.**
The orchestrator reconciled every CSV row against GitHub's live alert API before
planning. The reconciliation is recorded below and is LOCKED - do not re-derive it,
and do not plan any task off the CSV rows.

</domain>

<decisions>
## Reconciliation of the dashboard CSV against live GitHub state

The dashboard scans the repo default branch `main`, which trails `develop` by 11
commits, so it reports findings that `develop` already fixed. All 11 CSV rows are
already closed:

### Dependabot rows in the CSV (7) - ALL already closed on GitHub
Verified via `gh api repos/un-fao/exact-django-webapp/dependabot/alerts`:

| CSV row | Live state | Evidence |
|---|---|---|
| fast-uri x2 (package-lock.json) | `fixed` | fixed_at 2026-08-05T15:33:24Z |
| brace-expansion x2 (package-lock.json) | `fixed` | fixed_at 2026-08-05T15:33:24Z |
| PostCSS (package-lock.json) | `fixed` | fixed_at 2026-08-05T15:33:24Z |
| httplib2 (requirements.txt) | `fixed` | fixed_at 2026-08-05T15:33:25Z |
| Django STARTTLS (requirements.txt) | `fixed` | fixed_at 2026-08-05T15:33:25Z |
| WeasyPrint CSS injection | `dismissed` | dismissed_reason `tolerable_risk` |

These were closed by prior quick task `260805-l5b`. No action.

### Semgrep rows in the CSV (3) - ALL already resolved on develop
| CSV row | Verification on develop | Verdict |
|---|---|---|
| mutable action ref, `deploy-cloudrun.yaml:195` | `grep -rEn 'uses:[[:space:]]+[^ ]+@(v[0-9]\|main\|master)' .github/workflows/` returns nothing; all 13 `uses:` refs are 40-char SHA-pinned | Resolved |
| mutable action ref, `deploy.yaml:365` | same as above | Resolved |
| logger with hardcoded secret `"Token refresh failed: %s"`, `accounts/views.py:263` | That exact string does not exist on develop. `accounts/views.py:267` has `fallback="Token refresh failed"` as a kwarg to `firebase_error_response`, which is a `return`, not a logger call, so the rule cannot fire. Was a false positive on `main` anyway (the interpolated value was an exception object, not a credential) | Resolved + false positive |

**Conclusion: there is no Semgrep work in this task.** Semgrep findings will clear
on their own when `develop` reaches `main`. Do not plan Semgrep tasks. Do not
re-run or install Semgrep.

</decisions>

<specifics>
## The actual work: 6 open Dependabot alerts

These are the ONLY currently-open alerts (`state=open` from the live API). They do
not appear in the CSV at all because they were created 2026-08-09, after the
dashboard's last scan. Every one is Django, in the same manifest:

**File:** `gcp-deployment/cloud-function/requirements.txt`
**Current pin:** `Django==4.2.30`

| Alert | Severity | GHSA | Needs |
|---|---|---|---|
| 180 | low | GHSA-h7pc-vwp9-298g | signed cookies vulnerable to salt namespace collisions | >= 5.2.15 |
| 179 | low | GHSA-8cjm-8mp7-r2xf | UpdateCacheMiddleware may disclose cached responses (case-sensitive Cache-Control) | >= 5.2.15 |
| 178 | medium | GHSA-8qcx-xf44-272x | DomainNameValidator permits newlines enabling HTTP header injection | >= 5.2.16 |
| 177 | low | GHSA-3h9f-r86x-qvjx | cache middleware may expose private responses when unrelated cookies present | >= 5.2.16 |
| 176 | medium | GHSA-crhf-3pfg-w68w | GDALRaster may over-read heap memory when constructed from bytes | >= 5.2.16 |
| 175 | low | GHSA-923m-gv2p-w5qp | has_vary_header may expose cached responses when Vary contains whitespace | >= 5.2.15 |

**There is no 4.2.x fix.** Django 4.2 LTS is end-of-life; the advisories list
patched versions only for the 5.2 and 6.0 series (e.g. GHSA-8qcx-xf44-272x:
`< 5.2.16 -> 5.2.16`, `>= 6.0.0, < 6.0.7 -> 6.0.7`). Clearing all six therefore
requires moving this manifest to **Django >= 5.2.16**.

### Recommended target: align with the main app

`djangoexact/requirements.txt` already runs Django 5.2.17 in production, so pin the
cloud function to the same versions rather than inventing a new matrix. Where the
two manifests overlap, the main app is the reference:

| Package | cloud-function (now) | djangoexact (target) | Why it must move |
|---|---|---|---|
| Django | 4.2.30 | **5.2.17** | The fix itself; >= 5.2.16 required |
| djangorestframework | 3.15.2 | **3.16.1** | 3.15.2 predates Django 5.2 support; DRF added it in 3.16.0 |
| django-filter | 23.5 | **24.3** | 23.5 caps at Django 5.0 |
| django-cors-headers | 4.0.0 | **4.4.0** | 4.0.0 caps at Django 4.2 |
| django-environ | 0.10.0 | **0.11.2** | Alignment |
| PyYAML | 6.0 | **6.0.2** | Alignment |

Already identical in both manifests, leave untouched: `psycopg2-binary==2.9.6`,
`pandas==2.0.1`, `numpy==1.24.3`, `tqdm==4.67.1`, `python-dotenv==1.2.2`,
`python-dateutil==2.8.2`, `pytz==2023.3`, `requests==2.33.0`, `urllib3==2.7.0`,
`google-cloud-storage==2.19.0`.
Not in the main app, leave untouched: `functions-framework==3.*`,
`google-cloud-logging==3.8.0`.

</specifics>

<constraints>
## Constraints the planner must respect

- **The cloud function source code is NOT in this repo.** `gcp-deployment/` is
  gitignored (root `.gitignore:146`); only two files are tracked:
  `gcp-deployment/.gitignore` and `gcp-deployment/cloud-function/requirements.txt`.
  `main.py` is absent from this checkout. So the change cannot be verified by
  importing or running the function, and no import-site updates are possible or
  needed. Historical note (`docs/superpowers/plans/2026-04-15-minitool-sqlite-to-postgres.md:847`):
  the function imports `minitool` and uses `PermutationComputer`.
- **Verification is limited to the manifest itself.** There is no Postgres/Docker
  in this sandbox and the function's code is absent, so the realistic gate is that
  the file parses as valid pip requirements and the pins say what they should. Do
  not plan a task that claims to run the cloud function.
- Do not touch `djangoexact/requirements.txt` or `djangoexact/package-lock.json` -
  both are already fully patched.
- `.github/dependabot.yml` only watches `/djangoexact` for pip and npm. It does not
  watch `/gcp-deployment/cloud-function`, which is why this manifest drifted to an
  EOL Django. Note that adding it would yield nothing today because
  `open-pull-requests-limit: 0` disables version-update PRs repo-wide (commit
  581091fd), and security alerts already fire for untracked manifests regardless.
  Mention in the summary; do not treat as a required task.
- Project rule: never use em-dashes anywhere in the repo, including commit messages.
- Conventional commits, atomic per task. Work stays on `develop`, matching how
  prior quick tasks (`260805-l5b`) landed.

</constraints>

<canonical_refs>
## Canonical References

- Live alert state: `gh api repos/un-fao/exact-django-webapp/dependabot/alerts`
  (authoritative; the dashboard is a stale mirror)
- GitHub code scanning API is disabled for this repo ("Advanced Security must be
  enabled"), so the dashboard's Semgrep data comes from its own scanner and cannot
  be queried. The dashboard itself is behind Google IAP and returns 401 to a
  `gcloud auth print-identity-token` bearer, so it is only readable in a browser.
- Prior remediation: `.planning/quick/260805-l5b-read-exact-django-webapp-csv-security-fi/260805-l5b-SUMMARY.md`

</canonical_refs>
