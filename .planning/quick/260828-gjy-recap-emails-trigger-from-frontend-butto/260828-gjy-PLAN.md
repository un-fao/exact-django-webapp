---
phase: quick-260828-gjy
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - djangoexact/api/models.py
  - djangoexact/api/migrations/0293_project_last_recap_sent_at.py
  - djangoexact/api/serializers.py
  - djangoexact/api/utilities.py
  - djangoexact/api/security.py
  - djangoexact/api/views.py
  - djangoexact/api/templates/changes/changes.html
  - djangoexact/api/tests/test_recap_email.py
  - .github/workflows/deploy.yaml
autonomous: true
requirements: [260828-gjy]

estimate:
  tokens: 48000
  raw_tokens: 32000
  tasks: 3
  confidence: low

must_haves:
  truths:
    - "A project admin can POST /projects/{id}/recap/ on an UNLOCKED project and receive a 200 (D-03)."
    - "The recap covers only changes made since the previous recap email for that project, not since the project was locked (D-02)."
    - "On a project that has never had a recap, the recap covers every history record since the project was created (D-04)."
    - "A recap that sends nothing (no changes, or every send raised) leaves the window start where it was, so no change is ever skipped (D-05)."
    - "A project member who is not in the Admin group gets 403 from the recap endpoint; project Admins and superusers get 200 (D-06)."
    - "The automatic recap call inside Project.unlock() is still commented out (D-07)."
    - "The 200 response tells the caller whether an email actually went out, while keeping the existing message key (D-08)."
  artifacts:
    - djangoexact/api/migrations/0293_project_last_recap_sent_at.py
    - djangoexact/api/tests/test_recap_email.py
  key_links:
    - "Project.last_recap_sent_at -> send_changes_email history/comment window filters (D-01, D-02)"
    - "send_changes_email return value -> Project.last_recap_sent_at write -> ProjectViewSet.recap response body (D-05, D-08)"
    - "security.check_project_admin -> ProjectViewSet.recap 403 path (D-06)"
    - "Project.last_recap_sent_at -> ProjectExportSerializer exclude list (imported projects must not inherit a foreign window)"
---

<objective>
Turn the project recap email from a lock-driven side effect into a button-driven action whose diff window is "since the previous recap email".

Purpose: the frontend needs a recap button that works on an unlocked project, never re-sends the same changes, and never silently drops changes.
Output: one nullable timestamp on Project, a rewritten window inside `send_changes_email`, an admin-only endpoint that reports whether it sent, and a DB-free test module wired into the CI gate.

BACKEND ONLY. The frontend lives in a separate repo; nothing here renders a button.

## Source coverage (all 8 requirements)

| ID | Requirement | Covered by |
|----|-------------|------------|
| D-01 | Per-project "last recap sent" nullable DateTimeField + migration (next number after 0292) | Task 1 |
| D-02 | `send_changes_email` windows on that timestamp, not `project.locked_at` | Task 2 |
| D-03 | Drop the "must be locked" guard; lock context degrades gracefully in the template | Task 2 |
| D-04 | First send (timestamp NULL) covers all history since creation — USER DECIDED, do not revisit | Task 2 |
| D-05 | Timestamp advances only when an email was actually sent successfully | Task 2, asserted in Task 3 |
| D-06 | Recap endpoint tightens from `view_project` to project-admin-only — USER DECIDED, do not revisit | Task 2, asserted in Task 3 |
| D-07 | The commented-out auto trigger in `Project.unlock()` STAYS COMMENTED OUT | Task 2 verify gate |
| D-08 | Response distinguishes "email sent" from "no changes", additive to the existing `{"message": ...}` 200 | Task 2 |

No unplanned items. No package-manager installs in this task, so no package legitimacy gate applies.
</objective>

<execution_context>
@C:/Users/sirvosterzo/Developer/FAO/EXACT/exact-django-webapp/.claude/gsd-core/workflows/execute-plan.md
@C:/Users/sirvosterzo/Developer/FAO/EXACT/exact-django-webapp/.claude/gsd-core/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md

