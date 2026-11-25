---
status: built
---

# Occasions

Weddings, baptisms, funerals and other special services: booked by the
pastor, requested by members, kept apart from worship services
([[0013-occasions-module]]). Module code `occasions`; app `apps/occasions`.
It needs [[Worship]]: Occasions counts as switched off while Worship is
off. Decisions: [[Design-Decisions]], "Adviser comments, 24 Nov", A5.

## What exists

Built in Phase 9A, A5 (2026-11-24):

- **Occasion Type** (`OccasionType`, a
  [[Code-Conventions#Church-edited lists|church-edited list]] at
  `/occasions/settings/types/`): a name and a **usual length** (15 minutes
  to a day). "Wedding" (120), "Baptism" (60) and "Funeral" (90) are seeded
  **switched off** (migration `0002_seed_occasion_types`). Switched off,
  never deleted; the list's Active switch turns a type on or off without
  opening it.
- **Occasion** (`Occasion`): its type, date and time, length (the type's
  usual length unless changed), **For** (who it is for, as text),
  **Officiant** (a user), **Venue**, notes and **Cancelled**. No theme,
  lineup or team. Public UUID in URLs. Every change is in the audit trail.
- **Occasion Request** (`OccasionRequest`): who asked, the type, the
  preferred date and time, For, a note for the approvers, and its status:
  **Pending**, then **Approved** (linked to the Occasion it booked),
  **Declined** (with the reason) or **Withdrawn**.
- **Rules** (`rules.py`):
  - **No double booking:** adding, moving, requesting or approving an
    occasion is refused when its time overlaps a worship service (its
    template's length) or another occasion of the same church that isn't
    cancelled; each church has its own calendar.
    Back-to-back times are fine; a cancelled booking frees its time.
    Bookings take a database lock (`BOOKINGS`), so two at once take turns.
  - a request needs an active type and a time that hasn't passed;
    approving may move the time and set the officiant (one of the
    church's active people) and venue, and
    copies the request's note onto the Occasion; declining needs a
    reason; only the requester withdraws, while Pending; a decided request
    can't be decided again;
  - the requester gets a **Notification** (core, [[Accounts]]) when it is
    approved or declined, linking to My requests.
- **The calendar** (Worship's, `/worship/calendar/`) shows occasions
  through `apps/worship/bookings.py`: with their name and a link for
  holders of `occasions.view_occasion`; as "<start> to <end> Booked" for
  everyone else, and not at all when cancelled. A clash names an occasion
  only for people who may see it. Occasions never appear in the worship
  schedule list.
- **Screens** (`/occasions/`, the Module page, which sends people who see
  occasions to the list and others to My requests):
  - **Occasions**: Upcoming and Past, with search; Add an occasion; each
    occasion's page with Edit (and Cancel on the edit form);
  - **Requests** (for approvers, with the Pending count on the tab):
    Pending, then the latest 50 decided; each request's page with Approve
    and Decline, showing any clash;
  - **My requests**: Request an occasion; Withdraw while Pending;
  - **Settings**: Occasion types.
- Tests: `apps/occasions/tests/test_occasions.py` (42: setup and default
  permissions, booking and clashes with services and occasions,
  back-to-back and cancelled times, moving, the clash message, requests,
  approving, moving the time, refused approvals, declining, withdrawing,
  notifications with Teams off, every page and who may open it, the
  settings list, switching Occasions or Worship off, the calendar).

Phase 9A, A7 part 3: Occasion types is in the Settings hub's "Teams and
occasions" category; the dashboard shows waiting requests to approvers
and the coming occasions to people who may see them (`dashboard.py`).

## Permissions

| Permission                          | Allows                                          | Default roles |
| ----------------------------------- | ----------------------------------------------- | ------------- |
| `occasions.view_occasion`           | Seeing occasions in full (list, page, calendar) | Pastoral Staff, Worship Leader, Office Staff |
| `occasions.add_occasion` / `change_occasion` | Adding, editing and cancelling occasions | Pastoral Staff |
| `occasions.*_occasiontype`          | The Occasion types settings                     | Pastoral Staff |
| `occasions.request_occasion`        | Requesting; My requests                         | Church Member, Pastoral Staff, Worship Leader |
| `occasions.approve_occasion`        | Approving and declining requests                | Pastoral Staff |

The Administrator holds every permission. Team Members and Church Members
see others' occasions only as "Booked".

## Church settings this module depends on

- The **Occasion Types** list: names, usual lengths, which are switched on.
- Service Templates' usual length ([[Worship]]), which sets how long a
  worship service books.
- Who holds the permissions above.
- The church's time zone (Church Profile).
- Whether Occasions is switched on (and Worship, which it needs).

## Open questions

- "For" is text, not linked to Member records (Worship and Occasions don't
  depend on Members).
- Scheduling a worship service doesn't check for clashes with occasions;
  only occasions are checked. Ask the owner if a warning is wanted there.
