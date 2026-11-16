---
status: in progress
---

# Worship

Planning worship services: the schedule, each service's theme, and (in
later phases) song suggestions, lineups and song pages. Module code
`worship`; apps `apps/worship` (planning) and `apps/songs` (the song pool,
from Phase 4). This is the core of the [[Concept-Brief]].

## What exists

Built in Phase 3 (`apps/worship`):

- **Service Template** (`models/schedule.py`): a church-edited kind of
  service, such as the main weekly service or a youth night.
  - Ordered **Song Slots**, each with a name and an optional feel (upbeat,
    mid-tempo, slow, or any).
  - An optional usual day and start time, given together, which make the
    template schedulable weeks ahead.
  - One neutral template is seeded: "Worship Service" with Opening
    (upbeat), Praise (mid-tempo), Worship (slow) and Response (slow).
  - Templates are switched off, never deleted.
- **Worship Service**: name (the template's name unless given), template,
  date and time, rehearsal time (must be earlier), notes, headcount and a
  cancelled flag. A template can't have two services at the same moment.
  Public UUID in URLs.
- **Theme**: one per service, with title, main scripture, notes and an
  optional **Series**. It records who posted it. The notes are shown only
  to people who plan (those who can edit themes or lineups).
- **Series**: a church-edited list.
- **Screens** (`/worship/`):
  - the schedule: Upcoming and Past, with search over names and themes;
  - a month calendar (`/worship/calendar/?month=YYYY-MM`);
  - a service page with its theme, details and attendance;
  - add and edit a service; post and edit its theme;
  - **Schedule weeks ahead**: adds the chosen template's service on its
    usual day and time for up to 26 weeks, in the church's time zone, and
    skips dates that already have it;
  - settings: Service templates (with their slots) and Series.
- **Rules** are in `scheduling.py` (weekly scheduling, the calendar grid,
  audit fields), and the forms in `forms.py`.
- Every change to services, themes, headcounts and templates is in the
  audit trail.
- Tests: `apps/worship/tests/test_schedule.py`.

## Permissions

| Permission                                   | Allows                                   |
| -------------------------------------------- | ---------------------------------------- |
| `worship.view_worshipservice`                | Seeing the schedule and service pages    |
| `worship.add_worshipservice` / `change_worshipservice` | Scheduling and editing services |
| `worship.change_theme`                       | Posting and editing themes; seeing notes |
| `worship.record_attendance`                  | Recording a headcount                    |
| `worship.*_servicetemplate`, `*_sermonseries` | The settings lists                      |

Default roles ([[Accounts]]):
- **Pastoral Staff** schedule services, post themes, record headcounts and
  manage templates and series.
- **Worship Leader** and **Team Member** see the schedule.
- **Office Staff** see the schedule and record headcounts.

## Church settings this module depends on

- Service Templates and their Song Slots
- Series
- The "worship service" and "sermon" Labels
- The church's time zone (Church Profile)

## Open questions

- None for now. Song suggestions (Phase 5) start from the Theme, and
  lineups (Phase 6) fill the template's Song Slots.
