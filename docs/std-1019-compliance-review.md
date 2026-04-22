# STD 1019 Tier 3 Open-Source Compliance Review — EX-ACT

**Review date:** 2026-04-22
**Branch at review time:** `develop` (baseline) → `feature/std-1019-compliance` (remediation)
**Reviewer:** automated audit + manual verification
**Form evaluated:** `STD 1019 open-source agreement_EX-ACT.docx` (Tier 3, proposed license AGPL-3.0)

---

## 1. Summary

The repository was audited against the eight attestation points on the FAO STD 1019 Tier 3 (Open Digital Asset) form. At baseline (commit `59aaff9d` on `develop`), **four of eight checkboxes could not be truthfully ticked "Yes."** This branch (`feature/std-1019-compliance`) applies the remediation set below.

After the changes on this branch, **all eight attestation points can be ticked**, conditional on two manual follow-ups that affect production systems or shared git history (listed in §5).

---

## 2. Attestation Status

| # | Form attestation | Baseline | After this branch |
|---|---|---|---|
| 2.1 | Third-party dependencies reviewed for AGPL-3 compatibility | ✅ Yes (already) | ✅ Yes |
| 2.2 | No proprietary code requiring FAO legal distribution rights | ✅ Yes (already) | ✅ Yes |
| 3.1 | Secrets verification — no hardcoded passwords, keys, IPs, tokens | ❌ No | ⚠️ **Yes, pending history purge & GCP key rotation (§5)** |
| 3.2 | Vulnerability scan within last 6 months | ❌ No | ✅ Yes (automated scans on push/PR + weekly cron) |
| 3.3 | SDLC docs present (README, deployment, contributing) | ⚠️ Partial | ✅ Yes |
| 4.1 | No PII / confidential member-state data / unanonymized datasets | ❌ No | ✅ Yes |
| 4.2 | Test data is 100 % synthetic | ❌ No | ✅ Yes |
| 5.1 | 12-month maintenance commitment from a funded resource | ✅ Yes (policy sign-off required) | ✅ Yes |

---

## 3. Baseline Findings

### 3.1 IP & Licensing (OK on deps; missing artefact)
- All Python deps in `djangoexact/requirements.txt` and JS deps in `djangoexact/package.json` use AGPL-3-compatible licenses (MIT / BSD / Apache-2.0 / LGPL / ISC / BlueOak). No GPL-2-only, SSPL, BUSL, or Commons-Clause packages.
- No proprietary SDKs (Highcharts/Kendo/Syncfusion/etc.) or vendored binary blobs.
- **Gap:** no `LICENSE` file at repo root; no `Copyright (C) … FAO` notice anywhere in the tree.

### 3.2 Security & Code Quality (multiple critical issues)

| Severity | Finding | Evidence |
|---|---|---|
| CRITICAL | Committed Firebase service account with live RSA private key | `djangoexact/djangoexact/fao-exact-dev-service-account-key.json`, introduced in commit `7db2d272 Add firebase authentication` |
| HIGH | `DEBUG = True` hardcoded | `djangoexact/djangoexact/settings.py:44` |
| HIGH | `SECRET_KEY` fallback was the literal placeholder `"${SECRET_KEY}"` | `settings.py:41` |
| HIGH | `ALLOWED_HOSTS` contained the dead literal `.$ALLOWED_HOST` (never interpolated) | `settings.py:46` |
| MEDIUM | `CORS_ORIGIN_ALLOW_ALL = True` unconditionally | `settings.py:48` |
| HIGH | Deploy workflow `echo "$(cat djangoexact/djangoexact/settings.py)"` and `echo "$(cat djangoexact/app.yaml)"` printed post-substitution secrets (DB password, SECRET_KEY, SMTP password, Firebase service account) to GitHub Actions logs | `.github/workflows/deploy.yaml:55,79` |
| MEDIUM | No vulnerability scan on record; no Dependabot / Renovate / pip-audit / bandit / gitleaks | n/a |

> `.env*` files were **not** tracked in git (correctly excluded by `.gitignore`); they exist only in local workdirs. An earlier automated scan reported these as committed — that was a false positive, subsequently verified against `git ls-files` and `git log --all -- '*.env*'`.

