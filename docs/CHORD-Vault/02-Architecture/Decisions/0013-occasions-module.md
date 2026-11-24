---
status: accepted
---

# Occasions are their own Module, apart from worship services

Weddings, baptisms, funerals and other special services are not worship
services: they have no theme, song lineup or team. They are the
**Occasions** Module (`apps/occasions`), with their own form, list and
records: an **Occasion** of a church-edited **Occasion Type**. They share
the Worship calendar, and no two bookings may overlap. Decided by the
project owner on 2026-11-24, replacing [[0012-occasion-services]], which
made an occasion a kind of Worship Service.

What 0012 decided about scope still holds: occasions are requested by
people who sign in and approved with a permission; there are no fees,
requirements or church records.

## Considered Options

- **An occasion as a Worship Service whose template is marked as one**
  (0012, built and replaced the same day). One calendar and one clash
  check for free, but weddings sat in the worship schedule, on the service
  form and with a lineup the owner didn't want. Rejected by the owner.
- **Separate pages over the same Worship Service records.** Less rework,
  and occasions could still have a lineup and team. Rejected: the owner
  chose fully separate records with no music side.

## Consequences

- Occasions requires Worship (it counts as switched off while Worship is
  off), because booked times are shared with worship services.
- Worship never imports Occasions. The calendar shows occasions through a
  registry, `apps/worship/bookings.py`, which Occasions joins in
  `OccasionsConfig.ready()`; the clash check lives in Occasions, which
  reads Worship's services.
- Every Service Template has a usual length, so a worship service books
  time too. Only occasions (added, moved, requested or approved) are
  checked for clashes; scheduling a worship service is not, as before.
- An occasion has no lineup, suggestions or team assignments. If a church
  wants music at one, it adds a worship service for it as before.
- Follows [[0001-configure-behavior-not-identity]]: the church names its
  own Occasion Types. "Wedding", "Baptism" and "Funeral" are seeded as
  examples, switched off.
- Hard to reverse: once churches have occasions and requests, merging them
  back into worship services needs a data migration.
