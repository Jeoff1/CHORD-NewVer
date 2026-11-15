---
status: designed
---

# Services

Church services people request: weddings, burials, private Masses, child
dedications, house blessings and any others the church defines. Not built
yet; this note records the agreed design.

## Design

- The church creates its own **Service Types** ([[Glossary]]). The system
  has no built-in "Wedding" or "Private Mass" feature.
- Each Service Type has its own settings:
  - **Fee Mode**: no fee, fixed fee, optional donation, or amount set per
    request; plus whether the fee can be waived.
  - Whether approval is needed, minimum notice in days, whether an officiant
    is needed, and whether it produces a church record.
  - A **Requirements** checklist the church writes (e.g. baptismal
    certificate, seminar).
  - Extra form fields the church wants to collect.
- A **Service Request** moves through these steps, and steps that don't
  apply are skipped:

  ```
  Requested → Requirements checked → [Payment] → [Approval] → Scheduled → Completed → [Record issued]
  ```

  A Service Type with no fee has no payment step and no unpaid status.
- A neutral **Starter Catalog** (wedding, funeral/burial, baptism/christening,
  child dedication, private Mass/prayer service, house blessing) with no fees
  and few Requirements, which churches copy and edit.

## Church settings this module depends on

Service Types, Fee Mode, Requirements, Labels (e.g. the word for the
officiant).

## Open questions

- How payments are recorded and whether they link to the Giving module.
- What a church record issued by a Service Request contains.
