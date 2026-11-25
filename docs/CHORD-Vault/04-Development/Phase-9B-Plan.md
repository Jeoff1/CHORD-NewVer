# Phase 9B: Church Platform — plan for approval

Status: **approved by the owner on 2026-11-25**, with the recommended
answer to every question in section 11 ([[0014-church-platform]]).
Written 2026-11-25. Follows the owner's brief "New phase: Church Platform
(multi-church), before the rest of Phase 9A" (Option B, presentation
version; final presentation 1–4 Dec 2026).

## Context for a new session (what the codebase looks like today)

- Today one church is wired into the code in three places:
  - `ChurchProfile` (`apps/church/models.py`) is a single row: pk=1, the
    `church_profile_single_row` CheckConstraint, `SINGLETON_PK`, `load()`
    and a `save()` that forces pk=1. `ChurchProfileMiddleware`
    (`apps/church/middleware.py`) puts it on `request.church` and switches
    on its time zone.
  - Roles are `accounts.Role`, a multi-table subclass of Django `Group`, so
    their names must be unique across the whole installation. Seeded roles
    carry a unique `key`.
  - Permissions come from `user.groups` through Django's `ModelBackend`, so
    they apply everywhere.
- Three more singletons use pk=1: `SuggestionSettings`
  (`apps/worship/models/suggestions.py`), `WorshipCheckSettings` and
  `ChurchSpotifyAccount` (`apps/songs/models.py`, `apps/songs/connections.py`).
- Default data is created only by data migrations: roles
  (`accounts/0003`, `0004`, `0005`), theme tags (`songs/0002`), the default
  template (`worship/0002`), occasion types (`occasions/0002`), team parts
  (`teams/0002`) and member lists (`members/0002`). `DEFAULT_ROLE_PERMISSIONS`
  and `sync_default_role_permissions()` are in `apps/accounts/roles.py`.
- Modules and module gating are in `apps/church/modules.py` (`is_enabled`,
  `ModuleRequiredMixin`). Church-edited lists use `ChoiceItem` in
  `apps/core/setting_lists.py` (its `name` is unique across the installation).
- Test builders are in `apps/core/testing.py` (`make_user(roles=, perms=)`
  grants permissions straight to the user, `complete_setup()` uses
  `ChurchProfile.load()`).
- There are 172 `has_perm`/`PermissionRequiredMixin` call sites, about 250
  query sites in views and services, 64 test files and 1049 tests.
