# CHORD (new version) Vault

Development notes for CHORD: a worship planning system that turns a
service's theme into a confirmed song lineup with tracks, chord sheets and
keys. Any Christian church can use it without stating its denomination.
These notes describe what the code actually does; update them with each
development task.

## Current status

**Simpler church setup (28 Nov 2026), branch `church-setup-simplify`:**
no sermon series, a service date that fills itself in, no Labels page,
no Website, Currency or Time zone in Church details, the Praise Team as
its own switch under Worship, and the Member Directory retired. Still to
come on this branch: Teams kept per church (the Praise Team step for every
church) and a location picker for the church address.

**Dashboard and sidebar redesign (A7), 2026-11-27, on branch
`joy-ui-ux-v3`: built and checked, not committed yet** (the UI/UX owner
reviews the running site first). Every signed-in page now has a green
sidebar with the CHORD logo, the church's own panel and a menu limited to
what the person may open (Management holds Services and Bookings, the
on-screen names of the Occasions Module); the dashboard shows figures for
the next 30 days, the lineup status, Action required, Upcoming and Quick
actions ([[Design-System]], "The app sidebar and dashboard";
[[Design-Decisions]], "Dashboard and sidebar redesign").

**Landing page redesign (A7), 2026-11-27, on branch `joy-ui-ux-v2`:**
committed and pushed (`ee4fc60`), waiting for the lead developer's
approval before it is merged ([[Design-System]], "The landing page").
**Church directory redesign**, **church profile redesign**, the
**sign-in page** (now full-page) and the **church registration
wizard**, the same day and branch: committed and pushed, waiting for the
lead developer's approval before they are merged ([[Design-System]], "The
church directory", "The church profile", "The sign-in page" and
"Registering a church";
[[Development-Log]]). Registering now takes optional details too
([[0014-church-platform]], amended 27 Nov), and is CHORD's only sign-up:
the personal sign-up page is gone and its address redirects there.
Its steps run Church, Profile, Account, Review; the account asks a full
name (middle name and suffix optional) and no username, and people sign
in with their email or username.

**Phase 9C (guided service planning), the top priority (owner,
2026-11-26), is done and merged into `master` (2026-11-26) after the
owner's [[Phase-9C-Click-Through]] passed.** Planning a service now
follows four steps (Theme, Praise Team, Song Lineup, Confirm) with a
next-step panel on the service page; suggestions moved to the Song Lineup
page and confirming goes through a rundown; the pastor may attach the
sermon as a PDF, the Main scripture suggests passages from a stored
public-domain Bible, suggestions read the whole theme, and the lineup
comes first with suggestions beside it ([[0015-lineup-first-suggestions-assist]]; [[Design-Decisions]],
"Phase 9C"). Next: A6, A7, then Phase 10.

**Phase 9B (Church Platform: many churches on one installation) is
done (2026-11-26) and merged into `master` after the owner's
[[Phase-9B-Click-Through]] passed ([[0014-church-platform]],
[[Phase-9B-Plan]]).** Phase 9A was paused for it: A1 (Church Member
role), A2 (a role change keeps history), A3 (user history), A4 (batch
accounts) and A5 (occasions, their own Module; Notifications moved into
a core app) done 2026-11-24; A6 (member reports) is next, after the owner decides
about "who attended a service". A7 part 2, the owner's design system and
the Spotify player card, built 2026-11-25 on branch `ui-design-system`
([[Design-System]]), with the public landing page, merged into `master` the same
day.** Phase 8 done (2026-11-23). Updated
2026-11-26.

**Pick up here:**
- **Branch:** Phases 9B and 9C are merged into `master` (2026-11-26), as
  are 9A's A1 to A5.
- **Phase 9B** ([[Development-Plan]]; rules and tests in
  [[Design-Decisions]], "Phase 9B"; design and progress notes in
  [[Phase-9B-Plan]]): slices a (foundations) to e (public pages) done.
- **Next after the merge:** the rest of Phase 9A (A6 member reports, A7
  UI pass), then Phase 10.
- **Phase 9A** ([[Development-Plan]]; rules in [[Design-Decisions]],
  "Adviser comments, 24 Nov"): A1 Church Member role, A2 a role change
  keeps history, A3 user history, A4 batch accounts, A5 occasions
  ([[0013-occasions-module]]), A6 member reports, A7 UI pass (wireframes
  first). More adviser comments may come.
- **Waiting on the user:** "who attended a service" (on hold, before A6);
  what to show at Progress Check 2 and put in the Progress Report.
- **Phase 9** is built only if time remains before the final presentation
  (1–4 Dec 2026), an exception recorded in `AGENTS.md`.
