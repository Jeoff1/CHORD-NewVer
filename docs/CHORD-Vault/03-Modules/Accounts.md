---
status: started
---

# Accounts

Users who sign in to CHORD.

## What exists

- Custom user model `accounts.User` (`apps/accounts/models.py`), a plain
  extension of Django's standard user with no extra fields yet. It was added
  before the first migration because switching to a custom user model later
  is very difficult.
- Registered in the Django admin.
- Sign in at `/accounts/login/` and sign out (POST only) at
  `/accounts/logout/`, using Django's own views and
  `accounts/login.html`. Signed-in users who open the sign-in page are
  sent to the home page.
- Tests: `apps/accounts/tests/test_sign_in.py`.

## Church settings this module depends on

None yet.

## Open questions

- Roles, password change and reset, and user management come in Phase 1
  of the [[Development-Plan]].