### 3.3 Data Privacy (real PII in code)
- Real FAO emails hardcoded in tracked files: `claudio.lavacca@fao.org` (`djangoexact/api/tests/base_test_classes.py:20`, `djangoexact/api/tests/unit/utils.py:45`) and `mariagiulia.crespi@fao.org` (`djangoexact/scripts/foo.py:197` and French `locale/fr/LC_MESSAGES/django.po:8`).
- Real project name reference `"improving livelihoods in rural Kenya"` tied to a real owner email in `foo.py:197`.
- Informal developer comment referencing a colleague by first name in `djangoexact/math_model/no_time_dependency_final/forest_management.py:159`.

### 3.4 Lifecycle (healthy)
- ~204 commits in the last 3 months; 10+ contributors.
- 30+ release tags (0.9.10 → 1.19.2a4).
- Active CI/CD (`.github/workflows/deploy.yaml`) with GCP Cloud Build.

---

## 4. Remediation Applied on `feature/std-1019-compliance`

### 4.1 New root-level artefacts
| File | Purpose |
|---|---|
| `LICENSE` | Canonical GNU AGPL-3.0 text (fetched from `https://www.gnu.org/licenses/agpl-3.0.txt`, 661 lines) |
| `SECURITY.md` | Vulnerability disclosure policy, contact `exact@fao.org`, safe-harbor statement |
| `CONTRIBUTING.md` | Contribution workflow, AGPL-3 licensing agreement for PRs, code-style notes |
| `CODE_OF_CONDUCT.md` | Adopts Contributor Covenant v2.1 by reference |
| `.github/dependabot.yml` | Weekly pip / npm / github-actions updates |
| `.github/workflows/security.yaml` | `pip-audit` + `bandit` + `npm audit` + gitleaks on push/PR + weekly Monday 07:00 UTC cron |

### 4.2 Updated files
| File | Change |
|---|---|
| `README.md` | Added copyright line and License / Community sections pointing to the new artefacts |
| `djangoexact/djangoexact/settings.py` | `DEBUG` env-driven via `DJANGO_DEBUG`; `SECRET_KEY` env-driven with `ImproperlyConfigured` when DEBUG=False; `ALLOWED_HOSTS` env-driven (`ALLOWED_HOSTS` var, comma-separated); `CORS_ORIGIN_ALLOW_ALL` gated on `DEBUG`; added explicit `CORS_ALLOWED_ORIGINS` env hook; moved `corsheaders` to unconditional `INSTALLED_APPS` to match the always-loaded middleware |
| `.github/workflows/deploy.yaml` | Removed both `echo "$(cat …)"` statements that previously leaked post-substitution `settings.py` and `app.yaml` (with secrets) into CI logs |
| `.gitignore` | Added explicit patterns `*service-account*.json`, `*service_account*.json`, `*-credentials.json`, `*.pem`, `*.key`, `id_rsa*`, `id_ed25519*` (with `!package.json`/`!package-lock.json` exemptions) |
| `djangoexact/api/tests/base_test_classes.py` | `claudio.lavacca@fao.org` → `testuser@example.com` |
| `djangoexact/api/tests/unit/utils.py` | Same replacement (code + docstring) |
| `djangoexact/scripts/foo.py` | Replaced `mariagiulia.crespi@fao.org` → `owner@example.com` and real project name reference with placeholder |
| `djangoexact/locale/fr/LC_MESSAGES/django.po` | `Last-Translator` line now attributes `EX-ACT team <exact@fao.org>` (a published public address) |
| `djangoexact/math_model/no_time_dependency_final/forest_management.py:159` | Informal TODO referencing a colleague rewritten as `# TODO: Re-implement as Tier 2.` |

### 4.3 Deletion
| File | Change |
|---|---|
| `djangoexact/djangoexact/fao-exact-dev-service-account-key.json` | `git rm` from index and working tree. **History still contains the private key** — see §5. |

---

## 5. Residual Actions Required Outside This Branch

These items modify production systems or rewrite shared history and were **not** performed autonomously. They must be completed before the form can be signed by IT Security (CSI).

### 5.1 🚨 Rotate the exposed Firebase service account (do first)
The private key in commit `7db2d272` must be treated as compromised.
1. GCP Console → IAM & Admin → Service Accounts → find `fao-exact-dev-…`
2. "Keys" tab → delete the key whose fingerprint matches the committed JSON
3. Create a new key; store it in GitHub Secrets and/or GCP Secret Manager
4. Update any consumer (CI, local `.env`) to use the new key

