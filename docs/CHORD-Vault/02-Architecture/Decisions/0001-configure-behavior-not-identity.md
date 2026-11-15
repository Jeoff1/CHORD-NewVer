---
status: accepted
---

# Configure behavior, not identity

CHORD must serve any Christian church without asking for its denomination
(adviser requirement). So every module ships in every installation, and each
church configures what it *does* (which modules are on, which Service Types it
offers, each Service Type's Fee Mode, Requirements and steps, and the Labels it
uses) instead of declaring what it *is*. Terms are defined in [[Glossary]]. Code branches only on these settings,
never on a church's denomination or tradition.

## Considered Options

- **Tradition presets** (the first CHORD: a Tradition such as Roman Catholic or
  Iglesia Ni Cristo configured modules, terms and record types). Rejected:
  choosing a Tradition is choosing a denomination, and every unlisted church
  needs a new preset written in code.
- **A separate system per denomination.** Rejected: too many denominations
  to build and maintain.

## Consequences

- Church-specific practice (paid weddings, private Masses, burial
  requirements) is data the church enters, so supporting a new church never
  needs a code change.
- Defaults must be neutral: starter Service Types ship with no fee and few
  Requirements, and each church adds its own.
- Settings the church enters in a form are harder to report on than fixed
  database columns. Fields every church needs stay as real columns; only
  church-specific extras go in flexible fields.
