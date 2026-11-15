# CHORD (new version) Vault

Development notes for the second-option rebuild of CHORD: a church
administration system any Christian church can use without stating its
denomination. These notes describe what the code actually does; update them
with each development task.

## Current status

**Phase 0 done (2026-11-15).** The project has a Django 5.2 setup on
PostgreSQL 17, a custom user model, sign in and sign out, a base page using
Bootstrap and HTMX, one script that runs every check, and a test that
enforces the [[0001-configure-behavior-not-identity|core design rule]]. No
church modules are built yet.

**Next:** Phase 1 (Church Setup and Access) of the [[Development-Plan]].

## Project

- [[Project-Overview]]: goal, adviser constraint, scope
- [[Glossary]]: the project's terms
- [[Technology-Stack]]

## Architecture

- [[Environment-Setup]]: running the project and its database
- [[Code-Conventions]]: code layout, forms, UI and tests
- Decisions (ADRs):
  - [[0001-configure-behavior-not-identity|0001 Configure behavior, not identity]]
  - [[0002-server-rendered-ui|0002 Server-rendered UI with Bootstrap and HTMX]]

## Modules

Each module gets a note in `03-Modules/` once work on it starts (template:
`Templates/Module`).

| Module     | Status      | Note           |
| ---------- | ----------- | -------------- |
| Accounts   | Started     | [[Accounts]]   |
| Services   | Designed    | [[Services]]   |
| Members    | Not started |                |
| Giving     | Not started |                |
| Events     | Not started |                |
| Records    | Not started |                |
| Worship    | Not started |                |
| Ministries | Not started |                |

## Development

- [[Development-Plan]]: phased build order for the management side, with
  task checklists
- [[Development-Log]]: dated record of what changed and how it was verified
