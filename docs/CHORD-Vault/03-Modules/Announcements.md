---
status: built
---

# Announcements

Notes to everyone, or to one service's team. Module code `announcements`;
app `apps/announcements`. Decisions: [[Design-Decisions]], Phase 8
(decided 2026-11-23).

## What exists

Built 2026-11-23 (Phase 8, part B):

- **Announcement** (`Announcement`, public UUID): its church, title,
  message, audience, an optional service, author, when it was archived,
  and `visibility`: Internal, or Public ("Also show it on the church's
  homepage", for an announcement to everyone only; shown on the homepage
  from Phase 9B slice e). A check
  constraint keeps a service only on a service-team announcement.
- **Audiences** (`services.visible_to`):
  - **Everyone**: everyone working in the church;
  - **One service's team**: that service's assigned people whose reply is
    Pending or Accepted (see [[Teams]]), plus its author. It is offered,
    and shown, only while Teams is on, and only for a coming service that
    isn't cancelled.
- **Posting** (`/announcements/new/`) is the permission
  `announcements.add_announcement`, held by Pastoral Staff and Worship
  Leader by default (and the Administrator). Reading
  (`/announcements/`) needs only to be signed in.
- **No expiry:** only the author archives an announcement (others get a
  404); then nobody sees it.
- **Audit trail:** posting and archiving.
- The form uses the church's **worship service** Label.

Tests: `apps/announcements/tests/test_announcements.py` (audiences, the
Teams-off case, archiving, permissions, module switching).

Phase 9A, A7 part 3: the dashboard's side column shows the latest two
announcements the person may see (`dashboard.py`).

## Church settings this module depends on

- Whether the Announcements module is switched on; "one service's team"
  also needs Teams (and so Worship) on.
- Which roles or users hold `announcements.add_announcement`.
- The **worship service** Label.

## Open questions

Choices made while building, for the project owner to confirm:

- Service-team announcements already posted are **hidden while Teams is
  off**, along with the option, since nobody can see that team then.
- Their author always sees them (while Teams is on), even if not on that
  team.
- Posting an announcement sends no Notification; people read them on the
  Announcements page.
