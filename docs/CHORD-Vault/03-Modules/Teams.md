---
status: built
---

# Teams

Who serves at each worship service, when people can't, swaps between them,
and in-app Notifications. Module code `teams`; app `apps/teams`. It needs
[[Worship]]: Teams counts as switched off while Worship is off. Decisions:
[[Design-Decisions]], Phase 8 (2026-11-23).

## What exists

Phase 8, parts A and B, built 2026-11-23:

- **The team is a permission** (`rostering.TEAM_PERMISSION`,
  `teams.view_assignment`; `may_serve`, `team_people`). Only its holders
  have a Team Profile or Blackout Dates, are offered in Assign, can be
  assigned or take a swap. My team parts, the Blackout pages and the swap
  pages need it (`TeamMemberMixin`); people without it who open My schedule
  are sent to their Notifications, and the user menu leaves it out.
- **Team Parts** (`TeamPart`, a [[Code-Conventions#Church-edited lists|church-edited list]]):
  voices and instruments, at `/teams/settings/parts/`. Seeded with neutral
  defaults: Vocals, Acoustic guitar, Electric guitar, Bass, Keys, Drums
  (migration `0002_default_team_parts`). Switched off, never deleted.
- **Team Profile** (`TeamProfile`): one per user account on the team,
  holding only the person's parts (no vocal range). Not linked to a Member
  record; the [[Members]] module is unchanged. Each person edits their own
  ("My team parts"); holders of `teams.change_teamprofile` edit anyone's on
  the team from the **Roster** (`/teams/roster/`, `teams.view_teamprofile`).
- **Assignment** (`Assignment`, public UUID): one person, one part, one
  service, with a **reply**: Pending, Accepted or Declined, and who
  assigned it. Rules in `apps/teams/rostering.py`:
  - only team people whose Team Profile has the part, never on one of
    their Blackout Dates, once per part (a person may take two parts);
  - a cancelled or past service (`roster_closed`) is frozen: no new
    assignments, replies, removals or swaps;
  - the assigned person replies once, while Pending (`reply`); other
    people get a 404. Declining withdraws an open swap request;
  - assigning, taking a swap and adding a blackout lock the person's row,
    so they can't pass each other.
- **Assigning** (`/teams/services/<id>/assign/`, `teams.add_assignment`):
  choose a part, then one of the people who may take it; the people who
  can't are listed with the reason. Removing is `teams.delete_assignment`
  (and withdraws an open swap request).
- **The service page** shows a **Team** card to holders of
  `teams.view_assignment` while Teams is on (`service_team_context`):
  each part, person, reply and "Swap requested"; a declined assignment
  stays, marked "Needs filling" for the leader; the assigned person gets
  Accept and Decline on their own Pending one.
- **Blackout Dates** (`BlackoutDate`): ranges of whole days in the
  church's time zone (`day_bounds`, `service_day`), not already passed.
  One over a Pending or Accepted assignment at a service that isn't
  cancelled is refused (`RosterRefused.assignment` names it), and the page
  links to the way out: Decline on My schedule (Pending), or **Ask for a
  swap** (Accepted), or the open swap request.
- **Swap Requests** (`SwapRequest`, kept as the record after it closes):
  - asked for at `/teams/assignments/<id>/swap/` by the person Pending or
    Accepted on a future service that isn't cancelled; one open request per
    assignment; withdrawn by them while open;
  - **seen by everyone eligible** (`swaps_open_to`, `take_refusal`): on
    the team, has the part, not blacked out that day, not already on that
    service (with any reply);
  - **taken** (`take_swap`) by the first eligible person, with no
    approval: the request's row is locked (`select_for_update(of=self)`),
    the original assignment ends, the taker gets it as Accepted
    (`assigned_by` is the person who handed over), and the request is
    marked Taken. A second taker is told "Someone else took this swap
    first.";
  - the audit trail records the request (with "Handed over by"), the
    assignment that ended and the one made, and "Taken by".
- **My schedule** (`/teams/`, the module's page, also in the user menu
  for people on the team): the person's assignments from today on with
  Accept, Decline, Ask for a swap and Withdraw swap; the swaps they can
  take; their parts; their coming blackout dates.
- **Notifications** (`Notification`, `apps/teams/notifying.py`), in the
  app only:
  - to a service's **Pending and Accepted** assigned people, never the
    person who caused it, when its **lineup is confirmed** or a
    **confirmed lineup is edited** ("edited by <pastor Label> (<name>)"
    or "changed by <name>"), linking to the lineup page. Worship sends
    `apps.worship.signals.lineup_changed`; Teams listens
    (`TeamsConfig.ready`), so Worship never imports Teams;
  - to a person **when they are assigned** (not when they assign
    themself), linking to My schedule;
  - none for a **cancelled or past service**, a draft, or while Teams is
    off;
  - lineup edits collapse: an unread edit note for the same lineup is
    brought up to date (`key`) instead of adding another;
  - the navigation shows **Notifications** with the unread count
    (`apps.teams.context_processors.notifications`); the page
    `/teams/notifications/` opens one (marking it read) or marks all read.
- **Leaving the team** (`leaving.py`, Phase 9A, A2): when a change of
  roles or active status on the user page takes away
  `teams.view_assignment`, the page lists the person's Pending or Accepted
  assignments on coming services that aren't cancelled, and the editor
  ends them (removed as by the leader, open swap requests withdrawn) or
  keeps them. Past ones are never touched. Registered with
  `apps/accounts/role_changes.py` in `TeamsConfig.ready()`; nothing is
  listed while Teams is off. Taking the permission from a whole role in the
  matrix, or deleting a role, doesn't list them.
- **Audit trail:** assignments (created, reply, removed, ended by a swap),
  Team Profiles, Blackout Dates and Swap Requests, by name, part and
  service.

Permissions (default roles, `apps/accounts/roles.py`):

| Permission                  | Worship Leader | Pastoral Staff | Team Member |
| --------------------------- | -------------- | -------------- | ----------- |
| `teams.view_teampart`       | Yes            | Yes            |             |
| `teams.add/change_teampart` | Yes            |                |             |
| `teams.view_teamprofile`    | Yes            | Yes            |             |
| `teams.change_teamprofile`  | Yes            |                |             |
| `teams.view_assignment` (the team) | Yes     | Yes            | Yes         |
| `teams.add_assignment`      | Yes            |                |             |
| `teams.delete_assignment`   | Yes            |                |             |

Replies, swaps, a person's own Team Profile and Blackout Dates need only
`teams.view_assignment`; Notifications need none. The Administrator holds
every permission; a church may give `teams.add_assignment` to a pastor per
user.

Tests: `apps/teams/tests/test_rostering.py` (the rules),
`test_views.py` (pages, permissions, module switching), `test_swaps.py`
(including two people taking one swap at once, on two database
connections), `test_notifications.py` and `test_leaving_team.py`.

## Church settings this module depends on

- The **Team Parts** list (names, order, switched on or off).
- Which roles or users hold `teams.view_assignment` (the team) and
  `teams.add_assignment` (who assigns).
- The church's **time zone** (Church Profile), which sets the days a
  Blackout Date covers.
- The **worship service**, **lineup** and **pastor** Labels in messages.
- Whether the Teams module is switched on (and Worship, which it needs).

## Open questions

Choices made while building part B, for the project owner to confirm:

- **Nobody is notified when a swap is taken or withdrawn**, neither the
  person who handed over nor the leader: decision 6 doesn't list it. Both
  see it on My schedule and the service page.
- **"Already on that service" counts any assignment there, even a
  Declined one**, so someone who declined isn't offered a swap for the
  same service.
- The new assignment from a swap records the person who handed over as
  "assigned by".
- **Unread notes about edits to one lineup collapse** into one, brought up
  to date, so several quick edits don't pile up; confirmations and
  assignments are always new notes.
- Notifications sit in the Teams module (every one of them is about a
  service's team), so they're hidden while Teams is off.
