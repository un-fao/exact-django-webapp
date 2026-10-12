---
id: 260805-ncv
type: quick
status: complete
completed: 2026-08-05
commit: 8f426740
description: fix LoginExistingUserView orphan cleanup passing localId instead of idToken to delete_user_account
---

# Quick Task 260805-ncv: Summary

## Outcome

The gemini-code-assist finding was **valid**. Fixed in `8f426740`.

`LoginExistingUserView.post` reaches its `except User.DoesNotExist` branch when
Firebase knows an account but Django does not, and tries to delete the orphaned
Firebase account. It passed `user["localId"]` (the UID). But
`FirebaseAuth.delete_user_account` posts `{"idToken": id_token}` to the
Identity Toolkit `accounts:delete` endpoint, which authenticates by ID token,
not by UID. Firebase rejected every one of those calls, so the orphan was never
removed.

The failure was invisible from outside: the `except FirebaseError` guard swallows
the rejection into a log line and the client still receives the same 404. The
cleanup has therefore been silently dead for as long as the branch has existed.

## The reviewer's patch was not applied as given

The suggested diff was anchored one line off. It deleted
`except User.DoesNotExist:` and put the call in its place, which does not parse
and would have removed the branch entirely. Only the diagnosis was adopted; the
actual change is the single key.

## Changes

`djangoexact/accounts/views.py:183`

```
- auth.delete_user_account(user["localId"])
+ auth.delete_user_account(user["idToken"])
```

`djangoexact/accounts/test_firebase_auth.py`, new `OrphanedAccountCleanupTestCase`:

- `test_cleanup_sends_the_id_token_not_the_uid` asserts the delete call receives
  the ID token and that the UID is not among the call args, and that the
  response is still 404.
- `test_cleanup_failure_still_returns_not_found` drives a
  `FirebaseUnavailableError` through the best-effort guard and confirms the
  contract holds: 404 with `{"error": "User not found"}`.

## Reachability check

`user` is rebound at line 145 to the `sign_in_with_email_and_password` dict
before line 152 runs, and line 152 is the only statement in the `try` that can
raise `User.DoesNotExist`. So `user["idToken"]` is always present at line 183.
No restructure was needed.

## Testing technique

The module docstring recorded that these views cannot be driven under
`SimpleTestCase` because `@transaction.atomic` opens a connection before the
body runs. `functools.wraps` leaves the undecorated function on the wrapper, so
`LoginExistingUserView.post.__wrapped__` runs the real branch with no database.
That is what the new tests use, and it lifts the previous limitation for any
future test of these two views.

## Verification

- 29 of 29 tests pass in `accounts/test_firebase_auth.py` (was 27, plus the 2 new).
- The new test was confirmed to **fail** against the pre-fix code:
  `Expected: delete_user_account('id-token-abc')` /
  `Actual: delete_user_account('firebase-uid-123')`. Reverted to the fix, green again.
- `py_compile` clean on both changed modules.
- Run locally with `APP_MODE=test DJANGO_SETTINGS_MODULE=djangoexact.settings`
  under `unittest` after `django.setup()`, which needs no Postgres.

## Not addressed

- The branch deletes a Firebase account as a side effect of a failed login and
  runs inside `@transaction.atomic`, where an external non-transactional call
  cannot be rolled back. That is pre-existing design, out of scope here.
- `VerifyUserEmail` remains a dead `AllowAny` endpoint, already flagged by
  quick task 260805-mmh.