Read before editing:
- `djangoexact/api/utilities.py` — `get_changes` (line 604), `send_changes_email` (line 752), `find_modules` (line 175), `has_project_permission` (line 146), `ErrorResponse` (line 141)
- `djangoexact/api/models.py` — `Project` lock fields (lines 690-693), `Project.unlock` (line 805)
- `djangoexact/api/views.py` — `ProjectViewSet.recap` (line 1591)
- `djangoexact/api/security.py` — whole file, 11 lines
- `djangoexact/api/serializers.py` — `ProjectExportSerializer` (line 730), `check_member_management_allowed` (line 3212)
- `djangoexact/api/templates/changes/changes.html` — whole file, 87 lines
- `djangoexact/api/tests/test_finalized_member_management.py` — the DB-free fake-object test idiom this repo already uses

Facts already verified this session — do not re-derive:
- Latest migration is `0292_country_iso3`. There is a deliberate numbering gap at 0290 (see STATE.md quick task 260819-jfs). The new migration depends on `0292_country_iso3`.
- `djangoexact/api/utilities.py` does NOT import `django.utils.timezone`. You must add it.
- `Project.created_at` is `auto_now_add=True, null=True` — it can be NULL on legacy rows, so it is NOT a safe window fallback. Absent-filter is the only correct "since creation" implementation.
- `Project.updated_at` is `auto_now=True`. Saving with `update_fields=["last_recap_sent_at"]` leaves it untouched, which is what we want.
- The repo has no `pytest-django`. CI runs `python manage.py test --keepdb` with an explicit module label list in `.github/workflows/deploy.yaml` (lines ~131-148).
- `get_changes` is also called from three read-only changelog endpoints: `views.py:1465`, `views.py:2346`, `views.py:2822`. Task 2 changes it; that blast radius is intentional and described in the task.
</context>

<tasks>

<task type="auto">
  <name>Task 1: Persist the per-project recap window start (D-01)</name>
  <files>djangoexact/api/models.py, djangoexact/api/migrations/0293_project_last_recap_sent_at.py, djangoexact/api/serializers.py</files>
  <action>
Add `last_recap_sent_at = models.DateTimeField(null=True, blank=True, verbose_name="last_recap_sent_at")` to the `Project` model, immediately after the `locked_by` field around line 693 so it sits with the other per-project workflow timestamps. Follow the surrounding field style exactly (explicit `verbose_name` matching the attribute name).

Generate the migration with `python manage.py makemigrations api --name project_last_recap_sent_at`. It must land as `0293_project_last_recap_sent_at.py` and depend on `0292_country_iso3`. `Project` carries `HistoricalRecords`, so the migration will also add the column to `HistoricalProject` — that is expected, keep both operations. Do not hand-write the migration; let makemigrations produce it, then read it back to confirm the dependency and the two AddField operations.

Add the new field name to the `exclude` list of `ProjectExportSerializer` (serializers.py line 736), alongside the lock fields that are already excluded there. This matters: without it, a project imported from another environment inherits that environment's window and its very first recap silently skips its entire real history. Keep the list ordering/formatting of the surrounding entries.

Leave `ProjectSerializer` (serializers.py line 489, `fields = "__all__"`) alone — the field surfacing on the project read API is harmless and lets the frontend show when the last recap went out.
  </action>
  <verify>
    <automated>cd djangoexact && python manage.py makemigrations api --check --dry-run && ls api/migrations/0293_project_last_recap_sent_at.py && grep -c "0292_country_iso3" api/migrations/0293_project_last_recap_sent_at.py && test "$(sed -n '/class ProjectExportSerializer/,/def to_representation/p' api/serializers.py | grep -vE '^\s*#' | grep -c last_recap_sent_at)" -eq 1</automated>
  </verify>
  <done>`Project` has a nullable `last_recap_sent_at`, migration 0293 exists and chains off 0292, `makemigrations --check` reports no pending changes, and the export serializer excludes the field.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Window the recap on the last send, unlock the trigger, lock down the endpoint (D-02 through D-08)</name>
  <files>djangoexact/api/utilities.py, djangoexact/api/security.py, djangoexact/api/views.py, djangoexact/api/templates/changes/changes.html, djangoexact/api/models.py</files>
  <behavior>
    - `send_changes_email` on a project whose `last_recap_sent_at` is NULL queries history with no lower date bound (D-04).
    - `send_changes_email` on a project with a timestamp T queries history bounded at T, for the project, each activity, each module, each submodule, and each comment thread (D-02).
    - `send_changes_email` on an unlocked project completes and mails, instead of raising (D-03).
    - `send_changes_email` returns the number of recipients successfully mailed; 0 when the diff is empty, 0 when every send raised.
    - The stored timestamp moves only when that count is greater than 0 (D-05).
    - `security.check_project_admin` returns None for a project Admin and for a superuser, and a 403 ErrorResponse for everyone else (D-06).
  </behavior>
  <action>
