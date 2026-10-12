# 260902-f1z — CONTEXT (locked decisions)

**User story:** "As a user I select which projects I want to receive automated
notifications for. By default, the notifications should be off."

## Existing state (traced before planning — do not re-discover)

The per-project preference model **already exists** and is fully wired. This task
is an **inversion of its semantics**, not a new feature build.

- `api/models.py:944` — `ProjectNotificationPreference(user, project, is_opted_out=False, created_at, updated_at)`,
  `unique_together (user, project)`. Migration `0271_projectnotificationpreference.py`.
- `api/serializers.py:3263` — `ProjectNotificationPreferenceReadSerializer` (fields incl. `is_opted_out`)
  and `:3273` `ProjectNotificationPreferenceWriteSerializer` (`project`, `is_opted_out`;
  `validate()` requires project membership; `create()` stamps `user` from request;
  `update()` rejects other users' rows).
- `api/views.py:1767` — `ProjectNotificationPreferenceViewSet` (list w/ `?project_id=`,
  retrieve, create = get_or_create + update, partial_update w/ 403 on other users).
- `api/urls.py:37` — router `project-notification-preferences`.
- `api/utilities.py:806-820` — the **only consumer**: `send_changes_email()` builds
  `recipients` when not passed explicitly. Today: all `group__name="Admin"` members with
  global `user.is_opted_out_of_emails=False`, then a per-member Python loop excluding
  rows with `is_opted_out=True`. Absence of a row = **receives** (opt-out semantics).
- `api/views.py:1602` — `send_changes_email(project)` from the admin-gated recap endpoint.
  `api/models.py:815` — the auto-trigger on unlock stays commented out (prior decision D-07).
- Latest migration on disk: `0293_project_last_recap_sent_at.py` → this task adds **0294**.
- No admin.py registration and no tests exist for `ProjectNotificationPreference`.

**Scope boundary:** the recap email (`send_changes_email`) is the only *automated*
notification. Report-ready/failed (`api/services/report_notifications.py`), invitation
(`views.py:1944`), verification and password-reset mails are user-triggered/transactional
and are **out of scope** — do not gate them.

## Decisions (user-answered, LOCKED — do not revisit)

**D-01 — Pure opt-in, wipe the slate.**
Existing preference rows carry no meaning forward. Nobody receives recaps until they
explicitly subscribe. Do **not** grandfather current Admins, do **not** invert existing
`is_opted_out` values into subscriptions.
→ Migration 0294 may simply `RemoveField(is_opted_out)` + `AddField(is_subscribed, default=False)`.
That is the smallest correct migration and literally wipes the slate; no `RunPython` needed.

**D-02 — Admins only may subscribe.**
Recipient scope is unchanged: recaps go to project Admins only. The preference gates
*within* Admins. A non-admin member attempting to subscribe must get a **403**, not a
silently ignored row — reuse `api.security.check_project_admin` (`api/security.py:14`)
rather than writing a second admin check.

## Derived requirements

- Field renamed to positive polarity: `is_subscribed = BooleanField(default=False)`.
  A field named `is_opted_out` whose absence means "opted out" is the 3am-decoding trap —
  the name must match the semantics. Update `verbose_name`, `__str__`, both serializers,
  the viewset's `get_or_create`/update paths, and the OpenAPI-visible field list.
- `send_changes_email` recipient selection becomes a single queryset (drop the per-member
  N+1 loop at `utilities.py:812-820`): Admin members, global `is_opted_out_of_emails=False`,
  **and** an existing `ProjectNotificationPreference(project=…, is_subscribed=True)` row.
- Explicitly-passed `recipients=[...]` keeps bypassing the filter (existing tests rely on it).
- Leave the global `CustomUser.is_opted_out_of_emails` kill switch as-is; it stays an
  additional veto layer above the per-project opt-in.

## Verification expectation

DB-free unit tests in the existing style (`api/tests/test_recap_email.py` uses fakes, no DB)
where possible; a small DB-backed test is acceptable for the recipient queryset and the 403.
Must cover: (a) no preference row ⇒ not a recipient, (b) `is_subscribed=True` ⇒ recipient,
(c) subscribed but globally opted out ⇒ not a recipient, (d) non-admin subscribe ⇒ 403.
