---
status: in progress
---

# Teams

Who serves at each worship service, and when people can't. Module code
`teams`; app `apps/teams`. It needs [[Worship]]: Teams counts as switched
off while Worship is off. Decisions: [[Design-Decisions]], Phase 8
(2026-11-23).

## What exists

Phase 8, part A (roster and availability), built 2026-11-23:

- **Team Parts** (`TeamPart`, a [[Code-Conventions#Church-edited lists|church-edited list]]):
  voices and instruments, at `/teams/settings/parts/`. Seeded with neutral
  defaults: Vocals, Acoustic guitar, Electric guitar, Bass, Keys, Drums
  (migration `0002_default_team_parts`). Switched off, never deleted.
- **Team Profile** (`TeamProfile`): one per user account, holding only the
  person's parts (no vocal range). Not linked to a Member record; the
  [[Members]] module is unchanged. Anyone signed in edits their own
  ("My team parts"); holders of `teams.change_teamprofile` edit anyone's
  from the **Roster** (`/teams/roster/`, `teams.view_teamprofile`).
- **Assignment** (`Assignment`, public UUID): one person, one part, one
  service, with a **reply**: Pending, Accepted or Declined, and who
  assigned it. Rules in `apps/teams/rostering.py`:
  - only active people whose Team Profile has the part, never on one of
    their Blackout Dates, once per part (a person may take two parts);
  - a cancelled or past service (`roster_closed`) takes no new
    assignments, replies or removals;
  - the assigned person replies once, while Pending (`reply`); other
    people get a 404;
  - assigning and adding a blackout lock the person's row, so the two
    can't pass each other.
- **Assigning** (`/teams/services/<id>/assign/`, `teams.add_assignment`):
  choose a part, then one of the people who may take it; the people who
  can't are listed with the reason (already assigned, a blackout date).
  Removing is `teams.delete_assignment`.
- **The service page** shows a **Team** card to holders of
  `teams.view_assignment` while Teams is on (`service_team_context`):
  each part, person and reply; a declined assignment stays, struck
  through and marked "Needs filling" for the leader; the assigned person
  gets Accept and Decline on their own Pending one.
- **Blackout Dates** (`BlackoutDate`): ranges of whole days in the
  church's time zone (`day_bounds`, `service_day`). One that covers a
  Pending or Accepted assignment at a service that isn't cancelled is
  refused, naming it and pointing to Decline (Pending) or a swap
  (Accepted). Days already passed, or the wrong way round, are refused.
  Each person adds and removes only their own.
- **My schedule** (`/teams/`, the module's page, also in the user menu):
  the person's assignments from today on with reply buttons, their parts
  and their coming blackout dates.
- **Audit trail:** assignments (created, reply, removed), Team Profiles
  and Blackout Dates, by name, part and service.

Permissions (default roles, `apps/accounts/roles.py`):

| Permission                  | Worship Leader | Pastoral Staff | Team Member |
| --------------------------- | -------------- | -------------- | ----------- |
| `teams.view_teampart`       | Yes            | Yes            |             |
| `teams.add/change_teampart` | Yes            |                |             |
| `teams.view_teamprofile`    | Yes            | Yes            |             |
| `teams.change_teamprofile`  | Yes            |                |             |
| `teams.view_assignment`     | Yes            | Yes            | Yes         |
| `teams.add_assignment`      | Yes            |                |             |
| `teams.delete_assignment`   | Yes            |                |             |

Replies, a person's own Team Profile and their Blackout Dates need no
permission. The Administrator holds every permission.

Tests: `apps/teams/tests/test_rostering.py` (the rules) and
`apps/teams/tests/test_views.py` (pages, permissions, module switching).

Part B (not built yet): Swap Requests, in-app Notifications and the
Announcements module.

## Church settings this module depends on

- The **Team Parts** list (names, order, switched on or off).
- The church's **time zone** (Church Profile), which sets the days a
  Blackout Date covers.
- The **worship service** Label in messages.
- Whether the Teams module is switched on (and Worship, which it needs).

## Open questions

Choices made while building part A, for the project owner to confirm:

- A reply is given once, while Pending; an Accepted assignment is left by a
  swap (part B) or removed by the leader.
- Anyone signed in may set their own Team Profile; the leader can also set
  anyone's.
- Pastoral Staff see the roster and teams but don't assign by default.
- A past service's team can't be removed either, so it stays as it was.
- Blackout Dates for days already passed are refused.
