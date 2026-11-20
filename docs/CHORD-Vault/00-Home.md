# CHORD (new version) Vault

Development notes for CHORD: a worship planning system that turns a
service's theme into a confirmed song lineup with tracks, chord sheets and
keys. Any Christian church can use it without stating its denomination.
These notes describe what the code actually does; update them with each
development task.

## Current status

**Phase 6 done (2026-11-19); Phase 7 in progress (part A done, part B
next).** Updated 2026-11-20 for the next session.

**Pick up here:**
- **Branch:** `phase-7-chords`, at the commit that adds this note. `master`
  is at `bd5a543`: part A was fast-forwarded into it on 2026-11-20, at the
  user's request.
- **Don't merge `phase-7-chords` into `master` again until part B is
  tested.**
- **Progress Check 2 is on 25 Nov 2026.**
- **Phase 7, part A, is done and passed the user's click-through:**
  - ChordPro chord sheets, typed, pasted (chords over words converted on
    the server) or imported from a file;
  - Worship Together's rhythm lines, optional chords and chart marks;
    unreadable marks are kept as written with a warning;
  - approval of team members' sheets;
  - Find chords;
  - chord sheet counts on lineups;
  - a lineup song page with the server-side viewer: service key, personal
    transpose, capo, Nashville numbers and practise-along in the
    recording's key ([[0009-transposition-on-the-server]]);
  - the keys a song was sung in;
  - full lyrics only for people who plan (review F13).
- **Part B is next** ([[Development-Plan]], Phase 7; [[Design-Decisions]],
  Phase 7):
  - the Spotify connection per user, with encrypted tokens;
  - playback;
  - the playlist saved on confirmation, with "Save to Spotify";
  - no web request waiting on a Spotify Retry-After (review F10).
- **Checks:** `scripts/check.ps1` (it runs the tests with `--noinput`); on
  2026-11-20, 678 tests passed with 97% coverage.

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

**Next:** Phase 7, part B; then Phases 8 and 9, in any order.

## Project

- [[Concept-Brief]]: what the system is for, in full
- [[workflow-spec]]: the intended workflow, role by role and step by step
- [[Project-Overview]]: goal, adviser constraint, scope
- [[Glossary]]: the project's terms
- [[Technology-Stack]]

## Architecture

- [[Environment-Setup]]: running the project and its database
- [[Code-Conventions]]: code layout, forms, UI and tests
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

## Modules

Each module gets a note in `03-Modules/` once work on it starts (template:
`Templates/Module`).

| Module              | Status      | Note             |
| ------------------- | ----------- | ---------------- |
| Church Setup (core) | Built       | [[Church-Setup]] |
| Accounts (core)     | Built       | [[Accounts]]     |
| Members             | Built       | [[Members]]      |
| Worship             | In progress | [[Worship]]      |
| Teams               | Not started |                  |
| Announcements       | Not started |                  |

Out of scope: Services ([[Services]] keeps the old design), Giving,
Records, Ministries, Events, leadership appointment and ordination, SMS
messaging, check-in and follow-up, and per-person attendance.

## Development

- [[Development-Plan]]: phased build order, with task checklists
- [[Design-Decisions]]: agreed decisions and safeguards, by phase; they
  win over the Concept Brief, the workflow spec and the plan
- [[Review-Prompt]]: what a review of the code against the workflow spec
  produces; the latest review is [[2026-11-19-Workflow-Review]]
- [[Development-Log]]: dated record of what changed and how it was verified
