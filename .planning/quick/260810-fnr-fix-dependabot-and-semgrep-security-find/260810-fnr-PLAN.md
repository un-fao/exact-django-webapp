---
phase: quick-260810-fnr
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - gcp-deployment/cloud-function/requirements.txt
autonomous: true
requirements:
  - DEPENDABOT-175
  - DEPENDABOT-176
  - DEPENDABOT-177
  - DEPENDABOT-178
  - DEPENDABOT-179
  - DEPENDABOT-180

estimate:
  tokens: 26000
  raw_tokens: 20000
  tasks: 2
  confidence: low

must_haves:
  truths:
    - The cloud function manifest resolves to a Django version above the fixed version of all six open advisories, so alerts 175 through 180 have no affected pin left to report.
    - The manifest declares no dependency that caps below Django 5.2, so the pinned set is internally installable rather than merely patched.
    - Every package shared with djangoexact/requirements.txt is pinned to the identical version, proving no seventh package drifted unnoticed.
    - The manifest still parses as valid PEP 508 pip requirements after the edit.
  artifacts:
    - gcp-deployment/cloud-function/requirements.txt
  key_links:
    - six new pins to the advisory floor of Django 5.2.16 recorded in CONTEXT.md
    - cloud-function shared pins to djangoexact/requirements.txt shared pins
---

<objective>
Clear the six open Dependabot alerts (175 through 180) by moving
`gcp-deployment/cloud-function/requirements.txt` off the end-of-life `Django 4.2`
series onto the Django 5.2 series already running in production, and bring the
five other drifted shared pins along so the resulting set actually installs.

Purpose: Django 4.2 LTS is end of life. All six advisories publish patched
versions only for the 5.2 and 6.0 series, so there is no 4.2.x patch and no
in-series escape. This manifest is the last place in the repo still pinning a
vulnerable Django.

Output: one modified file, two atomic commits on `develop`.

Scope notes carried from CONTEXT.md (locked, do not re-derive):
- There is no Semgrep work. All three Semgrep rows are verified resolved on
  `develop`. Do not plan around, install, or run Semgrep.
- The dashboard CSV is stale. All 11 of its rows are already closed or dismissed.
  Do not work from the CSV.
- CONTEXT.md records its decisions as reconciliation tables rather than numbered
  `D-NN` identifiers, so tasks below cite the Dependabot alert IDs and the
  CONTEXT.md package matrix instead.
</objective>

<execution_context>
@$HOME/.claude/gsd-core/workflows/execute-plan.md
@$HOME/.claude/gsd-core/templates/summary.md
</execution_context>

<context>
@.planning/quick/260810-fnr-fix-dependabot-and-semgrep-security-find/260810-fnr-CONTEXT.md
@gcp-deployment/cloud-function/requirements.txt
@djangoexact/requirements.txt
</context>

<tasks>

<task type="tracer">
  <name>Task 1: Move the cloud function manifest to the Django 5.2 series</name>
  <files>gcp-deployment/cloud-function/requirements.txt</files>
  <precondition>Working tree is on branch `develop` and clean, matching how quick task 260805-l5b landed.</precondition>
  <action>
Edit exactly six pinned version numbers in
`gcp-deployment/cloud-function/requirements.txt`. Change only the version on the
right side of each `==`. Do not add, remove, reorder, or reword any line, and do
not touch the existing section comments in this task.

| Package | From | To | Why it moves |
|---|---|---|---|
| Django | 4.2.30 | 5.2.17 | The fix itself. Advisories 178, 177 and 176 need 5.2.16 or above; 180, 179 and 175 need 5.2.15 or above. 5.2.17 is the version already in production in `djangoexact/requirements.txt`. |
| djangorestframework | 3.15.2 | 3.16.1 | 3.15.2 predates Django 5.2 support, which DRF added in 3.16.0. Leaving it would break the function. |
| django-filter | 23.5 | 24.3 | 23.5 caps at Django 5.0. |
| django-cors-headers | 4.0.0 | 4.4.0 | 4.0.0 caps at Django 4.2. |
| django-environ | 0.10.0 | 0.11.2 | Alignment with the main app. |
| PyYAML | 6.0 | 6.0.2 | Alignment with the main app. |

Every target version is taken verbatim from `djangoexact/requirements.txt`, which
already runs this exact set against Django 5.2.17 in production, so the matrix is
proven rather than invented.

