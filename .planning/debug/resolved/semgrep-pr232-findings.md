---
status: resolved
trigger: "semgrep detected some issues that need to be fixed. Check out https://github.com/un-fao/exact-django-webapp/pull/232 and fix them using Backend Architect (agent)"
created: 2026-07-29
updated: 2026-07-29
---

## Symptoms

- **Expected:** SAST Scanning - Semgrep check on PR #232 (develop -> review promotion) passes.
- **Actual:** Check fails with 26 blocking findings (2 ERROR, 21 WARNING, 3 MEDIUM, 1 INFO... severity mix per the github-actions comment on the PR).
- **Errors:** Full findings table posted as a github-actions comment on PR #232 (Semgrep, 497 rules, 1179 files).
- **Timeline:** First surfaced on PR #232's CI run 30439358325 (2026-07-29). The Semgrep job is an org-level workflow, not defined in this repo.
- **Repro:** Push to the PR or re-run the "SAST Scanning - Semgrep" job; locally `semgrep scan --config auto` approximates it.

## Findings inventory (26)

1. `.github/dependabot.yml` lines 3, 16, 29 (MEDIUM x3): no `cooldown` block per package-ecosystem entry.
2. `.github/workflows/deploy.yaml` lines 47, 50, 218, 223, 229, 474 (WARNING x6): actions pinned to mutable tags, need full commit SHAs.
3. `.planning/quick/260729-exi-remove-staff-role-and-membership-traces-/scripts/inspect_staff.py:109` (WARNING + ERROR) and `verify_staff.py:99` (ERROR): SQL string concatenation in one-off diagnostic scripts.
4. `deploy/cloudrun-service.yaml:41` (INFO): container lacks securityContext runAsNonRoot.
5. `djangoexact/admin_scripts/templates/admin_scripts/scripts/example_script.html:14` and `djangoexact/api/templates/admin/upload_excel_files.html:28` (WARNING x2): forms missing csrf_token.
6. `djangoexact/api/models.py:60` (WARNING): set_password without validate_password.
7. `djangoexact/api/serializers.py` lines 196, 205, 207, 1523 (WARNING x4): non-static index into globals().
8. `djangoexact/minitool/management/commands/import_changes.py` lines 145, 150, 170, 173 (WARNING x4): formatted SQL queries.
9. `djangoexact/minitool/views.py:66` (WARNING): custom expression calling super().as_sql(); `djangoexact/minitool/views.py:1082` (WARNING): len(QUERY.all()) vs QUERY.count() rule.

## Current Focus

hypothesis: "Findings are a mix of genuine hardening gaps (CSRF tags, action pinning, dependabot cooldown, SQL formatting) and context-dependent items (globals() dispatch, planning scripts, Cloud Run securityContext) that need per-finding judgment: real fix where safe, targeted suppression with justification where a fix would change behavior or break the platform."
next_action: "Delegate remediation to Backend Architect agent on a feature branch off develop; verify with py_compile + bandit + semgrep if available."

## Evidence

- 2026-07-29: `gh pr checks 232` shows only SAST Scanning - Semgrep failing; test, Dependabot, Betterleaks pass.
- 2026-07-29: Findings table captured from github-actions comment on PR #232 (recorded above).
- 2026-07-29: No `.semgrepignore` at repo root; Semgrep workflow is org-level (only deploy.yaml / deploy-cloudrun.yaml exist in .github/workflows/).

## Eliminated

## Resolution

root_cause: "Mix of genuine hardening gaps (unpinned actions, missing Dependabot cooldown, dynamic globals() dispatch) and false positives or platform-constrained items (CSRF tags already present but suppressed under a wrong rule id, stacked nosemgrep comments that Semgrep ignores, Cloud Run not honoring runAsNonRoot, .planning diagnostic scripts scanned as production code)."
fix: "8 commits on fix/semgrep-sast-findings (5d1062df..0b747830): Dependabot cooldown added; deploy.yaml actions pinned to 40-char SHAs; serializers.py globals() lookups replaced with an allowlist registry built from DRF BaseSerializer subclasses; minitool len(connections.all()) restructured; remaining items suppressed with correctly-scoped rule ids and justifications (models.py:60 password path is Firebase-managed, cloudrun-service.yaml runAsNonRoot unsupported, import_changes.py interpolates only isidentifier-validated table names); .semgrepignore added replicating Semgrep defaults plus .planning/ exclusion."
verification: "Local semgrep 1.172.0 full-repo scan with CI-equivalent config: 0 findings, 497 rules (CI had 26). py_compile pass on all touched .py files; bandit shows no new issues vs develop baseline; YAML syntax validated; no em-dashes in added lines."
files_changed: ".github/dependabot.yml, .github/workflows/deploy.yaml, .semgrepignore, deploy/cloudrun-service.yaml, djangoexact/admin_scripts/templates/admin_scripts/scripts/example_script.html, djangoexact/api/models.py, djangoexact/api/serializers.py, djangoexact/api/templates/admin/upload_excel_files.html, djangoexact/minitool/management/commands/import_changes.py, djangoexact/minitool/views.py"
