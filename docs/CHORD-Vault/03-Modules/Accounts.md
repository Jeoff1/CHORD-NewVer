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

## Church settings this module depends on

None yet.

## Open questions

- Roles and permissions (who can manage services, giving, records) are not
  designed yet.