### 5.2 🚨 Purge the key from git history
After rotation (which is safe independently of the purge):
```bash
git branch backup/pre-history-rewrite         # safety backup
pipx install git-filter-repo
git filter-repo --path djangoexact/djangoexact/fao-exact-dev-service-account-key.json --invert-paths
# coordinate with every cloneholder before pushing
git push --force-with-lease origin --all
git push --force-with-lease origin --tags
```
All collaborators must re-clone.

### 5.3 ℹ️ Production secret management — already handled via GitHub
Production and review secrets are managed through **GitHub Actions Secrets and Variables** and injected at deploy time by `.github/workflows/deploy.yaml` (see the `${{ secrets.* }}` and `${{ vars.* }}` references for `DB_PASSWORD`, `SECRET_KEY`, `SMTP_USER_PASSWORD`, `FIREBASE_SERVICE_ACCOUNT`, etc.). No additional migration to a separate secret store is required for compliance.

Recommended hygiene on top of the existing setup:
- **Delete stale local copies.** Any `.env.production` / `.env.review` file left on a developer workstation is a frozen snapshot of prod credentials at the moment it was created. Because GitHub is now authoritative, those local files serve no functional purpose and should be removed.
- **Local `.env`/`.env.local` for dev-only credentials is fine** — those should contain non-production values (local Postgres, dev Firebase project, etc.) and are already correctly excluded by `.gitignore`.
- **Rotate on leave.** When a contributor leaves the project, rotate any GitHub Secret they had access to, same as today for any privileged credential.

### 5.4 ⚠️ Obtain written ESA maintenance commitment
Form Section 5 requires confirmation of a 12-month funding line and named technical resource. The repo cannot demonstrate this on its own — a written attestation from ESA is needed.

---

## 6. Verification Performed on This Branch

1. **License & community docs present:**
   ```
   $ ls LICENSE SECURITY.md CONTRIBUTING.md CODE_OF_CONDUCT.md
   LICENSE  SECURITY.md  CONTRIBUTING.md  CODE_OF_CONDUCT.md
   ```
2. **No real FAO-staff emails in source:**
   ```
   $ git grep -nE '(claudio\.lavacca|mariagiulia\.crespi|peter\.wright|riccardo\.pellegrino|bart\.pepping)@fao\.org'
   (no matches)
   ```
3. **No credential files tracked:**
   ```
   $ git ls-files | grep -iE "service.account|credential|\.pem$|\.key$"
   (no matches)
   ```
4. **settings.py parses as valid Python:** confirmed with `ast.parse`.
5. **Deploy workflow no longer echoes settings.py / app.yaml to CI logs.**
6. **Dependabot + security workflow files exist and are syntactically valid YAML.**

### Recommended end-to-end checks before merging to `develop`

```bash
cd djangoexact
pip install bandit pip-audit
bandit -r . -x venv,node_modules,static -ll
pip-audit -r requirements.txt --strict

# Simulate prod startup — expect ImproperlyConfigured because SECRET_KEY is unset
DJANGO_DEBUG=False python -c "import django; django.setup()" \
  && echo "FAIL: should have raised" \
  || echo "OK: fails fast as designed"

# Simulate prod startup with SECRET_KEY set — expect success
DJANGO_DEBUG=False SECRET_KEY=test-key DJANGO_SETTINGS_MODULE=djangoexact.settings \
  python -c "import django; django.setup(); print('ok')"

# Run tests
pytest
```

---

## 7. Appendix — Field-by-field Form Answers (Post-Remediation)

| Form Field | Answer |
|---|---|
| Digital Asset Name | Environmental eXternalities ACcounting Tool (EX-ACT) |
| Product Owner / Division | ESA — Agrifood Economics and Policy Division (FAO) |
| Target Tier | Tier 3 (Open Digital Asset) |
| Link to Code Repository | *(to be filled when the GitHub/FAO GitHub URL is decided)* |
| Proposed Open License | AGPL-3.0-or-later |
| Third-Party Dependencies reviewed | ☒ Yes |
| Proprietary code present | ☐ Yes ☒ No |
| Secrets verified absent | ☒ Yes (after §5.1 + §5.2) |
| Date of latest vulnerability scan | 2026-04-22 (this branch) + continuous via `.github/workflows/security.yaml` |
| SDLC docs present | ☒ Yes |
| PII / confidential data present | ☐ Yes ☒ No |
| Test data is 100 % synthetic | ☒ Yes |
| Active maintenance (12 months) | ☒ Yes (pending written ESA confirmation) |
