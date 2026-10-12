---
id: 260805-ncv
type: quick
status: in-progress
created: 2026-08-05
description: fix LoginExistingUserView orphan cleanup passing localId instead of idToken to delete_user_account
---

# Quick Task 260805-ncv: Orphan Firebase cleanup passes the wrong credential

## Goal

`accounts/views.py:183` calls `auth.delete_user_account(user["localId"])`.
`FirebaseAuth.delete_user_account` (`accounts/firebase_auth.py:91`) posts
`{"idToken": id_token}` to the Identity Toolkit `accounts:delete` endpoint,
which authenticates by ID token, not by UID. Passing `localId` makes Firebase
reject the request, so the orphaned Firebase account is never cleaned up.

Reported by gemini-code-assist on the open PR (High Priority).

## Analysis

Reachability of the buggy line, traced through `LoginExistingUserView.post`:

- line 137 binds `user` to a `firebase_admin` `UserRecord`
- line 145 rebinds `user` to the `sign_in_with_email_and_password` dict, which
  carries both `localId` and `idToken`
- line 152 `User.objects.get(firebase_uid=user["localId"])` is the only
  statement in the `try` that can raise `User.DoesNotExist`

So at line 183 `user` is always the sign-in dict and `user["idToken"]` is
present. The fix is a single key change, not a restructure.

The reviewer's suggested diff is anchored wrong: it deletes the
`except User.DoesNotExist:` line and replaces it with the call, which would not
parse. Only the diagnosis is adopted.

## Tasks

### Task 1: Pass the ID token to the delete call

- **files:** `djangoexact/accounts/views.py`
- **action:** change `auth.delete_user_account(user["localId"])` to
  `auth.delete_user_account(user["idToken"])`. Keep the surrounding
  `except FirebaseError` best-effort guard as is.
- **verify:** `py_compile` on the module.
- **done:** no caller passes a UID into an ID-token parameter.

### Task 2: Lock the regression with a DB-free test

- **files:** `djangoexact/accounts/test_firebase_auth.py`
- **action:** exercise the orphan-cleanup branch and assert
  `delete_user_account` receives the ID token. The module docstring records
  that `@transaction.atomic` prevents driving these views without a database;
  call the undecorated body through `post.__wrapped__` so the branch runs with
  no connection, and patch `User.objects.get` to raise `User.DoesNotExist`.
- **verify:** run the module under `unittest` with `django.setup()`; all tests
  must pass and the new test must fail against the pre-fix key.
- **done:** the wrong-key form is caught by the suite.

## must_haves

- **truths**
  - The orphan cleanup path sends a credential Firebase actually accepts.
  - The existing 404 response and best-effort semantics are unchanged.
- **artifacts**
  - `260805-ncv-SUMMARY.md`
- **key_links**
  - `djangoexact/accounts/views.py`
  - `djangoexact/accounts/firebase_auth.py`
  - `djangoexact/accounts/test_firebase_auth.py`

## Constraints

- No public API change: the endpoint still returns 404 for an orphaned account.
- No em-dashes (project rule).
