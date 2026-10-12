---
status: complete
quick_id: 260805-mmh
date: 2026-08-05
commit: 1d5c6405
---

# Quick Task 260805-mmh: Fix the `foo = json.loads(e.strerror)` error handling

## What was wrong

`TokenRefreshView.post` ended with:

```python
except Exception as e:
    foo = json.loads(e.strerror)
    return Response({"details": foo["error"]["message"]}, status=400)
```

`e.strerror` is not nonsense. `FirebaseAuth._raise_detailed_error` did
`raise HTTPError(e, response.text)`, and `requests.exceptions.HTTPError` inherits from
`OSError`, whose two-argument constructor is special-cased as `(errno, strerror)`. So
`strerror` held the raw response body. Confirmed empirically:

```
HTTPError(orig, '{"error":{"message":"TOKEN_EXPIRED"}}').strerror  ->  the JSON string
HTTPError('boom').strerror                                          ->  None
hasattr(KeyError('x'), 'strerror')                                  ->  False
```

The defect was that a bare `except Exception` wrapped the whole view body while the handler
assumed the only possible exception was the one Firebase HTTP errors produced. Every other
exception crashed the handler itself, converting a handled 400 into an unhandled 500:

| Trigger | Failure |
|---|---|
| `ConnectionError` / `Timeout` (Firebase unreachable) | `strerror` is `None`, `json.loads(None)` raises `TypeError` |
| 2xx body missing `user_id` / `id_token` / `refresh_token` | `KeyError`, which has no `strerror` |
| Non-JSON body (proxy or CDN error page) | `json.JSONDecodeError` |
| JSON body of an unexpected shape | `KeyError` on `foo["error"]["message"]` |
| `request.data` not a dict | `AttributeError` on `data.get` |

`LoginExistingUserView` (views.py:118) had the same pattern with a narrower inner `try`, so it
degraded to a confusing 400 rather than a 500.

## What changed

Parsing moved into `accounts/firebase_auth.py`. The `strerror` idiom is gone from the codebase
(`grep strerror` returns nothing).

- `parse_firebase_error(text) -> (code, payload)` is the single decoder and never raises. It
  degrades in stages: non-JSON gives `(None, None)`, unexpected shape gives `(None, payload)`,
  the documented shape gives `(code, payload)`.
- Three typed exceptions off a `FirebaseError` base, each carrying `.code`, `.payload`,
  `.status_code`: `FirebaseAuthError` (HTTP error status), `FirebaseUnavailableError` (any
  `RequestException`), `FirebaseResponseError` (2xx with an unusable body).
- All three requests share a `_post()` helper, so `delete_user_account` gets the same guarantees
  it previously had none of. `refresh()` converts its own `KeyError` on the token fields, so the
  view's `user["userId"]` can no longer raise.
- Both views map exceptions through one `firebase_error_response(exc, key, context, fallback)`
  helper, parameterised on the payload key each endpoint already used.

### Contract

Frontend-visible paths are unchanged. Only previously-500 paths moved:

| Case | Before | After |
|---|---|---|
| refresh, valid Firebase error body | 400 `{"details": CODE}` | same |
| login, `INVALID_LOGIN_CREDENTIALS` | 401 `{"error": "Invalid login credentials"}` | same |
| login, other Firebase code | 400 `{"error": CODE}` | same |
| login, JSON body of unexpected shape | 400 `{"error": "Bad Request"}` | same |
| refresh, JSON body of unexpected shape | **500** | 400 `{"details": "Token refresh failed"}` |
| either, ConnectionError / Timeout | **500** / confusing 400 | 503, generic message |
| either, non-JSON body | **500** / confusing 400 | 400, fallback message |
| refresh, 2xx with unusable body | **500** | 502, generic message |
| refresh, missing or blank `refresh` key | round trip to Firebase | 400 `{"details": "MISSING_REFRESH_TOKEN"}` |

The raw payload is never returned to the client, only logged. No new `str(e)` leaks were added.

### Adjacent fix

`except User.DoesNotExist: auth.delete_user_account(user["localId"])` raised out of an `except`
block, bypassing its sibling handler, so the intended 404 was in practice a 500. Now best-effort
with `logger.exception`. The call passes a UID where the `deleteAccount` endpoint wants an
`idToken`, so it fails every time; that was left alone deliberately, since fixing it would start
actually deleting Firebase accounts and needs its own review.

## Tests

`djangoexact/accounts/test_firebase_auth.py`, 27 tests, all DB-free.

The views cannot be exercised through the HTTP layer here: both are decorated with
`@transaction.atomic`, and `Atomic.__enter__` opens a connection to the default database before
any of the method body runs, which `SimpleTestCase` blocks. Probed rather than assumed
(`DatabaseOperationForbidden`). The two pieces the views delegate to are covered directly
instead: `FirebaseAuth` with `requests.post` mocked, and `firebase_error_response` raised and
caught so `logger.exception` sees real `exc_info`. Reasoning is recorded in the test module
docstring.

```
$ ../.venv/bin/python manage.py test accounts.test_firebase_auth
Ran 27 tests in 0.004s
OK
Skipping setup of unused database(s): default.
```

## Deslop pass

Applied before committing, per request:

- Collapsed two guard clauses in `TokenRefreshView` into one; two different error strings for
  "no refresh token supplied" was over-engineered.
- Narrowed `except (FirebaseError, KeyError, TypeError)` to `except FirebaseError`. The
  `KeyError`/`TypeError` branches were unreachable: reaching that handler means
  `sign_in_with_email_and_password` already returned a dict containing `localId`.
- `self.payload = payload if isinstance(payload, dict) else {}` to `payload or {}`, since
  `parse_firebase_error` already guarantees dict-or-None.
- Dropped a redundant `isinstance(text, str)` in `parse_firebase_error` already covered by
  `not text`.
- Removed a test asserting only class inheritance visible in the class definitions.
- Trimmed verbose docstrings and comments that restated the code.

Verified afterwards: `py_compile` clean, 27/27 pass, no unused imports (AST check), no em-dashes.

## Follow-ups raised, not fixed

1. **`VerifyUserEmail` is non-functional and should not simply be repaired.** views.py:201 does
   `email = email.casefold` without calling it, so a bound method reaches
   `firebase_admin_auth.get_user_by_email` and every request with an email returns 400 (the body
   leaks a repr containing a heap address). The endpoint is `AllowAny` and its body is
   `update_user(user.uid, email_verified=True)` with no token, no ownership check and no proof of
   address control. Adding the missing `()` would turn a dead endpoint into an unauthenticated
   "mark any address as verified" primitive, bypassing the `send_email_verification_link` flow and
   defeating the `if not user.email_verified` gate at views.py:110. Needs a ticket that fixes the
   typo and adds authentication together, or deletes the endpoint.
2. `PasswordResetView` and `VerifyUserEmail` both still return `str(e)` to the client
   (pre-existing). `PasswordResetView` returning Firebase's error text also distinguishes
   registered from unregistered addresses, which is a user-enumeration oracle.
3. `delete_user_account` is called with a UID where an `idToken` is expected.
