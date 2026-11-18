# CHORD (new version) Vault

Development notes for CHORD: a worship planning system that turns a
service's theme into a confirmed song lineup with tracks, chord sheets and
keys. Any Christian church can use it without stating its denomination.
These notes describe what the code actually does; update them with each
development task.

## Current status

**Phase 3 done (2026-11-17).** The project's scope is now the
[[Concept-Brief]] ([[0005-worship-planning-scope]]). Built so far:

- church setup, users and Roles, and the audit trail;
- [[Members]]: the people directory;
- [[Worship]]: the schedule of worship services, service templates with
  song slots, themes and series, and headcounts.

**Next:** Phase 4 (Song pool) of the [[Development-Plan]].

## Project

- [[Concept-Brief]]: what the system is for, in full
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
Records, Ministries and Events.

## Development

- [[Development-Plan]]: phased build order, with task checklists
- [[Development-Log]]: dated record of what changed and how it was verified
