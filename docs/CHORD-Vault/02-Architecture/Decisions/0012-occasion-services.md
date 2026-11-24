---
status: accepted
---

# Occasions: special services are scheduled and requested, without fees

Special services such as weddings and funerals are now part of CHORD's
scheduling, at the adviser's request (2026-11-24). A Service Template can be
marked as an **occasion**, with a usual length, and an occasion's Worship
Service records who it is for, the officiant and the venue. A church member
can send an **Occasion Request**; a holder of `worship.approve_occasion`
(Pastoral Staff by default) approves or declines it, and approving creates
the Worship Service. The calendar shows booked times, and a request that
overlaps one is refused. Approved by the project owner on 2026-11-24
([[Design-Decisions]], "Adviser comments, 24 Nov", A5).

This amends [[0005-worship-planning-scope]], which dropped requested
services. The fees, requirements and church records of the old
[[Services]] design stay out of scope.

## Considered Options

- **The old Services design** (Service Types with Fee Modes, a
  Requirements checklist, payment and church records). It brings finance and
  records back, which stay out of scope, and it is far larger than the
  adviser's request. Rejected.
- **No code: one-off Service Templates only.** A template without a usual
  day already makes a one-off service, but church members couldn't ask for
  one, and nothing would stop two services being booked at the same time.
  Rejected after the owner asked for requests and booked times.
- **A separate Occasion model beside Worship Service.** Two kinds of
  gathering would need two calendars, two clash checks, and two ways into
  the lineup pipeline. Rejected: an occasion is a Worship Service whose
  template is marked as one.

## Consequences

- Follows [[0001-configure-behavior-not-identity]]: the church names its own
  occasion templates, and nothing in code or seed data names one church's
  practice. Two examples common to Christian churches, "Wedding" and
  "Funeral", are seeded **switched off** (the owner's choice, 2026-11-24);
  the church switches on, renames or edits them.
- Approving is a permission, never a check on a role name, like the final
  say ([[0008-final-say-permission]]).
- Every service now has a length (from its template), so the calendar and
  the clash check can tell when a time is booked. People without planning
  permissions see only "Booked".
- Occasion Requests come from signed-in people, so a church member needs an
  account; batch accounts (A4) make that practical. No Member record is
  needed (the owner's choice, 2026-11-24).
- The requester's answer is an in-app Notification, so Notifications moved
  out of Teams into a core app that works whichever Modules are on.
- Hard to reverse: once churches have occasion templates, requests and
  services made from them, removing the feature needs a data migration.
