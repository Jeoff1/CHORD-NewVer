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
  - The navigation and dashboard show only switched-on Modules, and of
    those only the ones the person can open (Phase 9A): each Module names
    the permission its main page needs (`Module.view_permission`: Members
    `members.view_member`, Worship `worship.view_worshipservice`, Teams
    `teams.view_assignment`; Announcements needs none). A person who can
    open none sees a short message instead of cards. Data is never deleted
    when a Module is switched off.
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
- **Dashboard** (`/`): a card for each switched-on Module the person can
  open, named in the church's words. Modules not built yet say "Coming
  soon".
- Every profile change is recorded in the audit trail, field by field
  (see [[Code-Conventions#Audit trail]]).
- Tests: `apps/church/tests/` (profile, Labels, module switching, time
  zone, wizard, settings, logo upload).

### The dashboard and the Settings hub (Phase 9A, A7 part 3)

- **Dashboard** (`church/dashboard.html`, `apps/church/dashboard.py`): a
  greeting with today's date; **Needs your attention** (one sentence, a
  detail and one button per item, the first primary); **Coming up** (the
  next services and occasions); side cards; **Go to**. Each Module
  registers what it adds from its `AppConfig.ready()`: Worship (draft
  lineups to confirm, services with no theme, chord sheets waiting, the
  coming services), Occasions (waiting requests, the coming occasions),
  Teams (My schedule) and Announcements (the latest two). Each only for
  people who may act on it, and nothing from a switched-off Module.
- **Settings hub:** the gear in the navbar replaced the Administration
  menu. The Church Profile's sections (Church details, Labels, Modules) are
  its General category; the setup wizard stays outside it.
  ([[Design-System]], "Page patterns".)
- Tests: `apps/church/tests/test_dashboard_screen.py`,
  `apps/core/tests/test_settings_hub.py`.

### The landing page (Phase 9A, A7)

- **Landing page** (`church/landing.html`, `LandingView`): what a visitor
  who isn't signed in sees at `/`, with links to sign in. Its copy uses
  the church's Labels, its feature list shows only switched-on Modules
  (Teams, Occasions, Announcements), and its footer names the church.
  ([[Design-System]], "Landing page".)
- Tests: `apps/church/tests/test_landing.py`.

## Church settings this module depends on

This module *is* the church's settings: Church Profile details, switched-off
Modules and Labels. While the Worship module is on, the settings tabs also
show **Spotify**, the optional Church Spotify Account, which the Worship
module keeps ([[Worship]], [[0011-church-spotify-account]]).

## Open questions

- None for now.
