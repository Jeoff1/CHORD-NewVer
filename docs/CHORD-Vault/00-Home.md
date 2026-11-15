# CHORD (new version) Vault

Development notes for the second-option rebuild of CHORD: a church
administration system any Christian church can use without stating its
denomination. These notes describe what the code actually does; update them
with each development task.

## Current status

**Phase 2 done (2026-11-16).** Church setup, users and Roles, and the
audit trail work. The first church Module is built: [[Members]].
- the people directory, with households;
- church-edited statuses and Custom Fields;
- private details visible only with permission, and a "My record" page;
- CSV import with a preview, and CSV export.

**Next:** Phase 3 (Ministries and Events) of the [[Development-Plan]].

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
  - [[0004-custom-field-values-as-json|0004 Custom Field values stored as JSON on the record]]

## Modules

Each module gets a note in `03-Modules/` once work on it starts (template:
`Templates/Module`).

| Module     | Status      | Note           |
| ---------- | ----------- | -------------- |
| Church Setup (core) | Built  | [[Church-Setup]] |
| Accounts (core)     | Built  | [[Accounts]]   |
| Services   | Designed    | [[Services]]   |
| Members    | Built       | [[Members]]    |
| Giving     | Not started |                |
| Events     | Not started |                |
| Records    | Not started |                |
| Worship    | Not started |                |
| Ministries | Not started |                |

## Development

- [[Development-Plan]]: phased build order for the management side, with
  task checklists
- [[Development-Log]]: dated record of what changed and how it was verified
