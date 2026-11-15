# CHORD (new version) Vault

Development notes for the second-option rebuild of CHORD: a church
administration system any Christian church can use without stating its
denomination. These notes describe what the code actually does; update them
with each development task.

## Current status

**Foundation set up (2026-11-15).** Django 5.2 project on PostgreSQL 17, a
custom user model, and the [[0001-configure-behavior-not-identity|core design
rule]] recorded. No church modules built yet.

**Next:** Phase 0 (Engineering baseline) of the [[Development-Plan]].

## Project

- [[Project-Overview]]: goal, adviser constraint, scope
- [[Glossary]]: the project's terms
- [[Technology-Stack]]

## Architecture

- [[Environment-Setup]]: running the project and its database
- Decisions (ADRs):
  - [[0001-configure-behavior-not-identity|0001 Configure behavior, not identity]]

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