Work through `send_changes_email` (utilities.py line 752) in this order.

**Imports.** Add `from django.utils import timezone` to the utilities.py import block.

**Capture the new window boundary first.** As the very first statement of the function body, take `sent_at = timezone.now()`. Capturing before the diff is computed rather than after the send means a change landing mid-run falls into the next window instead of being lost.

**Delete the lock guard.** Remove the two-line guard near the top that rejects a project whose `locked_at` or `locked_by` is None. The button must work on an unlocked project (D-03).

**Replace the window.** Drop the local lock-timestamp alias and build two filter dicts from the persisted field instead:
an empty dict when `project.last_recap_sent_at` is None, otherwise a single-key dict bounding `history_date` at or after it; and the comment equivalent bounding `date_created`. Django's `filter(**{})` returns the unfiltered queryset, so the NULL case naturally means "everything since the project was created" with no branching (D-04).

**Collapse the four diff calls into one local helper.** All four `get_changes` call sites (project, activity, module, submodule) repeat the same queryset filter plus `exclude_fields` argument. Replace them with a single nested helper that applies the history filter dict, calls `get_changes`, and drops any returned changelog whose `changes` list is empty. Dropping empties is load-bearing: on a first send the project's creation record produces a changelog with no field changes, which renders as nothing in the template but would otherwise defeat the "no changes, do not send" bail-out and falsely advance the timestamp.

Rewrite `get_new_comments` (line 766) to close over the comment filter dict and take only the threads argument; update both of its call sites.

**Exclude the new field from diffs.** Add the new timestamp field name to `fields_to_exclude` (line 810), next to the lock fields. Writing the timestamp saves the project and therefore creates a history record; without this exclusion that record shows up as a spurious change in the next recap.

**Degrade the lock context.** `lock_holder` currently resolves from `project.locked_by` unconditionally and `project.locked_by.get_full_name()` blows up when the project is unlocked. Resolve the lock holder only when `project.locked_by` is set, keeping the existing "not a member of the project" warning for that case and the existing "Superuser" fallback for the group name. When the project is unlocked, pass None for the holder name and group name, and pass `sent_at` as the displayed date instead of the absent lock date. Build the subject line from the holder group name when there is a holder, and from a neutral project-recap phrasing when there is not — never interpolate a None into it.

In `changes/changes.html`, wrap the greeting line that names the reviewer group and the standalone `Reviewer:` line in a conditional on the holder name, with an alternative greeting for the unlocked case that says the mail is a recap of recent changes and comments. The `Date:` line stays unconditional because the context now always supplies a date. Do not restructure the rest of the template.

**Return a count and advance only on success.** Keep the existing early return when there is nothing to report, but make it return 0. Count each recipient whose `send_mail` returns without raising, leaving the existing per-recipient try/except logging exactly as it is. After the loop, when the count is greater than 0, set the project's timestamp to `sent_at` and persist it with `project.save(update_fields=["last_recap_sent_at"])`, then return the count. When the count is 0 — no recipients, or every send raised — do not touch the timestamp (D-05). Update the docstring: it currently documents two parameters that the signature does not have.

**Two root-cause fixes in `get_changes` (line 604).** Both are required for this feature and both also correct the three read-only changelog endpoints that share this function.
1. Line 608 reads `record.history_user.email` on a creation record. On a first send the window now reaches back to project creation, and a project created by an import, a copy or a script has no history user, so this raises and 500s the whole recap. Guard it so a missing history user yields None instead of an attribute error. Note that the later `history_user is None` skip on line 628 does not protect this branch, because the creation branch returns before reaching it.
2. Line 611 skips any record that has no newer record, which means the most recent change is structurally unreportable. Under the old lock flow the newest record was the lock-state save; under a button-driven window the newest record is the user's last real edit, and once the window advances past it that edit is lost forever. Remove that skip so the newest record is diffed against its predecessor like any other. Records whose only changed fields are excluded still produce an empty changelog and are still dropped, so this does not make empty recaps.

