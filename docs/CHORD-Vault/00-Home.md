# CHORD (new version) Vault

Development notes for CHORD: a worship planning system that turns a
service's theme into a confirmed song lineup with tracks, chord sheets and
keys. Any Christian church can use it without stating its denomination.
These notes describe what the code actually does; update them with each
development task.

## Current status

**Phase 5 done (2026-11-18).** The project's scope is now the
[[Concept-Brief]] ([[0005-worship-planning-scope]]). Built so far:

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

**Next:** Phases 7 (song pages: chords and playback), 8 (teams and
announcements) and 9 (learning to rank) of the [[Development-Plan]], in
any order.

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
