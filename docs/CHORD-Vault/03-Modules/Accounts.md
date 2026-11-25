---
status: built
---

# Accounts

Users who sign in to CHORD, their Roles and what each Role may do. Part of
the core; it can't be switched off. App: `apps/accounts`.

## What exists

- **User** (`accounts.User`): Django's standard user, shared across
  churches. Users are deactivated, never deleted, so the audit trail keeps
  its actors (there is no delete permission).
- **Membership** (`accounts.Membership`; Phase 9B): a user's place in one
  church, with their roles there and whether it is active. At most one per
  church. Users, Add user and Edit user work on the Current Church's
  memberships; a user from another church gives 404.
- **Permissions per church** (`backends.ChurchRoleBackend`, replacing
  Django's `ModelBackend`): a user holds the permissions of the roles in
  their active Membership in the Current Church, and nothing else
  (`user.groups` and permissions given straight to a user count for
  nothing). Code without a request asks `roles.users_with_perm(church,
  perm)`; `roles.administrators(church)` lists a church's administrators.
  A user object with no `current_church` (loaded outside a request)
  holds no permissions.
- **Role** (`accounts.Role`, built on Django's Group;
  [[0003-editable-roles]]): belongs to one church
  ([[0014-church-platform]]), with a `title` (the name people see, unique
  in the church), description and permissions. Django's `Group.name`
  holds a hidden internal name, `"<church id>:<title>"`. Each church has
  its own six default roles: the first church's came from migrations,
  and a new church gets them from `seed_roles` (`roles.DEFAULT_ROLES`):
  - Administrator
  - Office Staff
  - Pastoral Staff (the [[Concept-Brief]]'s pastor; holds the final say on
    lineups, `worship.finalize_lineup`, by default: [[0008-final-say-permission]])
  - Worship Leader
  - Team Member
  - Church Member (Phase 9A, A1; migration `0005_church_member_role`, not
    made if the church already has a role of that name): only
    `worship.view_worshipservice`, so the schedule, the calendar and each
    service's theme title. Announcements to everyone and their own member
    record need no permission. The service page shows lineups, the team,
    suggestions and theme notes only to holders of their own permissions,
    so a Church Member sees none of them. Tests:
    `apps/accounts/tests/test_church_member.py`.

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
  - set a new password for a user;
  - **Role history** on the edit page (Phase 9A, A2): every change to the
    user's Roles or Active status from the audit trail, newest first, with
    who made it. Changing roles never deletes what the person did before.
  - **History** (`/accounts/users/<id>/history/`, Phase 9A, A3; needs
    `audit.view_auditevent`, linked from the edit page): the person's latest
    50 sign-ins, sign-outs and failed sign-ins (`audit.SignInEvent`,
    recorded from Django's sign-in signals in `apps/audit/signins.py`; a
    failed one keeps only the username tried, never the password) and the
    latest 50 changes they made;
  - **Temporary Passwords** (Phase 9A, A4): accounts made in a batch from
    the Members list ([[Members]]) have `must_change_password`; until the
    person sets their own password (Change password, or a reset by email),
    `PasswordChangeRequiredMiddleware` sends every other page to Change
    password (Sign out, static files and the logo still work);
  - **What a change takes away** (`role_changes.py`): before saving a
    change of roles or active status, the page asks each registered Module
    what the user would lose (Teams: their coming assignments, when they
    leave the team). If anything, it lists it and the editor chooses to end
    or keep it; the choice is recorded on the user in the audit trail.
- **Role management** (`/accounts/roles/`):
  - list roles with their user counts;
  - add, edit and delete roles;
  - the **permission matrix** (`/accounts/roles/permissions/`): every
    managed permission against every role, grouped by app. Viewing it
    needs view-role permission; saving needs change-role permission.
- Every change to users, roles and permissions is in the audit trail.
  Passwords are recorded only as "(new password set)".
- Tests: `apps/accounts/tests/` (sign in, own account, password reset,
  users, roles, matrix, default-role syncing, the Church Member role, role
  history); leaving the team in `apps/teams/tests/test_leaving_team.py`.

### Notifications (core, `apps/notifications`)

Moved out of Teams on 2026-11-24 (Phase 9A, A5, the owner's choice), so
they work whichever Modules a church switches on.

- **Notification** (`models.py`): one person's in-app note, with text, an
  optional link inside CHORD, an optional `key` and when it was read. Never
  email or SMS. The table was renamed from Teams', so no note was lost
  (migrations `teams/0004_move_notification_out` and
  `notifications/0001_initial`).
- `services.py`: `notify(people, text, url, key=...)` (a `key` brings an
  unread note up to date instead of adding another), `unread_count`,
  `mark_read`, `mark_all_read`. Modules decide when to send: Teams
  (`apps/teams/notifying.py`, only while Teams is on) and Worship
  (answers to Occasion Requests).
- The navigation shows **Notifications** with the unread count to everyone
  signed in (`context_processors.notifications`). `/notifications/` lists
  the person's own; opening one marks it read and follows its link (never
  to another site); all can be marked read at once. No permission needed.
- Tests: `apps/notifications/tests/test_notifications.py`, including the
  pages with every Module switched off.

### Settings hub (Phase 9A, A7 part 3)

Users, Roles and permissions and the Audit log are the Settings hub's
"People and access" category (`apps/core/settings_menu.py`); the gear in
the navbar replaced the Administration menu.

**Appearance** (Settings › Personal; `/accounts/appearance/`,
`AppearanceView`, `AppearanceForm`): each person's own light or dark mode,
or Match my device (the default), saved as `User.theme` and applied by
`base.html` before the page draws. Anyone signed in; not audited. Tests:
`apps/accounts/tests/test_appearance.py`.

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