**Add the admin gate.** Add `check_project_admin(user, project)` to `djangoexact/api/security.py`, beside `check_permission` and returning the same contract (None when allowed, a 403 `utils.ErrorResponse` when not). Reuse the project-admin idiom this codebase already uses in `check_member_management_allowed` (serializers.py line 3221): superuser passes, otherwise the user must appear in `project.members` filtered on the Admin group name. Do not invent a permission codename and do not extend `has_project_permission` — the Admin group's codename set is not something this change can verify.

**Rewire the endpoint.** In `ProjectViewSet.recap` (views.py line 1591), swap the `view_project` permission check for the new admin gate (D-06). Call `send_changes_email` and branch on its return: a non-zero count returns 200 with the existing message key kept verbatim plus an additive `sent: true` and the recipient count; zero returns 200 with `sent: false`, a count of 0, and a message stating that nothing was sent because there were no changes since the last recap or every admin had opted out. Leave the existing broad except and its 500 ErrorResponse as they are. Update the `swagger_auto_schema` `operation_description` and the 403 response entry to reflect the admin-only gate.

**Leave `Project.unlock` alone (D-07).** The commented-out automatic call at models.py line 812-814 stays commented out. Do not uncomment it, do not delete it, do not reword the TODO above it.
  </action>
  <verify>
    <automated>cd djangoexact && python -m compileall -q api/utilities.py api/views.py api/security.py api/models.py && python manage.py check && test "$(grep -vE '^\s*#' api/models.py | grep -c send_changes_email)" -eq 0 && test "$(sed -n '/^def send_changes_email/,/^def find_modules/p' api/utilities.py | grep -vE '^\s*#' | grep -cE 'locked_at\s*=\s*project\.locked_at|history_date__gte=locked_at')" -eq 0 && grep -q "def check_project_admin" api/security.py && grep -q "check_project_admin" api/views.py && test "$(grep -vE '^\s*#' api/views.py | grep -c 'check_permission("view_project", request.user, project)')" -ge 0 && grep -q "lock_holder_name" api/templates/changes/changes.html</automated>
  </verify>
  <done>The recap windows on the persisted timestamp with no lower bound on first send, runs on an unlocked project without raising, renders without a broken reviewer block, returns a recipient count, advances the timestamp only on a successful send, is reachable only by project admins and superusers, and the auto trigger in `unlock()` is still commented out.</done>
</task>

<task type="auto">
  <name>Task 3: DB-free regression tests for the window, the advance rule, and the 403 (D-05, D-06)</name>
  <files>djangoexact/api/tests/test_recap_email.py, .github/workflows/deploy.yaml</files>
  <action>
Create `djangoexact/api/tests/test_recap_email.py` as a `django.test.SimpleTestCase` module with no database access, following the fake-object idiom already established in `djangoexact/api/tests/test_finalized_member_management.py` (`SimpleNamespace` stand-ins plus a hand-rolled fake for the `members` manager). `api/tests/factories.py` executes reference-data queries at import time — do not import it, and do not import anything that pulls it in.

Build a fake project exposing: the recap timestamp attribute, `locked_at` and `locked_by` both None, `name`, `id`, an `activities` stand-in whose `all()` returns an empty list, a `history` stand-in whose `filter(**kwargs)` records the kwargs it was handed and returns an empty list, and a `save` that records the `update_fields` it was called with. Pass `recipients` explicitly as a list of membership stand-ins so the function never reaches the `ProjectNotificationPreference` lookup, which would need a database.

Patch `api.utilities.get_changes`, `api.utilities.render_to_string` and `api.utilities.send_mail` with `unittest.mock.patch` for each test. Return a canned list of `ChangeLog` objects with at least one non-empty `changes` entry from the `get_changes` double when the test wants a non-empty diff, and an empty list when it wants the empty-diff path.

Cover exactly these cases:
1. First send: the recap timestamp starts as None, and the kwargs recorded by the history double contain no lower date bound at all (D-04).
2. Subsequent send: the recap timestamp is a concrete datetime, and the recorded kwargs bound `history_date` at that datetime (D-02).
3. Successful send: the mail double returns normally, the function returns a non-zero count, the project was saved with the recap field in `update_fields`, and the stored timestamp is now a datetime later than the previous one (D-05).
4. Empty diff: the `get_changes` double returns nothing, the function returns 0, `send_mail` was never called, `save` was never called, and the stored timestamp is unchanged (D-05).
5. Failed send: the mail double raises, the function returns 0, `save` was never called, and the stored timestamp is unchanged (D-05).
6. Permission: `security.check_project_admin` returns None for a member in the Admin group and for a superuser, and returns a response whose `status_code` is 403 for an authenticated non-admin member (D-06).

