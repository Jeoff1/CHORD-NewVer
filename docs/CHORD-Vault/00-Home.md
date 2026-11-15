# CHORD (new version) Vault

Development notes for the second-option rebuild of CHORD: a church
administration system any Christian church can use without stating its
denomination. These notes describe what the code actually does; update them
with each development task.

## Current status

**Phase 1 done (2026-11-16).** A church can set itself up through the
setup wizard (details, Labels, Modules) without stating a denomination,
switch Modules on and off, and use its own wording. Users, editable Roles,
the permission matrix, password reset and the audit trail work. No church
Modules (Members, Giving and the others) are built yet.

**Next:** Phase 2 (Members) of the [[Development-Plan]].

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
  - [[0003-editable-roles|0003 Editable roles on Django groups, with a fixed Administrator]]

## Modules

Each module gets a note in `03-Modules/` once work on it starts (template:
`Templates/Module`).

| Module     | Status      | Note           |
| ---------- | ----------- | -------------- |
| Church Setup (core) | Built  | [[Church-Setup]] |
| Accounts (core)     | Built  | [[Accounts]]   |
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
