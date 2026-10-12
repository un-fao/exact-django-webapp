# Quick Task 260805-l5b: Apply security findings from exact-django-webapp.csv - Context

**Gathered:** 2026-08-05
**Status:** Ready for planning

<domain>
## Task Boundary

Read `/home/sirvosterzo/Downloads/exact-django-webapp.csv` (11 security findings: 7 Dependabot,
3 Semgrep, 1 low Dependabot) and apply the necessary remediations to the repo on branch `develop`.

Scope is limited to the findings in that CSV. No API contract changes, no calculation changes.
</domain>

<verified_findings>
## Finding triage (verified against the working tree, 2026-08-05)

The CSV was scanned against `origin/main`. Line numbers do not match `develop`, so every finding
was re-located before triage.

### A. npm transitive dev dependencies (`djangoexact/package-lock.json`)

`npm audit` confirms 3 vulnerable packages, all transitive dev deps, all `fixAvailable: true`
with no breaking-change flag. `npm audit fix --package-lock-only` resolves all three.

| Package | Installed | Vulnerable range | Advisories |
|---|---|---|---|
| `fast-uri` | 3.1.2 | 3.0.0 - 3.1.4 | GHSA-v2hh-gcrm-f6hx, GHSA-7p8r-x3mc-p8w7, GHSA-4c8g-83qw-93j6 |
| `brace-expansion` | 2.1.0 | 2.0.0 - 2.1.3 | GHSA-3jxr-9vmj-r5cp, GHSA-mh99-v99m-4gvg, GHSA-rgw5-rvv9-x895 |
| `postcss` | 8.5.15 | <=8.5.22 | GHSA-r28c-9q8g-f849, GHSA-fxqj-rqcc-2cmp |

Note: the live `npm audit` reports **more** advisories than the CSV (a third `brace-expansion` DoS
and a second `fast-uri` host-confusion), so the CSV is already slightly stale. Fixing to current
covers all of them. Direct deps in `package.json` are unchanged: only the lockfile moves.

### B. Python dependencies (`djangoexact/requirements.txt`)

| Package | Pinned | Action | Rationale |
|---|---|---|---|
| `httplib2` | 0.22.0 | -> `0.32.0` | CVE-2026-59939 decompression bomb; fixed in 0.32.0 (OSV). |
| `pyparsing` | 3.0.9 | -> `3.3.2` | Forced: httplib2 0.32.0 requires `pyparsing<4,>=3.1`. |
| `Django` | 5.2.14 | -> `5.2.17` | CVE-2026-7666 STARTTLS (fixed 5.2.15). 5.2.17 is the current 5.2 LTS patch and also picks up CVE-2026-35193/48587/6873/8404 (5.2.15) and CVE-2026-48588/53877/53878 (5.2.16). Patch-level within LTS. |
| `weasyprint` | 68.0 | **no change** | See decision below. |

Neither `httplib2` nor `pyparsing` is imported anywhere in `djangoexact/` (verified by grep) --
they are vestigial transitive pins, so the blast radius of both bumps is low.

### C. Semgrep: unpinned GitHub Action references

Real and actionable. Every other `uses:` in the repo is already SHA-pinned; exactly two are not:

- `.github/workflows/deploy-cloudrun.yaml:188` -> `docker/setup-buildx-action@v3`
- `.github/workflows/deploy.yaml:350` -> `docker/setup-buildx-action@v3`

The `v3` tag currently resolves to commit `8d2750c68a42422c14e847fe6c8ac0403b4cbd6f` (= v3.12.0,
released 2025-12-19). Pin to that SHA. Do **not** jump to v4.2.0: pinning the already-in-use major
is the minimal change that closes the finding without altering build behaviour. Match the existing
in-repo comment style, e.g. `actions/checkout@11d5960a326750d5838078e36cf38b85af677262 # v4.4.0`.

### D. Semgrep: "Token refresh failed: %s" logger (`djangoexact/accounts/views.py:263`)

**Stale finding -- no change required.** The flagged statement exists on `origin/main`
(`accounts/views.py:243` and `:263`) but was removed on `develop`. `git grep "Token refresh failed" HEAD`
returns nothing, and `develop`'s `accounts/views.py` is 239 lines with no logger call in
`TokenRefreshView` (lines 214-239). It was also a Semgrep false positive: `"Token refresh failed: %s"`
is a log message, not a hardcoded secret, and the interpolated value was an exception object.