Register the module in the CI gate by adding `api.tests.test_recap_email` to the explicit label list in the `Run test suite` step of `.github/workflows/deploy.yaml` (the list around lines 131-148). Keep the list's existing ordering convention and line style — the surrounding comment explains why bare `api` or `api.tests` labels are forbidden, so add a specific module label, not a package label.

Run the module. Note that Django's test runner sets up a test database even for `SimpleTestCase`, so this needs a reachable Postgres from the working environment. If no database is reachable here, say so plainly in the summary and record that the module was not executed locally — do not claim a run that did not happen. The CI gate will run it against real Postgres either way.
  </action>
  <verify>
    <automated>cd djangoexact && python manage.py test api.tests.test_recap_email --keepdb -v 2 && grep -c "api.tests.test_recap_email" ../.github/workflows/deploy.yaml</automated>
  </verify>
  <done>Six DB-free tests exist and are registered in the CI label list; they pass locally, or the summary states explicitly that no database was reachable and the module was not executed here.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| authenticated client -> `POST /projects/{id}/recap/` | Any project member could previously trigger a mail-out of the full project change history |
| application -> SMTP recipients | Project change details leave the system as email bodies |
| foreign environment -> `.exactproject` import | An imported project carries attacker- or environment-controlled field values |

## STRIDE Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation Plan |
|-----------|----------|-----------|----------|-------------|-----------------|
| T-gjy-01 | Elevation of Privilege | `ProjectViewSet.recap` | high | mitigate | Replace the `view_project` check with `security.check_project_admin`; only Admin-group members and superusers may trigger a recap (D-06, Task 2), asserted by test case 6 |
| T-gjy-02 | Information Disclosure | `send_changes_email` recipient resolution | high | mitigate | Recipient derivation is unchanged: Admin-group members minus global opt-outs minus per-project opt-outs. No new recipients, no caller-widened list from the endpoint (the view keeps calling with the default) |
| T-gjy-03 | Tampering | `ProjectExportSerializer` | medium | mitigate | Exclude `last_recap_sent_at` from export/import so an imported project cannot arrive with a future or foreign window that silently suppresses its entire history (Task 1) |
| T-gjy-04 | Denial of Service | recap endpoint, repeated presses | low | accept | Endpoint is authenticated and now admin-only; a repeat press with no new changes sends zero mail and does not advance the window. Existing DRF throttling is unchanged; per-endpoint rate limiting is Phase 4 scope (see STATE.md blockers) |
| T-gjy-05 | Repudiation | window advance | low | mitigate | The window advances only after at least one `send_mail` returned without raising, and to a boundary captured before the diff was computed, so a crash, an empty diff or a total send failure leaves every change still in scope for the next recap (D-05) |
| T-gjy-06 | Denial of Service | `get_changes` creation-record branch | medium | mitigate | Guard the missing history user on creation records; without it the first recap on any imported, copied or script-created project raises and 500s (Task 2) |
</threat_model>

<verification>
1. `cd djangoexact && python manage.py makemigrations --check --dry-run` reports no pending model changes.
2. `cd djangoexact && python manage.py check` passes.
3. `cd djangoexact && python manage.py test api.tests.test_recap_email --keepdb` passes, or the summary states that no database was reachable locally.
4. `grep -vE '^\s*#' djangoexact/api/models.py | grep -c send_changes_email` returns 0 — the automatic trigger is still commented out (D-07).
5. `git diff --stat` touches only the nine files in `files_modified`. No frontend files, no scheduler, no new model, no new preferences table.
</verification>

<success_criteria>
- A project admin can trigger a recap on an unlocked project and gets a 200 that says whether mail went out.
- The second recap on an unchanged project sends nothing, returns `sent: false`, and leaves the window untouched.
- The first recap on a project that never had one covers its whole history, including its creation record, without raising.
- A non-admin project member gets 403.
- `Project.unlock()` is byte-identical to what it is now.
</success_criteria>

<output>
Create `.planning/quick/260828-gjy-recap-emails-trigger-from-frontend-butto/260828-gjy-SUMMARY.md` when done.
</output>
