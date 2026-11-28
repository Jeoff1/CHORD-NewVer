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
  homepage", for an announcement to everyone only). The homepage shows
  the five latest Public announcements to everyone that aren't archived,
  while Announcements is on (`public.py`). A check
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

### Screens (UI/UX Phase 9, 28 Nov 2026)

From [[UI-UX-Master-Plan]] §15: `announcements/list.html` is a news feed
(`.chord-feed` of `.chord-post` cards): the author's initials and name, the
date, who it is for as a chip (everyone, or one service's team, linked),
the title and text; Archive (author only, as before) asks first; an empty
state offers Post an announcement. Only public announcements reach the
church page (unchanged). Notifications are a core app; their screens,
redesigned in the same phase, are described below.

### Notifications screens (UI/UX Phase 9)

`notifications/list.html`: page header with Mark all as read, rows with an
icon, a red dot and gold wash when unread (and "New:" for screen readers),
the time and Open or Mark as read; an empty state. The header bell
(`includes/app_header.html`) opens a popover (`.chord-bell__pop`) that
loads this page in the background and shows its first eight rows, with Mark
all as read and See all notifications; a click outside or Escape closes it;
without JavaScript, or with Ctrl or Shift, the bell is the plain link. No
new endpoint. Tests: `apps/notifications/tests/test_notification_screens.py`.

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