Do not invent a change for this. Record it as resolved-on-develop in the summary.
</verified_findings>

<decisions>
## Implementation Decisions

### WeasyPrint (CVE-2026-49452, medium) -- LOCKED: stay on 68.0, document as not-affected

The advisory only fires when `presentational_hints=True` is passed to WeasyPrint. Grep confirms
the flag is never set anywhere in `djangoexact/`; all three call sites are plain
`HTML(string=html).write_pdf()`:

- `djangoexact/api/views.py:1441-1443`
- `djangoexact/api/services/report_jobs.py:60-62`
- `djangoexact/public/views.py:208-209`

WeasyPrint's default for `presentational_hints` is `False`, so the vulnerable code path is
unreachable. The only fix version is 69.0, a major bump that also moves pydyf, tinycss2,
cssselect2, tinyhtml5 and fonttools -- unacceptable churn under the PDF reporting layer for an
unreachable vuln.

Required work:
1. Keep `weasyprint==68.0` pinned.
2. Add a short comment above the pin in `requirements.txt` recording the CVE, why it is not
   applicable, and the condition that would change that (any call passing `presentational_hints=True`).
3. Add a guard test that asserts no source file under `djangoexact/` enables `presentational_hints`,
   so the not-affected claim cannot silently rot. It must be a `SimpleTestCase` (no DB) so it runs
   in the constrained local environment.
4. The Dependabot alert should be dismissed as "not affected" -- note this in the summary as a
   manual follow-up for the user; do not attempt to dismiss it via tooling.

### httplib2 -- LOCKED: bump both httplib2 and pyparsing

`httplib2==0.32.0` and `pyparsing==3.3.2`. Both are unused vestigial pins; keep them pinned rather
than removing them, so pip resolution stays deterministic.

### Django -- go to 5.2.17, not 5.2.15

The CSV only names the STARTTLS CVE (fixed in 5.2.15), but 5.2.16 and 5.2.17 carry six further
security fixes. Staying on the 5.2 LTS line means no framework-level breaking changes.

### Claude's Discretion

- Commit granularity: group by remediation surface (npm lockfile / Python pins / workflow pinning /
  WeasyPrint guard) rather than one commit per CVE.
- Exact wording of the requirements.txt comment and the guard test's assertion message.
</decisions>

<constraints>
## Environment and repo constraints

- Local sandbox has **no Postgres and no Docker**. There is a working virtualenv at the repo root
  (`.venv`). DB-free checks that DO work locally: `.venv/bin/python -m py_compile`, YAML/JSON parse,
  and `cd djangoexact && ../.venv/bin/python manage.py test <label>` for `SimpleTestCase` suites.
  Anything touching the DB (migrate, full suite) must be left to CI.
- `npm` and network access both work locally; `npm audit fix --package-lock-only` was dry-run
  successfully and reports all 3 issues fixable.
- Do NOT run a plain `npm install` that rewrites unrelated lockfile entries. Use
  `npm audit fix --package-lock-only` so only the vulnerable transitive entries move and
  `package.json` stays untouched.
- Do NOT `pip install` the bumped Python pins into `.venv` -- the sandbox cannot validate them
  meaningfully and it would churn the local env. Editing `requirements.txt` is the deliverable;
  CI/deploy resolves it.
- The CI `test` job in `.github/workflows/deploy.yaml` is currently disabled via `if: false` and
  `pip-audit` runs with `continue-on-error: true`. Do not change either as part of this task.
- Project rule: **never use em-dashes** anywhere in this repo, including commit messages,
  comments and docs.
- Conventional commits, `fix(deps):` / `fix(ci):` / `test(...)` scopes. Feature branch off
  `develop`; this task runs directly on `develop`.
</constraints>

<canonical_refs>
## Canonical References

- Source CSV: `/home/sirvosterzo/Downloads/exact-django-webapp.csv` (11 rows, header + 11 findings)
- OSV API confirmations for httplib2 / weasyprint / Django fixed versions
- `npm audit --json` output from `djangoexact/` for the three npm advisories
- GitHub API: `docker/setup-buildx-action` tag `v3` -> `8d2750c68a42422c14e847fe6c8ac0403b4cbd6f` (v3.12.0)
</canonical_refs>
