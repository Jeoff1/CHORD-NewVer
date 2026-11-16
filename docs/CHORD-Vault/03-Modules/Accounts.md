---
status: built
---

# Accounts

Users who sign in to CHORD, their Roles and what each Role may do. Part of
the core; it can't be switched off. App: `apps/accounts`.

## What exists

- **User** (`accounts.User`): Django's standard user. Users are
  deactivated, never deleted, so the audit trail keeps its actors (there is
  no delete permission).
- **Role** (`accounts.Role`, built on Django's Group;
  [[0003-editable-roles]]): a name, description and permissions. The five
  default roles are created by migrations:
  - Administrator
  - Office Staff
  - Pastoral Staff (the [[Concept-Brief]]'s pastor)
  - Worship Leader
  - Team Member

  Finance, Records Keeper and Ministry Leader were default roles until the
  scope changed ([[0005-worship-planning-scope]]). The migration removed
  each one that no user held; a church that put one to use keeps it.
- **Default permissions** (`roles.py`):
  - After every migrate, the Administrator role receives every managed
    permission.
  - The other default roles receive what `DEFAULT_ROLE_PERMISSIONS` lists,
    once each. Each phase adds its Module's permissions there.
- **Administrator rules:**
  - Administrators are active superusers and holders of the Administrator
    role.
  - The Administrator role can't be deleted, and its matrix column can't
    be edited.
  - The last active administrator can't be deactivated or lose the role.
  - Nobody can deactivate their own account.
- **Own account:**
  - sign in at `/accounts/login/`, and sign out with a POST to
    `/accounts/logout/`;
  - My profile (name and email) at `/accounts/profile/`;
  - change password;
  - reset password by email: the reset email prints to the console in
    development, and an SMTP server can be configured through `.env`.
- **User management** (`/accounts/users/`):
  - a list filtered by Active, Inactive or All, with search;
  - add a user with an initial password and roles;
  - edit details, active status and roles;
  - set a new password for a user.
- **Role management** (`/accounts/roles/`):
  - list roles with their user counts;
  - add, edit and delete roles;
  - the **permission matrix** (`/accounts/roles/permissions/`): every
    managed permission against every role, grouped by app. Viewing it
    needs view-role permission; saving needs change-role permission.
- Every change to users, roles and permissions is in the audit trail.
  Passwords are recorded only as "(new password set)".
- Tests: `apps/accounts/tests/` (sign in, own account, password reset,
  users, roles, matrix, default-role syncing).

## Permissions

| Permission                            | Allows                                  |
| ------------------------------------- | --------------------------------------- |
| `accounts.view_user`                  | Seeing the user list                    |
| `accounts.add_user`                   | Adding users                            |
| `accounts.change_user`                | Editing users, setting their passwords  |
| `accounts.view_role`                  | Seeing roles and the permission matrix  |
| `accounts.add_role` / `change_role` / `delete_role` | Managing roles and saving the matrix |

## Church settings this module depends on

The church's own Roles and their permissions.

## Open questions

- None for now.