Leave every other line untouched. Already identical in both manifests:
psycopg2-binary, pandas, numpy, tqdm, python-dotenv, python-dateutil, pytz,
requests, urllib3, google-cloud-storage. Present only here and out of scope:
functions-framework, google-cloud-logging.

Do not modify `djangoexact/requirements.txt` or `djangoexact/package-lock.json`.
Both are already fully patched, and touching either would re-open settled work.

Commit as `fix(deps): move cloud function manifest to Django 5.2.17`.
  </action>
  <verify>
    <automated>python3 -c '
from pip._vendor.packaging.requirements import Requirement
import pathlib, sys
root = pathlib.Path.cwd()
while not (root / ".git").exists():
    root = root.parent
F = root / "gcp-deployment/cloud-function/requirements.txt"
targets = {"Django": "5.2.17", "djangorestframework": "3.16.1", "django-filter": "24.3",
           "django-cors-headers": "4.4.0", "django-environ": "0.11.2", "PyYAML": "6.0.2"}
seen = {}
bad = []
for raw in F.read_text().splitlines():
    line = raw.split("#")[0].strip()
    if not line or line.startswith("-"):
        continue
    r = Requirement(line)
    seen.setdefault(r.name.lower(), []).append(str(r.specifier))
for name, want in targets.items():
    got = seen.get(name.lower(), [])
    if got != ["==" + want]:
        bad.append(name + ": expected ==" + want + " got " + str(got))
print("PARSED", sum(len(v) for v in seen.values()), "requirements")
if bad:
    print("\n".join(bad))
    sys.exit(1)
print("ALL SIX PINS OK")
'</automated>
    <human-check>Before this reaches production, deploy the cloud function to the review environment and confirm one permutation job completes. The function's `main.py` is gitignored and absent from this checkout, so the Django 4.2 to 5.2 jump cannot be exercised here. Rollback is a one-line revert of this commit.</human-check>
  </verify>
  <done>The gate prints `PARSED 18 requirements` followed by `ALL SIX PINS OK` and exits 0. It raises on any malformed pip line, and the list comparison also fails on a duplicated pin, so a stale line left behind cannot pass silently.</done>
  <reversibility rating="reversible">Single-file version bump on a tracked manifest; `git revert` restores the prior pins exactly.</reversibility>
</task>

<task type="auto">
  <name>Task 2: Record the alignment invariant and prove zero residual drift</name>
  <files>gcp-deployment/cloud-function/requirements.txt</files>
  <action>
Update the comment header of `gcp-deployment/cloud-function/requirements.txt` to
state the invariant that Task 1 just restored: for every package this manifest
shares with `djangoexact/requirements.txt`, the pinned version must match that
file, which is the reference. Note that this manifest is not covered by
`.github/dependabot.yml`, which watches `/djangoexact` only, so drift here is
caught by review rather than by tooling.

Keep it to a few comment lines at the top of the file, below the existing
purpose line. Change no pinned version and add no new requirement line. Comments
are stripped before parsing by both gates, so this edit cannot affect them.

Then run the drift gate below. It compares every shared package across both
manifests. A clean run is the proof that the six packages in CONTEXT.md were the
complete set and that no seventh package was missed. If it reports drift on a
package not listed in Task 1, stop and report rather than bumping it, since that
would be new scope beyond the locked CONTEXT.md matrix.

Commit as `docs(deps): record cloud function manifest alignment with the main app`.
  </action>
  <verify>
    <automated>python3 -c '
from pip._vendor.packaging.requirements import Requirement
import pathlib, sys
root = pathlib.Path.cwd()
while not (root / ".git").exists():
    root = root.parent
def pins(rel):
    out = {}
    for raw in (root / rel).read_text().splitlines():
        line = raw.split("#")[0].strip()
        if not line or line.startswith("-"):
            continue
        r = Requirement(line)
        out[r.name.lower()] = str(r.specifier)
    return out
fn = pins("gcp-deployment/cloud-function/requirements.txt")
app = pins("djangoexact/requirements.txt")
shared = sorted(set(fn).intersection(app))
drift = [n for n in shared if fn[n] != app[n]]
print("shared=" + str(len(shared)), "drifted=" + str(len(drift)))
for n in drift:
    print("DRIFT " + n + ": cloud-function " + fn[n] + " vs djangoexact " + app[n])