- **Progress Check 2 is on 25 Nov 2026.**
- **Phase 8, part A:** [[Teams]]: Team Parts, Team Profiles (parts only),
  Assignments with replies, Blackout Dates, My schedule, the Team card on
  the service page; the playlist fix (a stored playlist is made again only
  on a 404, or a 403 from a playlist the connected account doesn't own).
- **Phase 8, part B:** the team is the permission `teams.view_assignment`;
  Swap Requests (first eligible taker, under a row lock); in-app
  Notifications with an unread count; [[Announcements]] to everyone or one
  service's team.
- **Choices to confirm:** "Open questions" in [[Teams]] and
  [[Announcements]].
- **Checks:** `scripts/check.ps1` (from `.venv`, about 70 seconds;
  `-Quick` skips coverage); on 2026-11-25, on `tooling-fast-checks`,
  1049 tests passed with 97% coverage.
- **Waiting on the user, too:** whether the pastor may create batch
  accounts (only the Administrator can today; see the plan's decisions).

Built so far (scope: the [[Concept-Brief]], [[0005-worship-planning-scope]]):

- church setup, users and Roles, and the audit trail;
- [[Members]]: the people directory;
- [[Worship]]: the schedule of worship services, service templates with
  song slots, themes and series, and headcounts;
- [[Worship]]'s song pool: songs from Spotify, lyrics from LRCLIB, and
  their analysis by ONNX models (the model's worship score, kept apart
  from the Trusted Artist bonus; theme tags; feel; embedding), with the
  song library to correct it;
- [[Worship]]'s song suggestions: from a service's theme to ranked songs
  placed in its song slots, with reasons, carried out by one search worker
  ([[0007-search-worker]]) under the Spotify safeguards, and seen only by
  the people who plan the service. After the first smoke test (2026-11-18):
  fixed match labels, feel as a placement preference with one-click
  corrections, the church's worship check rules, and one version of each
  song;
- [[Worship]]'s lineups (Phase 6, done 2026-11-19): a lineup saved from
  the reviewed suggestions as its own copy; swap, lock, reorder, remove,
  add from the pool and regenerate; confirmation by the worship leader or
  the pastor, whose final say is the permission `worship.finalize_lineup`
  ([[0008-final-say-permission]]); reopening and sending back. Team
  members see a lineup only once it is confirmed. Confirming records
  Suggestion Feedback; song usage from confirmed lineups now counts in
  ranking; reports for song usage (with CSV) and attendance.
- [[Worship]]'s chord sheets (Phase 7, part A, 2026-11-20), as above.
- [[Worship]]'s Spotify Connection, playback and Lineup Playlist (Phase 7,
  part B, 2026-11-22), as above.
- [[Teams]] and [[Announcements]] (Phase 8, 2026-11-23): the roster,
  availability, swaps, Notifications and announcements, as above.

**Next:** Phase 9A, then Phase 10; Phase 9 if time remains.

## Project

- [[Concept-Brief]]: what the system is for, in full
- [[workflow-spec]]: the intended workflow, role by role and step by step
- [[Project-Overview]]: goal, adviser constraint, scope
- [[Glossary]]: the project's terms
- [[Technology-Stack]]

## Architecture

- [[Environment-Setup]]: running the project and its database
- [[Code-Conventions]]: code layout, forms, UI and tests
- [[Design-System]]: the owner's colours, fonts, icons, dark mode and player card
- Decisions (ADRs):
  - [[0001-configure-behavior-not-identity|0001 Configure behavior, not identity]]
  - [[0002-server-rendered-ui|0002 Server-rendered UI with Bootstrap and HTMX]]
  - [[0003-editable-roles|0003 Editable roles on Django groups, with a fixed Administrator]]
  - [[0004-custom-field-values-as-json|0004 Custom Field values stored as JSON on the record]]
  - [[0005-worship-planning-scope|0005 Worship planning is the scope; church administration stays light]]
  - [[0006-onnx-runtime-for-song-analysis|0006 Song analysis runs ONNX models, with a keyword stand-in]]
  - [[0007-search-worker|0007 One search worker, a management command polling the database]]
  - [[0008-final-say-permission|0008 The final say on lineups is its own permission]]
  - [[0009-transposition-on-the-server|0009 Chord sheets are transposed on the server, in Python]]
  - [[0010-store-own-playlist-id|0010 CHORD stores the ID of a playlist it created itself]]
  - [[0011-church-spotify-account|0011 An optional Church Spotify Account holds the Lineup Playlists]]
  - [[0012-occasion-services|0012 Occasions: special services are scheduled and requested, without fees]] (superseded by 0013)
  - [[0013-occasions-module|0013 Occasions are their own Module, apart from worship services]]

## Modules

Each module gets a note in `03-Modules/` once work on it starts (template:
`Templates/Module`).

| Module              | Status      | Note             |
| ------------------- | ----------- | ---------------- |
| Church Setup (core) | Built       | [[Church-Setup]] |
| Accounts (core)     | Built       | [[Accounts]]     |
| Notifications (core) | Built      | [[Accounts]] ("Notifications") |
| Members             | Retired     | [[Members]]      |
| Worship             | In progress | [[Worship]]      |
| Teams               | Built       | [[Teams]]        |
| Occasions           | Built       | [[Occasions]]    |
| Announcements       | Built       | [[Announcements]] |

Out of scope: the old Services design with fees, requirements and records
([[Services]]; occasions are in scope as the [[Occasions]] Module, [[0013-occasions-module]]),
Giving, Records, Ministries, Events, leadership appointment and
ordination, SMS messaging, check-in and follow-up, and per-person
attendance (on hold).

## Development

- [[Development-Plan]]: phased build order, with task checklists
- [[Design-Decisions]]: agreed decisions and safeguards, by phase; they
  win over the Concept Brief, the workflow spec and the plan
- [[Review-Prompt]]: what a review of the code against the workflow spec
  produces; the latest review is [[2026-11-19-Workflow-Review]]
- [[Development-Log]]: dated record of what changed and how it was verified