- The landing page is `apps/church/templates/church/landing.html` (button
  "Sign in to your church" at line 35, CTA "Sign in with the account your
  church gave you." at line 187).
- **Branch:** `phase-9b-church-platform`, from `master` (which already
  holds 9A's A1 to A5). It is merged into `master` only when the full
  check passes.
- **Checks:** `.\scripts\check.ps1 -Quick` after each change, the full
  check before each commit (the pre-commit hook runs it). Never bypass
  the hook.

## 1. Data model

**Church.** Keep the class name `ChurchProfile` so its ~30 references
don't change. The Glossary calls it "Church", and its record is the Church
Profile.

- Removed: the `church_profile_single_row` rule, `SINGLETON_PK`, `load()`
  and the pk-forcing `save()`.
- Added:
  - `slug`, unique and made from the name
  - `about`
  - `show_in_directory` (on by default)
  - `show_upcoming_services` (off by default)
  - `members_teams_unlocked` (True only for the migrated first church; see §5)
- Name, logo, address, phone, email, website, time zone, Labels and Modules
  are already on it, so they become per church with no extra work.

**Membership (new, in `accounts`).**

- Fields: `user`, `church`, `roles` (many-to-many to Role), `is_active`,
  `created_at`.
- Each user has at most one Membership per church.
- A User stays global and can have memberships in many churches, or none.

**Role.**

- Gets a `church` FK, and `key` becomes unique per church.
- New field `Role.title`, shown in the UI and unique per church. The
  underlying `Group.name` must stay unique across the installation, so it
  becomes a hidden internal name like `"<church id>:<title>"`. The role
  forms edit `title`.
- Each new church gets its own copy of the six default roles.

**Which models get a `church` foreign key** (★ = direct FK; the rest are
scoped through their parent):

| Area | Gets a direct `church` FK | Scoped through its parent |
|---|---|---|
| Worship schedule | ★ ServiceTemplate, ★ SermonSeries, ★ WorshipService | TemplateSlot (template), Theme (service) |
| Suggestions | ★ Season; SuggestionSettings (one-to-one with church, replacing pk=1) | SearchRun (service), Suggestion (run) |
| Lineups | — | Lineup, LineupItem, SuggestionFeedback (service/lineup) |
| Song library | ★ Song, ★ ThemeTag, ★ TrustedArtist; WorshipCheckSettings (one-to-one); ChurchSpotifyAccount (one-to-one) | ChordSheet (song); usage comes from lineups |
| Occasions | ★ OccasionType, ★ Occasion, ★ OccasionRequest | — |
| Announcements | ★ Announcement, plus a new `visibility` field (Internal / Public) | — |
| Core | ★ Notification, ★ AuditEvent (both nullable, for account-level events); ★ Role, ★ Membership | — |

- **Stays global on purpose:**
  - `User`
  - `SpotifyConnection`: a person's own Spotify account, used for playback
  - `SpotifyLimit`: the shared 429/Retry-After block, which must cover
    every church
  - `SignInEvent`: an account-level record
- **Not scoped yet, locked (§5):**
  - Members: Member, Household, MembershipStatus, RelationshipType,
    MemberField
  - Teams: TeamPart, TeamProfile, Assignment, BlackoutDate, SwapRequest

**Constraint changes:**

- Church-scoped list items (via a new abstract `ChurchChoiceItem`): `name`
  becomes unique per church instead of across the installation.
- `Song.spotify_id` becomes unique per church.
- WorshipService's unique constraints get `church` added.

## 2. Permissions (the 172 call sites stay as they are)

**Middleware.** `CurrentChurchMiddleware` replaces `ChurchProfileMiddleware`:

- It reads the working church from `session["church_id"]` and keeps it only
  if the user has an active Membership there (or is a superuser).
- With no session choice it falls back to the user's first membership.
- It sets `request.church` and `request.user.current_church`, and switches
  on the church's time zone.

**Permission lookup.** `ChurchRoleBackend` replaces `ModelBackend` in
`AUTHENTICATION_BACKENDS`:

- `get_all_permissions(user)` returns the permissions of the roles in the
  user's Membership in `user.current_church`, cached per church on the user
  object.
- With no current church, it returns no permissions.
- It ignores `user.groups` and permissions granted straight to a user, so
  nothing leaks between churches.
- Every `has_perm`, `PermissionRequiredMixin` and template `perms.*` check
  then works per church unchanged. `worship.finalize_lineup` stays a
  permission (decision 0008).

**Code without a request** (worker, notifications, "who may approve",
`administrators()`):

- It moves to a helper `users_with_perm(church, perm)` that queries
  memberships.
- The Administrator role still holds every permission, and "the last
  active administrator can't be removed" becomes a rule per church.

**Superusers** (Django admin accounts only) stay all-powerful and can
switch to any church, for support. Nobody approves new churches.
(Question 3.)

**Tests.** `make_user(roles=..., perms=...)` will create a Membership in a
test church and put the requested permissions on a test role in that
church. Existing tests keep their meaning without rewrites, and the suite
still runs without a network.

## 3. Scoping objects

- Each scoped model gets `objects.for_church(church)`. For child models it
  filters through the parent, e.g. `Lineup.objects.for_church(c)` is
  `service__church=c`.
- A `ChurchScopedMixin` filters `get_queryset()` for the generic views.
- A helper `get_in_church(Model, request, **lookup)` replaces
  `get_object_or_404` on scoped models. An object from another church gives
  404, not 403.
- **Forms:** every ModelChoiceField on a scoped model gets its queryset
  filtered (template, series, season, tags, occasion type, officiant). This
  is the easiest place to leak, so each one gets a test.
- **Creating records:** the church is always set on the server from
  `request.church` and never taken from the form.
- **Setting lists:** the generic list, add and edit views filter by church
  whenever the model has a `church` field.
- **Worker:** `run_worker` and `process_songs` handle runs and songs from
  every church, and every query goes through each row's church. Analysis
  loads that church's theme tags, trusted artists and worship check
  settings, and ranking loads that church's SuggestionSettings. It stays
  one worker with one advisory lock, and the `SpotifyLimit` block is shared
  by all churches.
- **New-church defaults:** `seed_church(church)` creates the default roles
  and permissions, theme tags, default template, settings rows and occasion
  types (Wedding, Baptism and Funeral, switched off). It reuses the values
  the existing seed migrations use. The post-migrate permission sync runs
  for every church.
- **Announcement notifications:** "Everyone" today notifies every active
  user. It will notify that church's active members only.

## 4. URLs and choosing the church

- **Staff pages keep their URLs** (`/worship/…`, `/church/…`, …) and act on
  the current church. That avoids rewriting hundreds of `{% url %}` tags in
  a week. Objects already use UUIDs in their URLs, and a lookup in the
  wrong church gives 404.
- **Church switcher:** a navbar menu of the person's memberships, which
  sends a POST to `/church/switch/<slug>/` (the membership is checked) and
  goes to the dashboard. It's shown only when the person has more than one
  membership.
- **New public and account pages:**
  - `/churches/`: the directory, with search by name or address
  - `/churches/<slug>/`: the Church Homepage
  - `/churches/<slug>/request/<type uuid>/`: Request this service (sign-in
    needed)
  - `/churches/register/`: "Sign in your church"
  - `/accounts/signup/`: "Create an account"
  - `/occasions/my-requests/`: a person's own requests at every church,
    with Withdraw
- **People with no membership** get a home page with Churches and My
  requests, and no staff navigation.
- **Known limit:** the current church lives in the session, so two tabs
  share it. A link to Church B's object opened while working in A gives 404
  until you switch.

## 5. The Members and Teams Modules are locked

- A Module gets `platform_ready` (False for Members and Teams).
- `is_enabled()` returns False for a church without
  `members_teams_unlocked`. This branches on a church setting, not on the
  church's identity (core rule), and only the migrated first church has it.
- The Modules settings page shows them as "Not available yet".
- Pages that touch these Modules for other churches are hidden as well:
  batch accounts, the Team card on a service, Swap Requests, and the member
  record of the Church Member role.
- **Reports:** song usage and attendance read WorshipService and Lineup, so
  they come scoped for free and stay on. The member reports (A6) aren't
  built yet and wait.
- Batch accounts (A4) now create a Membership in the first church instead
  of `user.groups`.

## 6. Registration, accounts and the public pages

- **Landing page:**
  - The main button reads "Sign in your church" and opens
    `/churches/register/`.
  - The CTA reads "Already part of a church's team? Sign in with your
    account." (wording open to the owner).
  - "Sign in" stays.
  - A **Churches** tab is added.
- **Register a church:** church name, plus username, name, email and
  password, or just the church name when signed in. In one transaction it
  creates the church and its slug, runs `seed_church`, adds an
  Administrator Membership, sets the session church and opens the setup
  wizard. It never asks for a denomination, and the guard test is extended
  to these forms.
- **Create an account:** username, name, email and password, with no
  church.
- **Adding people to a church:** the Users screen lists that church's
  memberships, and the admin gives each person roles.
  - *Add user* creates an account and its Membership.
  - **"Add an existing account"** (by exact username or email) only creates
    a Membership. It's needed to make someone who signed up a Pastor.
- **Profile (CMS):** the existing profile and settings pages gain About,
  Show in the directory and Show upcoming services.
- **Occasion Types** gain `offered_publicly`: "Shown on the homepage;
  anyone signed in can request it".
- **Church Homepage** shows:
  - the logo, name, address and contact details
  - About
  - offered occasion types, each with "Request this service"
  - Public announcements
  - optionally, the next upcoming services as date, time and kind only,
    without theme or lineup

  It never shows lineups, songs, chord sheets, lyrics, members or teams.
- **Request this service:**
  - Uses the existing `OccasionRequest` flow and overlap check for that
    church.
  - Anyone signed in may request an offered type (question 2).
  - The in-church request screen still needs `occasions.request_occasion`.
  - Approvers holding `occasions.approve_occasion` in that church are
    notified.
  - The requester is notified, with a notification tagged with the church.
  - The notifications list shows a person's notifications from every
    church, each with the church's name.

## 7. Migrating the existing data (nothing is lost)

1. **Schema:** add the new fields and Membership, add nullable `church`
   FKs, and drop the singleton rule.
2. **Data:**
   - Load or create the pk=1 church, give it a slug and set
     `members_teams_unlocked=True`.
   - Point every row of every scoped root model at it, along with the three
     settings singletons and the Church Spotify Account.
   - Roles move to it, and `title` takes the role's name.
   - Every existing user, active or not, gets a Membership there with
     exactly the roles in their `user.groups`.
   - `user.groups` is left as it is, ignored from now on, so the migration
     can be reversed. Suggest a cleanup migration later.
3. **Schema:** make the FKs required and swap in the per-church unique
   constraints.

- **Migration test:** using Django's `MigrationExecutor`:
  - Migrate back to the state before 9B.
  - Build a church, roles, users (one inactive), songs, services, lineups,
    occasions, announcements and settings rows.
  - Migrate forward.
  - Check every row's church, the per-user role sets and that the row
    counts haven't changed.

## 8. Slices (each one ends with the check green)

| Slice | Contents | Estimate |
|---|---|---|
| Docs | Decision 0014; Project-Overview, Glossary, Design-Decisions, workflow-spec and Development Plan (9B, 9A paused, 9 dropped unless time remains) | 0.5 day |
| a | Church fields, Membership, Role per church, backend, middleware, `seed_church`, test builders, migration and its test. Nothing changes on screen | 1.5 days |
| b | Scoping of the worship pipeline, song library, worker, Occasions, Announcements (visibility), Notifications, Audit and settings, plus **isolation tests**: a user in Church A gets 404 on every scoped detail, edit and action view for Church B's object, and Church B's rows are missing from every list and form | 2 days |
| c | Register a church, Create an account, add an existing account, church switcher, locked Modules, home page for people with no church | 1 day |
| d | Profile fields, the setup wizard for new churches, Occasion Types offered publicly | 0.5 day |
| e | Directory, Church Homepage, Request this service, My requests; anonymous, other-church and member permission tests | 1 day |
| End | Full check, Development Log, module notes, `00-Home.md`, the click-through test list | 0.5 day |

That comes to about 7 working days against roughly 6 before 1 Dec, so it's
tight. If time runs short, drop these in order:

1. upcoming services on the homepage
2. directory search
3. the cross-church My requests page (people would follow notification
   links instead)

Slices a and b are not optional.

## 9. Risks

- **Leaks through forms or non-view code** (notifications, the worker,
  reports). Mitigation: one shared `for_church` API,
  `users_with_perm(church, …)` and an isolation test for every view. There
  is also a grep audit for leftover `Model.objects.` calls on scoped
  models.
- **Permission backend mistakes would affect every page.** Slice a keeps
  all 1049 tests passing before any scoping starts.
- **Spotify Development Mode allows 5 users per app, across the whole
  platform.** That's acceptable for the presentation, but it's a real limit
  to record in decision 0014.
- **Repeat LRCLIB lookups**, because each church has its own song rows
  (question 1).
- **The deadline.**

## 10. Decision records and vault statements this contradicts

- **Project-Overview:** "One church per installation and five users or
  fewer."
- **Concept-Brief:** "one church, five users or fewer" (line 176), and
  "Keep them private to the project's few users".
- **Glossary:** "Church Profile: The single record describing this
  installation's church"; "_Avoid_: tenant, organization" (suggestion: keep
  avoiding "tenant").
- **0003 editable roles:** roles are installation-wide, granted through
  Groups, and Django's own permission checks apply. Needs an update
  section: roles per church, membership-based backend.
- **0007 search worker:** "for one church with five users or fewer". The
  design holds, but the reasoning text changes.
- **0009:** "one church, a handful of users". Only a reasoning note.
- **0011:** "at most one row" Church Spotify Account. It becomes one per
  church.
- **0013 / Occasions:** requests come from church members holding
  `request_occasion`. Public requests from any signed-in account are new.
- **Church-Setup.md:** "the single row (pk 1, enforced by a…)".
- **Development-Plan:** "Church Profile (exactly one per installation)" and
  "Suggestion settings (one row)".
- **Worship.md:** Suggestion Settings "one row" (l.121) and Church Spotify
  Account "at most one row" (l.465).
- **Design-Decisions l.560:** the "one church, five users" open point.
- **AGENTS.md:**
  - "Lyrics and chord sheets … keep them inside the installation" still
    holds, but they now also stay inside each church.
  - Its Phase 9A priority exception needs a line for 9B coming first.
    AGENTS.md ranks above everything else, so change it only with the
    owner's OK (question 4).
- **Announcements:** "readable by everyone signed in". It becomes the
  church's members, plus Public on the homepage.
- No conflict found with 0001, 0005, 0008 or the Spotify safeguards.

## 11. Questions for the owner (answered 2026-11-25)

1. **LRCLIB cache across churches.** Each church gets its own Song rows.
   Proposal: when Church B adds a track whose lyrics another church already
   fetched, copy those lyrics instead of asking LRCLIB again. That respects
   "every result cached" and lowers LRCLIB load. Lyrics would stay inside
   the installation and never be shown across churches, but analysis, tags
   and chord sheets stay separate. OK, or should each church look up its
   own?
2. **Public requests.** Any signed-in account may request an offered
   occasion type from the homepage. Proposal: make it a church setting,
   "Accept requests from people outside the church" (on by default). OK?
3. **Superusers.** May they switch into any church as full administrators,
   for support? Or should they get no church powers unless they hold a
   membership?
4. **Updating AGENTS.md.** May one line be added to its priority exception
   saying Phase 9B comes before the rest of 9A, and "inside the
   installation" be replaced with "inside the church's installation"?
   Nothing else in AGENTS.md changes.

**Answers (2026-11-25):** 1. Reuse lyrics another church already
fetched. 2. Yes, as a church setting, on by default. 3. Yes, superusers
may switch into any church. 4. Yes, both AGENTS.md lines.

Next: the docs, then slice a.
