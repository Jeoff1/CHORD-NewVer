---
status: accepted
---

# Editable roles on Django groups, with a fixed Administrator

Churches split work differently (one secretary does everything; another has
a finance team and records keeper), so **Roles** are church-editable. Each
Role is a Django `Group` (multi-table subclass `accounts.Role`), so Django's
own permission checks apply. Six default roles are seeded once; the church
can rename them, change their permissions, delete them, or add its own.
The **Administrator** role always holds every CHORD permission and can't be
deleted, and the last active administrator can't be removed, so a church
can't lock itself out.

## Considered Options

- **Fixed roles in code** (the original CHORD's approach): simple, but it
  hard-codes one way of organising church work, against
  [[0001-configure-behavior-not-identity]].
- **A separate Role model with its own permission backend**: duplicates
  what Django groups already do.

## Consequences

- Seeded roles carry a stable `key`. Later phases grant their new
  permissions to default roles by listing them in
  `DEFAULT_ROLE_PERMISSIONS` (`apps/accounts/roles.py`). Each is granted
  once after migrations, and if the church removes it, it is never
  re-granted.
- Only permissions that CHORD's models declare appear in the permission
  matrix. Framework permissions (sessions, admin log) and stale rows are
  hidden.