sys.exit(1 if drift else 0)
'</automated>
  </verify>
  <done>The gate prints `shared=16 drifted=0` and exits 0. Before Task 1 this same command reported 6 drifted packages, so a green run is a state change and not a vacuous pass.</done>
  <reversibility rating="reversible">Comment-only edit.</reversibility>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| HTTP client to cloud function | Untrusted request headers, cookies and cache keys reach Django request handling inside the deployed function. |
| Repo manifest to deployed runtime | This file is the sole tracked input that determines which library code executes in the function. |

## STRIDE Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation Plan |
|-----------|----------|-----------|----------|-------------|-----------------|
| T-fnr-01 | Information Disclosure | Django cache middleware in the deployed function (GHSA-3h9f-r86x-qvjx, GHSA-8cjm-8mp7-r2xf, GHSA-923m-gv2p-w5qp) | medium | mitigate | Task 1 pins Django 5.2.17, above the 5.2.15 and 5.2.16 floors, removing the cached-response disclosure paths through unrelated cookies, case-sensitive Cache-Control and whitespace in Vary. |
| T-fnr-02 | Spoofing | Django signed cookies (GHSA-h7pc-vwp9-298g) | low | mitigate | Task 1 pin closes the salt namespace collision. |
| T-fnr-03 | Tampering | DomainNameValidator, HTTP header injection via newlines (GHSA-8qcx-xf44-272x) | medium | mitigate | Task 1 pin meets the 5.2.16 floor. |
| T-fnr-04 | Information Disclosure | GDALRaster heap over-read from bytes (GHSA-crhf-3pfg-w68w) | medium | mitigate | Task 1 pin meets the 5.2.16 floor. The function is not known to use GeoDjango, so exposure is likely nil, but the pin closes it regardless. |
| T-fnr-05 | Denial of Service | Manifest stranded on an end-of-life Django series receiving no further security patches | high | mitigate | Task 1 moves to the 5.2 LTS series, which remains supported and is the series the main app already tracks. Task 2 records the alignment invariant in-file so the next reader sees which manifest is the reference, since `.github/dependabot.yml` does not watch this path. |
| T-fnr-06 | Elevation of Privilege | Django 4.2 to 5.2 major upgrade applied to function source that is absent from this checkout and therefore untestable here | high | mitigate | Task 1 carries a blocking `human-check`: deploy to review and complete one permutation job before production. Risk is bounded because the code the function imports (`minitool`, `PermutationComputer`) already runs under Django 5.2.17 in the main app, and rollback is a single-commit revert. |
| T-fnr-SC | Tampering | pip supply chain for the six changed pins | medium | accept | No task executes an install, and no new package name is introduced. All six target versions are already pinned and running in `djangoexact/requirements.txt` in production, so they carry no unvetted supply-chain surface beyond what is already deployed. |
</threat_model>

<verification>
1. Task 1 gate is green: manifest parses and all six pins are exact.
2. Task 2 gate is green: zero drift across the 16 shared packages.
3. `git status` shows exactly one modified file,
   `gcp-deployment/cloud-function/requirements.txt`. Neither
   `djangoexact/requirements.txt` nor `djangoexact/package-lock.json` appears.
4. Two atomic conventional commits on `develop`, no em-dashes in either message.
5. After the branch reaches `main`, alerts 175 through 180 auto-close. They are
   scanned against the default branch, so they stay open on `develop` alone. This
   is the same lag documented for quick task 260805-n82 and is expected, not a
   failure of this task.
</verification>

<success_criteria>
- All six open Dependabot alerts have no affected pin remaining in the repo.
- The changed manifest is installable, not merely patched: DRF, django-filter and
  django-cors-headers all declare Django 5.2 support.
- Shared-package parity with `djangoexact/requirements.txt` is complete and proven
  by a runnable gate.
- Nothing outside the one permitted file changed.
</success_criteria>

<notes>
Out of scope by explicit CONTEXT.md instruction, mention in the summary only:
- Adding `/gcp-deployment/cloud-function` to `.github/dependabot.yml`. It would
  yield nothing today because `open-pull-requests-limit: 0` disables version-update
  PRs repo-wide as of commit 581091fd, and security alerts already fire for
  unwatched manifests.
- A checked-in regression test asserting the drift gate. It would make the Task 2
  invariant machine-enforced in CI rather than review-enforced, but it requires a
  new file under `djangoexact/api/tests/`, which the locked single-file constraint
  forbids. Worth raising as a follow-up quick task.
</notes>

<output>
Create `.planning/quick/260810-fnr-fix-dependabot-and-semgrep-security-find/260810-fnr-SUMMARY.md` when done.
</output>
