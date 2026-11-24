---
status: out of scope
---

# Services

> [!note] Out of scope since 2026-11-16
> Requested services (weddings, burials and the like) are not part of the
> worship planning scope ([[0005-worship-planning-scope]]). Nothing here
> was built. The design is kept in case the scope widens again. In the
> rest of the vault, "service" now means a Worship Service ([[Glossary]]).
>
> **2026-11-24:** weddings, baptisms, funerals and similar occasions are
> back in scope in a smaller form, as the [[Occasions]] Module: Occasions
> and Occasion Requests, with no fees, requirements or records
> ([[0013-occasions-module]]). The design below is still not being built.

## The design that was agreed

- The church creates its own **Service Types**. The system has no built-in
  "Wedding" or "Private Mass" feature.
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

## Open questions when it was shelved

- How payments are recorded.
- What a church record issued by a Service Request contains.
