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

## Update (2026-11-18)

There are now five default roles: Administrator, Office Staff, Pastoral
Staff, Worship Leader and Team Member ([[0005-worship-planning-scope]]).
The finance and records examples above are out of scope; the reasoning for
editable roles still holds.

## Update (2026-11-25): roles per church

Since [[0014-church-platform]], each church has its own roles. A Role
belongs to a church, its shown name is `title` (unique per church), and
the underlying Django Group keeps a hidden internal name. Roles are given
through a **Membership** in a church, not `user.groups`, and
`ChurchRoleBackend` replaces Django's `ModelBackend`, so a user's
permissions are those of their roles in the Current Church. Permission
checks in views and templates stay Django's own. Each new church gets its
own copy of the default roles, and the last active Administrator rule
applies per church.
