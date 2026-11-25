---
status: built
---

# Church Setup

The configuration layer every Module depends on: the Church Profile, Module
switching, Labels, the first-run setup wizard and the dashboard. It is part
of the core and can't be switched off. App: `apps/church`.

## What exists

- **Church Profile** (`models.py`): one per church; an installation
  holds many ([[0014-church-platform]]). It holds the name, a unique `slug`
  made from the name ("grace-chapel", then "grace-chapel-2"), address,
  phone, email, website, logo (2 MB maximum), currency (three-letter code,
  default PHP), time zone (default Asia/Manila), switched-off Modules,
  Labels and whether setup is finished. Since Phase 9B it also has
  `about`, `show_in_directory` (on), `show_upcoming_services` (off) and
  `members_teams_unlocked` (only the church migrated from before 9B). A
  new installation starts with one church.
  - Nothing falls back to a church: `load()` is gone, and no `church`
    field has a default. `first_church_id()` is kept only because the 9B
    migrations name it.
- **Current Church middleware** (`middleware.py`,
  `CurrentChurchMiddleware`): puts the church a request works in on
  `request.church` and `request.user.current_church`, and activates its
  time zone. A signed-in person works in the church kept in the session
  (`church_id`) while they have an active Membership there (a superuser
  may choose any church); otherwise in their oldest membership's church.
  Visitors and people with no active Membership have no church
  (`request.church` is None): a signed-in person without one sees only
  their own account pages and notifications, and "You're not part of a
  church yet" everywhere else (`church/no_church.html`). The landing page
  is the platform's, with every Module and the neutral wording.
- **Scoping** (`scoping.py`): `for_church`, `get_in_church`,
  `ChurchScopedMixin`, `ChurchFormMixin` and `ChurchFormKwargsMixin`
  ([[Code-Conventions]], "One church's records").
- **Registering a church** (`/churches/register/`,
  `registration.register_church`): the church's name only, plus a new
  account for a visitor who isn't signed in. In one transaction it creates
  the account, the church and slug, its defaults and the person's
  Administrator Membership; any failure leaves nothing. The person then
  works in the new church and goes on to the setup wizard.
- **Slugs** (`models.unique_slug`): made from the name, never shared
  ("grace", "grace-2"), never a reserved word (`RESERVED_SLUGS`, such as
  `register`: a church named "Register" gets `register-church`).
- **Church switcher** (navbar, when a person has more than one church;
  `/church/switch/<slug>/`): POST with the CSRF token. A church without an
  active Membership is 404 (a superuser may choose any). A church whose
  Membership was removed or switched off is dropped at the next request;
  signing out clears the choice.
- **Public homepage** settings section (also the setup wizard's last
  step): "Show the church publicly" (directory and homepage), About (plain
  text, line breaks kept, 2,000 characters), "Show upcoming services" and
  "Accept requests from people outside the church". The church from before
  Phase 9B starts private ([[Design-Decisions]], Phase 9B).
- **Logo**: an image only (PNG, JPEG, GIF or WebP, checked with Pillow), 2
  MB at most, saved under a random name (`church/<random>.<ext>`).
- **Setup wizard** (details, Labels, Modules, Public homepage): a church
  whose setup isn't finished sends its Administrator role holders there
  from the dashboard, such as whoever just registered it; not a superuser
  looking in, nor anyone else holding the permission.
- **Locked Modules**: on the Modules settings page, Members and Teams show
  "Not available yet" for a church without `members_teams_unlocked`, with
  no switch, and can't be posted on.
- **Seeding** (`seeding.py`): `seed_church(church)` gives a new church its
  defaults. Each app registers a seeder in `AppConfig.ready()`: roles
  (Accounts), Theme Tags and Worship Check settings (`songs/defaults.py`),
  the default template and Suggestion Settings (`worship/defaults.py`),
  and the example Occasion Types, switched off (`occasions/defaults.py`).
- **Modules** (`modules.py`): the registry of the Modules (Members,
  Worship, Teams, Occasions, Announcements; [[0005-worship-planning-scope]]).
  `is_enabled(code, church)` needs the church; without one no Module is
  on. Members and Teams have `platform_ready=False`: only a church with
  `members_teams_unlocked` may use them (Phase 9B, §5).
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
