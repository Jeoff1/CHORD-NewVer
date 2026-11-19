---
status: built
---

# Church Setup

The configuration layer every Module depends on: the Church Profile, Module
switching, Labels, the first-run setup wizard and the dashboard. It is part
of the core and can't be switched off. App: `apps/church`.

## What exists

- **Church Profile** (`models.py`): the single row (pk 1, enforced by a
  database constraint). It holds the name, address, phone, email, website,
  logo (2 MB maximum), currency (three-letter code, default PHP), time zone
  (default Asia/Manila), switched-off Modules, Labels and whether setup is
  finished. Load it with `ChurchProfile.load()`.
- **Middleware** (`middleware.py`) puts the profile on `request.church`
  and activates the church's time zone for each request.
- **Modules** (`modules.py`): the registry of the four Modules (Members,
  Worship, Teams, Announcements; [[0005-worship-planning-scope]]).
  - Each entry has a code, the Django apps that hold its models, a main
    URL (none until the Module is built) and an optional Label key for
    its name.
  - A Module can **need** another: Teams needs Worship, so it counts as
    switched off while Worship is off. The Modules settings page says so.
  - All Modules start switched on, and the church switches off what it
    doesn't use.
  - `ModuleRequiredMixin` returns 404 for a switched-off Module's pages.
  - The navigation and dashboard show only switched-on Modules. Data is
    never deleted when a Module is switched off.
- **Labels** (`labels.py`): member, worship service, sermon, lineup and
  pastor (the people with the final say on a lineup; added in Phase 6).
  - Each has a neutral default singular and plural, which the church can
    edit.
  - Use them in templates with `{% load church %}{% label "sermon" %}`
    (`plural=True` for the plural; `as word` stores it in a variable), and
    in Python with `profile.label_set.get(key)`.
  - Module names follow Labels: if the church calls members
    "Parishioners", the Module is shown as Parishioners.
- **Setup wizard** (`/church/setup/<section>/`): three steps, Church
  details, then Labels, then Modules. It never asks for a denomination.
  - Administrators are sent there from the home page until it's finished;
    other users see a notice.
  - After it's finished, the same forms live at
    `/church/settings/<section>/`.
- **Dashboard** (`/`): a card for each switched-on Module, named in the
  church's words. Modules not built yet say "Coming soon".
- Every profile change is recorded in the audit trail, field by field
  (see [[Code-Conventions#Audit trail]]).
- Tests: `apps/church/tests/` (profile, Labels, module switching, time
  zone, wizard, settings, logo upload).

## Church settings this module depends on

This module *is* the church's settings: Church Profile details, switched-off
Modules and Labels.

## Open questions

- None for now.
