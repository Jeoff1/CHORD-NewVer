# Development Log

Newest entries first. Template: `Templates/Development-Log-Entry`.

## 2026-11-25: Phase 9B, slice a: foundations for many churches

Nothing changes on screen yet; one installation can now hold many
churches ([[0014-church-platform]]; choices in [[Phase-9B-Plan]],
"Progress notes").

- **Church Profile** is no longer a single row: it has a `slug`, `about`,
  `show_in_directory`, `show_upcoming_services` and
  `members_teams_unlocked` (the migrated church only). The id sequences of
  the old pk=1 tables are reset by the migrations.
- **Membership** and **roles per church**: `Role.church` and `Role.title`
  (unique per church); `ChurchRoleBackend` gives the permissions of the
  roles in the Current Church only; `CurrentChurchMiddleware` replaces
  `ChurchProfileMiddleware`. Users and roles pages, the permission matrix,
  role changes (A2), batch accounts (A4) and the team list read
  memberships instead of `user.groups`.
- **`church` on every scoped root model**: services, templates, sermon
  series, seasons, songs, theme tags, trusted artists, occasion types,
  occasions, requests and announcements; nullable on notifications and
  audit events; one settings row per church for Suggestion Settings,
  Worship Check settings and the Church Spotify Account. Church lists use
  `ChurchChoiceItem` (names unique per church); Spotify track IDs are
  unique per church.
- **`seed_church`** with seeders from Accounts, Songs, Worship and
  Occasions; `make_church` and a church-aware `make_user` for tests.
- **Tests:** `apps/accounts/tests/test_church_platform.py` (permissions
  follow the Current Church, groups and direct permissions give nothing,
  superusers, `users_with_perm`, administrators per church, the middleware,
  `seed_church`, per-church names, accounts pages show one church);
  `apps/church/tests/test_platform_migration.py` (back to before 9B, data,
  forward: every row in the first church, counts kept, each user's roles
  kept). Updated tests: role titles instead of names, the Church Spotify
  Account per church, and "a permission given to the user directly"
  (it no longer keeps someone on the team).
- **Checks:** quick check passes (1071 tests); the full check runs in the
  pre-commit hook.

## 2026-11-25: Phase 9B approved; docs

The owner approved the Church Platform plan ([[Phase-9B-Plan]], moved into
the vault from the cloud session's branch) with the recommended answer to
each question: lyrics another church fetched are reused; requests from
outside a church are a church setting, on by default; superusers may
switch into any church; AGENTS.md says 9B comes before the rest of 9A.

- New decision [[0014-church-platform]]; update sections in
  [[0003-editable-roles]] and [[0011-church-spotify-account]].
- [[Development-Plan]]: Phase 9B row and section; 9A paused (A1 to A5 in
  `master`); the "five users" question closed.
- [[Design-Decisions]]: "Phase 9B" rules and tests.
- [[Glossary]]: Church Profile reworded; Church Platform, Membership,
  Current Church, Church Homepage and Directory added.
- [[Project-Overview]], [[Concept-Brief]] (a dated note on the scope line)
  and `workflow-spec.md` no longer say one church per installation.
  Module notes ([[Church-Setup]], [[Worship]], [[Announcements]],
  [[Occasions]]) change with the slices that change their code.
- `AGENTS.md`: 9B comes before the rest of 9A; lyrics stay inside the
  church's installation.
- **Checks:** docs only; no code changed.

## 2026-11-25: Checks run automatically before each commit; tblib

Tooling only; the app is unchanged.

- `scripts/git-hooks/pre-commit` runs `scripts/check.ps1` (the full check)
  before every commit and stops the commit on a failure. Commits that
  change only `docs/` or `*.md` files skip it. Each clone turns it on once
  with `git config core.hooksPath scripts/git-hooks` (README and
  [[Environment-Setup]] step 7). `.gitattributes` keeps the hook's line
  endings LF so it runs on every system.
- `tblib==3.2.2` added to `requirements.txt`. Without it, a test that
  fails inside a parallel worker stopped the whole run and showed no line
  number or other failures (tried with a throwaway failing test).
- **Checks:** the hook ran the full check on this commit (see below).

## 2026-11-25: Faster checks (about 11 minutes down to about 70 seconds)

Tooling only; the app is unchanged.

- Tests run in 4 parallel processes (`--parallel 4`), each with its own
  copy of the test database. On Windows each worker starts fresh, so the
  test setup (network blocked, keyword ML engine, Spotify unset) moved to
  `apps/core/test_environment.py`, which `ChordParallelTestSuite` runs in
  every worker. Without this, workers would have run with the network
  open.
- Tests hash passwords with MD5 (tests only; production hashers
  unchanged).
- Coverage collects from every worker (`parallel`, `concurrency` in
  `pyproject.toml`) and `scripts/check.ps1` combines it before the report.
- `scripts/check.ps1 -Quick` runs every check and test without coverage;
  `-Tests <labels>` narrows the tests while working; `-Workers N` sets the
  process count.
- **Test:** `apps/core/tests/test_test_environment.py` checks the network
  block, ML engine, Spotify settings and hasher; it runs inside a worker.
- **Checks:** before: 1046 tests in 634 s. After: `-Quick` passes in 66 s
  (1049 tests in 28.5 s); full check passes in 72 s (1049 tests in 32 s,
  97% coverage).
- **Seen once:** one test run before these changes stopped with PostgreSQL
  "out of memory"; the rerun passed. C: had 2.7 GB free, which can stop
  Windows from growing its page file. The worker count stays at 4 for this
  reason.

## 2026-11-25: "Sheet's key" label when a lineup song has no service key

- On the lineup song page, the toolbar labelled the key "Service key"
  even when the song had none and the sheet was shown in its own key. It
  now reads "Sheet's key" in that case (`LineupSongView.sheet_context`
  in `apps/worship/views/lineups.py`).
- **Test:** `ViewerTests.test_without_a_service_key_the_sheets_own_key`
  checks for "Sheet's key" and no "Service key".
- **Checks:** Ruff lint and format, Django checks and migrations pass;
  full test suite with coverage: 1046 tests, OK.

## 2026-11-25: The 5 lineup tests left from A7 part 3 pass again

Tests only; the app is unchanged. Each test now checks the redesigned
pages' wording instead of the wording from before A7 part 3.

- `test_lineup_songs`, `ViewerTests`: the toolbar shows the label
  ("Service key") and the key in separate elements, so the key tests
  look for each one. Without a service key, the test checks for the
  sheet's own key (G) in the toolbar and "In G." under it, because the
  sentence "shown in the sheet's key, G" is no longer used.
- `test_lineup_songs`, `test_a_team_member_pastes_and_only_they_and_planners_see_it_waiting`:
  **not a leak.** "Amazing " matched the "Amazing Grace" title in the
  page's song list, not the pending sheet. The check now looks for a
  lyric from the sheet ("sweet the"). A probe confirmed that the leader's
  page contains that lyric and the other team member's page doesn't, so
  the check would catch a real leak.
- `test_lineup_views`: the button now reads "Confirm {lineup label}", so
  both tests look for ">Confirm lineup<". (The team member's "no Confirm
  button" check was passing only because the old wording was gone.) The
  service page shows a song's key as "Song A · key of G" instead of "(G)".
- **Checks:** Ruff lint and format, Django checks and migrations pass;
  full test suite with coverage: 1046 tests, OK.

## 2026-11-25: Active switch on settings lists; Settings menu always open

- **Active switch:** on every church-edited list (Occasion types, Membership
  Statuses, Team parts, Theme tags and the rest), the Active column is a
  switch for people with the list's change permission. Ticking it saves at
  once with HTMX (a Save button without JavaScript) through the new
  `<url_prefix>_switch` URL (`SettingSwitchView` in
  `apps/core/setting_lists.py`, partial `core/includes/active_switch.html`).
  The post carries the state wanted, so a second click or a page left
  open never flips an item the wrong way; a real change is audited
  ("Active: Yes → No"). People who may only view still see Yes or No.
  Gated by the Module like the list's other pages.
- **Settings menu:** the categories are no longer dropdowns; every
  category and its pages are always shown. The menu scrolls on its own
  when it is taller than the space it has (beside the page on a wide
  screen it stays in view, up to the window's height; stacked on a narrow
  screen it is kept to 45% of the height), and opens scrolled to the
  current page. `MenuCategory.is_open` was removed.
- **Tests:** new `apps/core/tests/test_setting_switch.py` (7: switch shown
  only to people who may change, HTMX switch-off with audit, switch-on
  without HTMX, asking for the current state changes nothing, POST only,
  switched-off Module). `test_settings_hub` now checks there are no
  dropdowns.
- **Checks:** Ruff lint and format pass. `apps.core`, `apps.occasions`,
  `apps.members`, `apps.teams` and `apps.songs`: 541 tests, one failure,
  the known `test_pages` "Welcome, Ana." wording (see the entry below).
  `test_settings_hub` and `test_setting_switch` re-run after the menu
  change: 20 tests, OK. Full `check.ps1`: lint, format, Django checks
  and migrations pass; tests 1046 run, **5 failures**, all in
  `apps.worship` (`test_lineup_views`: `test_the_leader_confirms`,
  `test_a_team_member_sees_a_confirmed_lineup_without_the_planning`;
  `test_lineup_songs`: both `ViewerTests` key tests and
  `test_a_team_member_pastes_and_only_they_and_planners_see_it_waiting`).
  The same 5 fail on the committed `master` without these changes, so
  they come from the A7 part 3 lineup redesign, not from this work.
  Still to fix; the pending-sheet one may be a real visibility leak.
- **Fixed test:** `test_pages` now expects the dashboard's time-of-day
  greeting ("Good morning|afternoon|evening, Ana") instead of "Welcome,
  Ana."; 3 tests, OK.

## 2026-11-25: Phase 9A, A7: the landing page

On branch `ui-design-system`, fast-forward merged into `master` for the demo.

- **Landing page** (`church/landing.html`, `LandingView`): a visitor who
  isn't signed in sees it at `/` instead of being sent to sign in;
  signed-in people still get the dashboard (`DashboardView.dispatch`).
  It follows the owner's reference design: green hero with an example
  lineup, How it works (four steps), Features, Rehearsal (a chord sheet
  beside the player), a gold call to action and the footer.
- **Configure behavior, not identity:** the copy uses the church's Labels
  (worship service, sermon, lineup, pastor), says no day of the week, and
  offers Team roster, Calendar and occasions, and Announcements only when
  those Modules are switched on. The examples are public-domain hymns.
- **Styles:** `.chord-landing*` in `static/css/chord.css`; light and dark
  mode follow the device (nobody is signed in). The example lineup card
  stays light in both modes. New icons: music-note, document, people,
  calendar, megaphone, check-circle.
- **Tests:** new `apps/church/tests/test_landing.py` (5: a visitor sees the
  page and the sign-in link, a signed-in person sees the dashboard, Labels,
  switched-off and switched-on Modules). `apps/core/tests/test_pages.py`:
  the visitor test now expects the landing page at `/` and the sign-in
  redirect on other pages.
- **Checks:** Ruff lint and format, Django checks and missing migrations
  pass; 1039 tests, coverage 97%. Six tests fail, and failed before this
  change too (A7 part 3's page wording): `test_pages` "Welcome, Ana.",
  `test_lineup_songs` (pending sheet; two viewer tests on "Service key"
  and "the sheet's key") and `test_lineup_views` (">Confirm<", "(G)").

## 2026-11-25: Phase 9A, A7 part 2: the owner's design system and the player card

On branch `ui-design-system` (from `master`; not merged, at the owner's
request, since Progress Check 2 is demoed from `master`).

- **Theme** (`static/css/chord.css`, after Bootstrap in `base.html`): the
  owner's light and dark tokens as Bootstrap variables; `--bs-body-bg` is
  the surface and `body` the page colour; buttons, menus, tabs, pills,
  forms, cards and status text restyled. Dark mode follows the device
  (`data-bs-theme`, set in `<head>`), with no toggle.
- **Fonts:** Raleway (variable, 600 to 800) and Fira Sans Condensed (400
  to 700), Latin and Latin Extended woff2 from Google Fonts, self-hosted in
  `static/vendor/fonts/` with their OFL licences; `font-display: swap`.
- **Icons:** `templates/includes/icons/` (search, gear, eye, eye-off,
  person, play, pause, chevron-left, back-10, forward-10), solid,
  `currentColor`, `aria-hidden`. Used in the navbar (gear) and the player.
- **base.html:** the theme stylesheet and dark-mode script; no
  `bg-body-tertiary`; the profile letter (`.chord-avatar`) beside the name.
- **Back links:** `templates/includes/back_link.html`; the 15 "←" links
  now use it (the calendar's "Previous" month button is not a back link).
- **Chord letters** use `--chord-chord-letter` (`songs/includes/chord_sheet.html`).
- **Player card** (`songs/includes/player.html`, `songs/static/songs/player.js`;
  `playback_context` adds the Song's title, artist and length): three
  states (full playback, embedded player, no playback), green in both
  modes. The SDK state gives the cover (browser only), the progress (about
  once a second while playing, not while hidden) and seeking. Every Phase 7
  safeguard kept. Only the lineup song page uses the player.
- **No page links an existing song to a Spotify track**, so the
  no-playback card shows no fix link.
- **Contrast:** every text pair is at least 4.5:1 ([[Design-System]]). The
  light-mode strong border `#9FA7A2` is 2.46:1 on white, under 3:1 for
  input outlines: kept as given, for the owner to decide.
- **Tests:** new `apps/songs/tests/test_design_system.py` (7: the three
  card states, the player's safeguards, the theme and fonts, the profile
  letter, the back link); `test_spotify_playlists.py`: a song without a
  track now gets the card.
- **Notes:** [[Design-System]] (new), [[Design-Decisions]] (A7: the owner's
  design system), [[Code-Conventions]], [[Worship]] (playback),
  [[Development-Plan]], [[00-Home]].
- **Verified:** `scripts/check.ps1` passed. Ruff lint and format were
  clean, `manage.py check` was clean, and no migrations were missing. 968
  tests passed, with 97% coverage.

## 2026-11-24: Phase 9A, A5 rebuilt: Occasions as their own Module

On branch `adviser-comments`. The owner decided that weddings, baptisms
and funerals are not worship services: they need their own form and part,
with no lineup or team, and the pastor adds them directly as well as
approving requests. New decision [[0013-occasions-module]] replaces
[[0012-occasion-services]] (marked superseded); `AGENTS.md` scope updated.
The previous entry's design was built and replaced the same day; its
commit was never pushed or merged.

- **Worship back to worship services:** the occasion fields, the occasion
  templates and the worship-side requests were removed (their migrations
  were unapplied locally and replaced by `worship/0012_template_length`).
  Kept: `ServiceTemplate.length_minutes` (90 by default) and
  `WorshipService.ends_at`. New `apps/worship/bookings.py`: other Modules
  register calendar sources, so the calendar shows them without Worship
  importing them.
- **Occasions Module** (`apps/occasions`, requires Worship; [[Occasions]]):
  - `OccasionType` (church-edited, with a usual length; "Wedding",
    "Baptism" and "Funeral" seeded switched off), `Occasion` (type, time,
    length, For, officiant, venue, notes, cancelled) and `OccasionRequest`
    (`request_occasion`, `approve_occasion`).
  - Rules in `rules.py`: adding, moving, requesting and approving refuse a
    time that overlaps a worship service or another occasion that isn't
    cancelled (under the `BOOKINGS` lock); the requester is notified.
  - Pages: Occasions (Upcoming/Past, search), Add an occasion, each
    occasion with Edit, Requests with Approve and Decline (Pending count on
    the tab), My requests, and the Occasion types settings. The calendar
    shows occasions to holders of `occasions.view_occasion` and "Booked"
    to everyone else.
  - Defaults: Pastoral Staff add, edit, approve and keep the types; Office
    Staff and Worship Leader see occasions; Church Member, Pastoral Staff
    and Worship Leader request.
  - `Module.view_permission` may be a tuple: Occasions opens for people
    who see occasions or may request one.
- **Kept from the first build:** Notifications in the core
  `apps/notifications` app.
- **Tests:** new `apps/occasions/tests/test_occasions.py` (42); booked time
  in `apps/worship/tests/test_schedule.py`; the module lists in
  `apps/church/tests/test_views.py` and
  `apps/accounts/tests/test_church_member.py` now include Occasions.
- **Notes:** [[0013-occasions-module]], [[0012-occasion-services]],
  [[Occasions]] (new), [[Worship]], [[Services]], [[Design-Decisions]]
  (A5 rewritten), [[Glossary]] (Occasion, Occasion Type, Occasion
  Request), [[workflow-spec]], [[Concept-Brief]], [[Project-Overview]],
  [[0005-worship-planning-scope]], [[Code-Conventions]],
  [[Development-Plan]], [[00-Home]], `AGENTS.md`.
- **Verified:** `scripts/check.ps1` passed. Ruff lint and format were
  clean, `manage.py check` was clean, and no migrations were missing. 961
  tests passed, with 97% coverage (`occasions/rules.py` 99%,
  `occasions/views.py` 94%). An earlier run stopped with two PostgreSQL
  "out of memory" errors while C: had about 1 GB free; the rerun passed
  unchanged.

## 2026-11-24: Phase 9A, A5: occasions; Notifications made core

On branch `adviser-comments`. A5 of Phase 9A is done, after the owner
settled the three open points: Notifications move out of Teams; "Wedding"
and "Funeral" are seeded as switched-off examples; signing in is enough to
request (no Member record).

- **Notifications are core** (`apps/notifications`): the model, `notify`
  and the read helpers, the page `/notifications/` and the unread count,
  for everyone signed in, whichever Modules are on. The table was renamed,
  not copied (migrations `teams/0004_move_notification_out` and
  `notifications/0001_initial`, which also renames the index and moves the
  content type); undoing and redoing it was tried on the local database.
  Teams keeps `notifying.py` and still sends its notes only while it is on.
- **Occasions** ([[0012-occasion-services]]; migrations
  `worship/0012_occasions`, `0013_seed_occasion_templates`):
  - `ServiceTemplate.length_minutes` (90 by default; a blank form keeps it)
    and `is_occasion`; `WorshipService.occasion_for`, `officiant`, `venue`
    and `ends_at`; `OccasionRequest` with `worship.request_occasion` and
    `worship.approve_occasion` (Church Member, Pastoral Staff and Worship
    Leader request; Pastoral Staff approve).
  - Rules in `apps/worship/occasions.py`: requests and approvals that
    overlap a booked time of a service that isn't cancelled are refused;
    approvals take the `BOOKINGS` transaction lock
    (`apps/core/locks.py`, `wait_for_transaction_lock`); declining needs a
    reason; only the requester withdraws, while Pending; the requester is
    notified either way.
  - Who sees an occasion: holders of `change_worshipservice`,
    `view_lineup`, `approve_occasion` or `record_attendance`. Others see
    "Booked" on the calendar, and nothing in the schedule list or search;
    the occasion's pages are a 404 for them (`ServiceMixin`).
  - Pages: Request an occasion, My requests (with Withdraw), Occasion
    requests and each request's Approve and Decline; an "Occasions" tab in
    Worship with the Pending count for approvers.
- **Built differently from the plan, for the owner to confirm:** "who it
  is for" is a text field, not names linked to Members (Worship doesn't
  depend on Members, and nothing in A5 reads the link).
- **Found by the first full run, and fixed:** older tests assumed one
  seeded Service Template (`objects.get()`; now `active().get()`); the
  Church Member test expected one default permission; the template form
  refused a missing length (it now keeps 90 minutes, with a test).
- **Tests:** new `apps/notifications/tests/test_notifications.py` (10; the
  page tests moved here from Teams) and
  `apps/worship/tests/test_occasions.py` (37).
- **Notes:** [[Design-Decisions]] (A5: the owner's answers, how it was
  built), [[0012-occasion-services]], [[Worship]], [[Accounts]]
  ("Notifications"), [[Teams]], [[Glossary]], [[workflow-spec]],
  [[Code-Conventions]], [[Development-Plan]] (A5 ticked), [[00-Home]].
- **Verified:** `scripts/check.ps1` passed on the second run. Ruff lint and
  format were clean, `manage.py check` was clean, and no migrations were
  missing. 954 tests passed, with 97% coverage
  (`worship/views/occasions.py` 94%). The first run had failed (2
  failures, 25 errors), as above.

## 2026-11-24: Phase 9A, A3 and A4: user history; batch accounts

On branch `adviser-comments`. A3 and A4 of Phase 9A are done, built
together with one full check run at the end.

- **A3, user history:**
  - `audit.SignInEvent` (migration `audit/0002_signinevent`): sign-in,
    sign-out and failed sign-in, recorded from Django's signals
    (`apps/audit/signins.py`, connected in `AuditConfig.ready()`). A
    failed one keeps the username tried and the account it names, never
    the password. Kept apart from `AuditEvent`, so the change log isn't
    flooded and tests that read "the one audit event" still hold.
  - History page `/accounts/users/<id>/history/` (`audit.view_auditevent`),
    linked from the user's edit page: the latest 50 sign-ins and the latest
    50 changes the person made.
- **A4, batch accounts:**
  - `/members/accounts/` (`apps/members/accounts.py`, `MemberAccountsView`),
    from a "Create accounts" button on the Members list; needs
    `members.view_member` and `accounts.add_user` (Administrator only by
    default). Current members without an account, filtered by name and
    status; the chosen role, Church Member by default.
  - Each account is linked to its member, with username "first.last"
    (unique), the member's email and a 12-character Temporary Password.
    Each member's row is locked while its account is made; members who
    already have one or are archived are skipped with the reason.
  - The result page shows the passwords once, with the CSV built into the
    page as a download (never stored on the server), is never cached, and
    escapes formula-like cells. Passwords never reach the Audit Trail.
  - `User.must_change_password` (migration
    `accounts/0006_user_must_change_password`) and
    `PasswordChangeRequiredMiddleware`: until the person sets their own
    password (Change password, or a reset by email), every page except
    Change password and Sign out sends them to Change password; static
    files and the logo still load.
- **Found in review before the full run, and fixed:** the middleware would
  have blocked the church logo on the Change password page; a password
  reset by email didn't clear the flag.
- **Open, for the owner:** whether the pastor should create batch accounts
  too ([[Development-Plan]] decisions: `accounts.add_user` would let them
  give any role, Administrator included). The Members CSV export (older)
  doesn't escape formula-like cells; noted in [[Members]] for Phase 10.
- **Tests:** new `apps/audit/tests/test_sign_ins.py` (8) and
  `apps/members/tests/test_member_accounts.py` (18).
- **Notes:** [[Design-Decisions]] (A3, A4: how they were built),
  [[Accounts]], [[Members]], [[Code-Conventions]] (sign-ins, CSV cells),
  [[Glossary]], [[Development-Plan]], [[00-Home]].
- **Verified:** `scripts/check.ps1` passed. Ruff lint and format were
  clean, `manage.py check` was clean, and no migrations were missing. 913
  tests passed (26 new), with 97% coverage.

## 2026-11-24: Phase 9A, A2: a role change keeps history

On branch `adviser-comments`. A2 of Phase 9A is done.

- **Role history** on the user's edit page (`accounts/user_form.html`,
  `views.role_history`): every change to Roles or Active from the Audit
  Trail, newest first, with who made it.
- **What a change takes away** (`apps/accounts/role_changes.py`): before
  saving a change of roles or active status, the page works out the
  permissions the user would lose (from the database, not the form's
  instance) and asks each registered Module. Teams
  (`apps/teams/leaving.py`, registered in `TeamsConfig.ready()`) answers
  with the person's Pending or Accepted assignments on coming services
  that aren't cancelled, when they leave the team. The page lists them and
  saves nothing until the editor chooses **End** (each removed with
  `rostering.remove`, open swap requests withdrawn) or **Keep**; the choice
  is recorded on the user ("Ended (2)" or "Kept (2)"). Past assignments
  are never touched; nothing is listed while Teams is off.
- `templates/form_page.html` gained the `form_extra` and `after_form`
  blocks.
- **Left for now** (owner, 2026-11-24): taking the team permission from a
  whole role in the matrix, or deleting a role, doesn't warn; recorded in
  the [[Development-Plan]]'s decisions.
- **Tests:** new `apps/accounts/tests/test_role_history.py` (a Worship
  Leader made a Church Member keeps their confirmed and edited lineups,
  chord sheets, approvals and past assignments; the history lists both
  roles and deactivation; the permission) and
  `apps/teams/tests/test_leaving_team.py` (the list shows only coming,
  not cancelled, Pending or Accepted assignments and saves nothing; End
  frees the places and withdraws open swaps, with the audit; Keep; asking
  again without a choice; past assignments unchanged; deactivation;
  staying on through another role or a direct permission; no assignments;
  Teams off).
- **Notes:** [[Design-Decisions]] (A2, how it was built), [[Accounts]],
  [[Teams]], [[Code-Conventions]] (form page blocks; role changes between
  Modules), [[Development-Plan]], [[00-Home]].
- **Verified:** `scripts/check.ps1` passed. Ruff lint and format were
  clean, `manage.py check` was clean, and no migrations were missing. 887
  tests passed (15 new), with 97% coverage (`role_changes.py` 92%,
  `accounts/views.py` 98%).

## 2026-11-24: Phase 9A, A1: the Church Member role

On branch `adviser-comments`. A1 of Phase 9A is done.

- **Church Member** default role (migration
  `accounts/0005_church_member_role`; not made if the church already has a
  role of that name) with one default permission,
  `worship.view_worshipservice` (`DEFAULT_ROLE_PERMISSIONS`). It sees the
  schedule, the calendar and theme titles, announcements to everyone and
  its own member record; the service page already shows lineups, the team,
  suggestions and theme notes only to holders of their permissions.
- **Only openable Modules are listed:** `Module.view_permission` and
  `Module.can_open(user)` (`apps/church/modules.py`); the `church` context
  processor's `module_entries` now holds only the Modules the user can
  open (`enabled_modules` still names every switched-on one). A user who
  can open none sees a message. Affects every role: Office Staff no longer
  see Teams, Team Members no longer see Members.
- **"Spotify account" menu link** only for holders of `worship.view_lineup`
  (the owner's choice); the page still works for anyone signed in.
- **Environment:** the user's virtual environment was in `venv`, but
  `check.ps1` and [[Environment-Setup]] use `.venv`; at the user's request
  the folder was renamed to `.venv` (the dev server, worker and VS Code's
  Black formatter were stopped for it). Running `check.ps1` from a
  PowerShell 5.1 session with `2>&1` stops it at the tests (Django's
  stderr becomes an error); run it in a terminal, or with
  `powershell -File` and the output redirected outside PowerShell.
- **Tests:** new `apps/accounts/tests/test_church_member.py` (14 tests:
  the role's permissions, editable like any role, each allowed page, the
  refused lineup, lineup song, suggestions, song, chord sheet, reports,
  roster and member pages, the Modules each role sees, the Spotify link by
  role, the no-module message); `test_roles.py` expects the sixth role.
- **Notes:** [[Design-Decisions]] (A1, and the Phase 7 Spotify line),
  [[Accounts]], [[Church-Setup]], [[Code-Conventions]],
  [[Development-Plan]] (A1 ticked), [[00-Home]].
- **Verified:** `scripts/check.ps1` passed from `.venv`. Ruff lint and
  format were clean, `manage.py check` was clean, and no migrations were
  missing. 872 tests passed (14 new), with 97% coverage.

## 2026-11-24: Adviser comments recorded; Phase 9A planned

On branch `adviser-comments` (from `master`, not pushed). Documentation
only; no code changed.

- **Adviser comments (24 Nov)** and the owner's answers recorded in
  [[Design-Decisions]] ("Adviser comments, 24 Nov", A1 to A7): a Church
  Member role; a role change keeps history; user history; batch accounts
  from the Members list; occasions such as weddings and funerals, requested
  by church members, with booked times on the calendar; printable member
  reports with age groups; a UI pass, wireframes first.
- **Scope changed** with the owner's approval: new decision
  [[0012-occasion-services]] amends [[0005-worship-planning-scope]] (update
  note added); `AGENTS.md` scope lists occasions and the Phase 9A items,
  keeps fees and per-person attendance out, and records the exception that
  Phase 9A comes before Phase 9. Also updated: the [[Concept-Brief]], the
  [[workflow-spec]] (Church member role, OCCASIONS, ACCOUNTS, HISTORY AND
  REPORTS), [[Project-Overview]], [[Services]] (note), the [[Glossary]]
  (Church Member, Age Group, Temporary Password, Occasion, Occasion
  Request, Booked Time; Audit Trail).
- **[[Development-Plan]]:** Phase 9A added before Phase 9 (status Next),
  with its tasks and "done when"; Phase 9 only if time remains; new
  decisions to make (who attended a service, on hold; notifications
  without Teams; the five-user wording; Progress Check 2 and the Progress
  Report).
- **[[00-Home]]** "Current status" updated.
- Checks: documentation only, so `scripts/check.ps1` was not run; no code
  changed since it last passed (858 tests, 97% coverage).

## 2026-11-23: Phase 8 merged into master

- **Merged:** `phase-8-teams` fast-forwarded into `master`, at the user's
  request; the user hasn't clicked through Phase 8 yet.
- **[[00-Home]]** "Current status" updated: Phase 8 is on `master`;
  Phase 9 next.
- Checks: documentation only, no code changed since `scripts/check.ps1`
  last passed (858 tests, 97% coverage), so it was not run again.

## 2026-11-23: Phase 8 part B: Swap Requests, Notifications, Announcements; the team is a permission

On branch `phase-8-teams`. Phase 8 is done.

- **Recorded:** the project owner's answers to the part A questions in
  [[Design-Decisions]] (Phase 8: "Approved after part A", with the team
  permission change, and "Swap Requests"; notifications on cancelled or
  past services and the unread count added), the [[workflow-spec]] (Teams
  and Announcements sections), the [[Glossary]] (Team; Team Profile, Swap
  Request and Notification updated) and the [[Development-Plan]] (part B
  ticked, "done when" updated, Phase 8 Done).
- **Part A fixes:**
  - only holders of `teams.view_assignment` have a Team Profile or
    Blackout Dates: `TeamMemberMixin` gates My team parts and the
    Blackout pages; `candidates()`, the Roster and editing someone's parts
    use `team_people()`; `assign`, `set_parts` and `add_blackout` refuse
    anyone else. People off the team who open My schedule are sent to
    their Notifications;
  - a test of the playlist fix on the private path (no Church Spotify
    Account): a 403 on another owner's playlist makes a new private one on
    the confirmer's account and stores neither ID.
- **Swap Requests** (`SwapRequest`, `rostering.request_swap`,
  `withdraw_swap`, `swaps_open_to`, `take_swap`): asked for by someone
  Pending or Accepted on a future open service, withdrawn while open,
  taken by the first eligible person as Accepted under a row lock; the
  original assignment ends; the audit trail records both people. Declining
  or removing an assignment withdraws its open request. The blackout
  refusal links to asking for the swap.
- **Notifications** (`Notification`, `notifying.py`): confirmation and
  every edit of a confirmed lineup reach the service's Pending and
  Accepted people, never the person who did it; being assigned reaches the
  person. Nothing for cancelled or past services or drafts. Worship sends
  a new signal, `apps.worship.signals.lineup_changed`, so it doesn't
  import Teams. Unread count in the navigation; open one or mark all read.
- **Announcements** (new app `apps/announcements`): to everyone signed in
  or to one service's team (only while Teams is on), posted with
  `announcements.add_announcement` (Pastoral Staff and Worship Leader by
  default), archived by the author.
- **Tests:** new `apps/teams/tests/test_swaps.py` (including two people
  taking one swap at once, on two database connections),
  `test_notifications.py` and `apps/announcements/tests/test_announcements.py`;
  team-permission tests in `test_rostering.py` and `test_views.py`; the
  private-path playlist test in `test_church_spotify.py`.
- **Notes:** [[Teams]] (rewritten), [[Announcements]] (new),
  [[Code-Conventions]] (signals between Modules, row locks, lock tests),
  [[00-Home]].
- **Verified:** `scripts/check.ps1` passed. Ruff lint and format were
  clean, `manage.py check` was clean, and no migrations were missing. 858
  tests passed (50 new), with 97% coverage (`teams/rostering.py` 99%,
  `teams/notifying.py` 95%, `teams/views.py` 98%, `announcements/views.py`
  93%). Not yet clicked through by the user.

## 2026-11-23: Phase 8 part A: Team Parts, Team Profiles, Assignments, Blackout Dates; playlist 403 fix

On branch `phase-8-teams`. Part A of Phase 8 is built; part B (swaps,
announcements, notifications) is next.

- **Recorded first:** the project owner's Phase 8 decisions in
  [[Design-Decisions]] (Phase 8: Teams decided before building; Notifying
  the team, widened to confirmations and every edit of a confirmed lineup
  and to newly assigned people; Updating a stored Lineup Playlist), the
  [[workflow-spec]] (new TEAMS and ANNOUNCEMENTS sections, the playlist
  rule, tables), the [[Glossary]] (Teams terms) and the
  [[Development-Plan]] (Phase 8 split into parts A and B; "done when"
  covers the new notifications). No vocal range.
- **Teams app** (`apps/teams`, registered in settings, URLs `/teams/`; the
  Module's page is My schedule): `TeamPart` (church-edited, seeded Vocals,
  Acoustic guitar, Electric guitar, Bass, Keys, Drums), `TeamProfile`
  (parts only, on the user account), `Assignment` (reply Pending,
  Accepted or Declined) and `BlackoutDate` (whole days in the church's
  time zone). Rules in `rostering.py`; pages: My schedule, My team parts,
  blackout dates, Assign, Roster, Team parts; a Team card on the service
  page. Default role permissions added. See [[Teams]].
- **Playlist fix** (`apps/worship/playlists.py`, `apps/songs/spotify.py`):
  a stored Lineup Playlist is made again only on a 404, or on a 403 when
  the connected account doesn't own it, checked by asking Spotify for
  both IDs (`playlist_owner_id`, `current_user_id`) and storing neither.
  Any other 403 is a refusal; a 429 on a lookup fails fast.
- **Tests:** `apps/teams/tests/test_rostering.py` and `test_views.py` (55
  tests); 4 new in `apps/worship/tests/test_church_spotify.py` (403 from
  another owner, 403 on the account's own playlist, 404 on the lookup, 429
  on a lookup). New builders `make_team_part`, `make_team_profile`,
  `make_assignment` ([[Code-Conventions]]).
- **Notes:** [[Teams]] (new), [[Worship]] (playlist rule),
  [[Code-Conventions]], [[00-Home]].
- **Verified:** `scripts/check.ps1` passed. Ruff lint and format were
  clean, `manage.py check` was clean, and no migrations were missing. 808
  tests passed (59 new), with 97% coverage (`rostering.py` 99%,
  `teams/views.py` 99%, `playlists.py` 93%). Not yet clicked through by
  the user.

## 2026-11-22: part B passed the real Spotify test; merged into master

- **Tested by the user** with a real Spotify account: connecting, playback,
  playlists on confirmation and Save to Spotify, and the Church Spotify
  Account. The faked rate limit (a 2-minute block) was skipped; the
  automated tests cover it.
- **Merged:** `phase-7-chords` fast-forwarded into `master`.
- **[[00-Home]]** "Current status" updated: Phase 7 fully done and on
  `master`; Phases 8 and 9 next.
- Checks: documentation only, no code changed since `scripts/check.ps1`
  last passed (749 tests, 97% coverage), so it was not run again.

## 2026-11-22: part B review: playlist ID, Church Spotify Account, approved choices

On branch `phase-7-chords`. The user reviewed part B and approved it, with
the changes below.

- **Recorded:**
  - **Playlist ID** (changes a hard rule): AGENTS.md now allows the ID of a
    playlist CHORD itself created, only to find and update it, never as
    model input or a training feature; the lineup may also store the
    owning account and the track IDs saved. Decision
    [[0010-store-own-playlist-id]], [[Design-Decisions]] (Phase 7) and the
    [[workflow-spec]].
  - **Church Spotify Account**: decision [[0011-church-spotify-account]],
    Design-Decisions (Phase 7), the spec, the [[Glossary]],
    [[Environment-Setup]] (a User Management slot, no Premium),
    [[Church-Setup]] and [[Worship]].
  - The browser player's token and the smaller choices, under "Approved
    after part B" in Design-Decisions. The open question in [[Worship]] is
    removed.
- **Built:**
  - `ChurchSpotifyAccount` (one row; tokens encrypted through a shared
    abstract `SpotifyTokens` with `SpotifyConnection`), connected and
    disconnected by holders of `church.change_churchprofile` on a new
    **Spotify** tab in church settings (shown while Worship is on), through
    the same callback, with only `playlist-modify-public` and
    `playlist-modify-private`. The audit trail records only connected or
    not, on the Church Profile.
  - Lineup Playlists go to the church account as public playlists when it
    is connected, whoever confirms or saves; everyone who sees the confirmed
    lineup gets "Open the playlist". Without it, unchanged: private, on the
    saver's account. New `Lineup.spotify_playlist_on_church_account`.
  - Playlist names are now "<service name> – <Mon D>". A stored playlist
    Spotify no longer has (403 or 404) is made again. Once a church account
    is connected, a lineup with a personal playlist is offered Save to
    Spotify again. `SpotifyError` carries Spotify's status.
- **Tests:** `apps/worship/tests/test_church_spotify.py` (22 tests with the
  one below): public playlist on the church account and the team's link;
  saving again and reopening update the same playlist; two services make
  two playlists and editing one leaves the other; a gone playlist is made
  again; 429, refusal and revoked account leave the lineup confirmed with
  Save to Spotify; without it, private on the confirmer's account; only the
  church-settings permission manages it; scopes, encryption and audit; the
  settings tab; never used for playback. In `test_spotify_connection.py`,
  the token page never hands out another person's token (GET refusal and
  no-store were already covered).
- **Verified:** `scripts/check.ps1` passed. Ruff lint and format were
  clean, `manage.py check` was clean, and no migrations were missing. 749
  tests passed (22 new), with 97% coverage (`connections.py` 93%,
  `playlists.py` 95%). Part B has passed the automated tests but not yet a
  test with a real Spotify account.

## 2026-11-22: Phase 7 part B: Spotify Connection, playback, Lineup Playlist, F10

On branch `phase-7-chords`. Phase 7 is done.

- **Spotify Connection** (`apps/songs/connections.py`, model
  `SpotifyConnection`): each user connects their own account with the
  Authorization Code flow from "Spotify account" in their menu. The state
  is checked once against the session. Access and refresh tokens are
  stored encrypted with Fernet (`SPOTIFY_TOKEN_KEY`), refreshed when under
  a minute is left or once after a 401, and removed when Spotify revokes
  them or the key can't read them. The audit trail records only
  connected/not connected.
- **`SpotifyClient`** (`apps/songs/spotify.py`): fails fast on a 429 by
  default (one request, no wait, block recorded); only the search worker
  passes `may_wait=True`. New user calls under the same safeguards:
  authorize URL, code exchange, refresh, `POST /me/playlists`,
  `PUT /playlists/{id}/items` (Spotify's February 2026 endpoints).
  `UserTokens` keeps tokens out of its `repr`.
- **Playback** on the lineup song page (`songs/includes/player.html`,
  `static/songs/player.js`): the Web Playback SDK for a connected account,
  with the person's own access token from a POST-only, never-cached
  endpoint. No Premium, an unsupported browser, a refused token, a 429 or
  no "ready" in 15 s fall back to Spotify's embedded player with a short
  message, never retrying. Without a connection the embedded player shows
  at once; "Open in Spotify" always.
- **Lineup Playlist** (`apps/worship/playlists.py`; four new `Lineup`
  fields): confirming saves a private playlist on the confirming person's
  account. No connection, a block or a 429 leave the lineup confirmed and
  show "Save to Spotify". The same person saving again updates their
  playlist; a playlist made before a 429 is kept for the next try.
- **Dependencies:** `cryptography` 50.0.2 (with `cffi`, `pycparser`) in
  `requirements.txt`; `SPOTIFY_TOKEN_KEY` and `SPOTIFY_REDIRECT_URI` in
  `.env.example` and settings. The test runner clears both.
- **Tests:** `test_spotify_connection.py`, `test_spotify_playlists.py`,
  and fail-fast tests in `test_spotify_limits.py`. The worker's wait tests
  now use a worker client. The SDK fallback itself runs only in a browser;
  a test checks `player.js` keeps its fallbacks.
- **Notes:** [[Worship]] (part B, permissions, settings, choices to
  confirm), [[Glossary]] (Spotify Connection, Lineup Playlist),
  [[Code-Conventions]], [[Environment-Setup]], [[Development-Plan]]
  (tasks ticked, Phase 7 Done), [[00-Home]].
- **Verified:** `scripts/check.ps1` passed. Ruff lint and format were
  clean, `manage.py check` was clean, and no migrations were missing. 727
  tests passed (49 new), with 97% coverage (`connections.py` 96%,
  `playlists.py` 96%, `spotify.py` 94%). Not yet tried against real
  Spotify.

## 2026-11-20: hand-over: decisions checked, status for the next session, check.ps1 --noinput

On branch `phase-7-chords`.

- **Decisions checked:** every decision the user approved in this session
  was checked against [[Design-Decisions]], the [[workflow-spec]] and the
  [[Glossary]]. Missing ones were recorded:
  - the Phase 6 click-through fixes: the feel reason follows the slot;
    full names in marks and notes; no nested brackets; move arrows only
    where allowed. Added to Design-Decisions (Phase 6) and spec step 10;
  - the stray `]` removal and the viewer's style and note for kept marks,
    added to the spec;
  - Chart Mark and Rhythm Line, added to the Glossary.
- **[[00-Home]] "Current status"** is rewritten for the next session:
  - the branch and commit;
  - what Phase 7 part A includes, and that it passed the user's
    click-through;
  - part B next (the Spotify connection, playback, the playlist on
    confirmation, F10 fail-fast);
  - `phase-7-chords` not to be merged again until part B is tested;
  - Progress Check 2 on 25 Nov 2026.
- **`scripts/check.ps1`** runs the tests with `--noinput`, so a test
  database left by an interrupted run is replaced instead of stopping at
  Django's prompt. [[Environment-Setup]] says so.
- **Verified:** `scripts/check.ps1` passed with `--noinput`. Ruff lint and
  format were clean, `manage.py check` was clean, and no migrations were
  missing. 678 tests passed, with 97% coverage.

## 2026-11-20: a stray ] no longer blocks saving

On branch `phase-7-chords`. From the click-through: Worship Together's
Hark! file has `[(Em7)]]King`, and saving failed with "a ] closes a chord
never opened".

- **Fixed:** a `]` that closes nothing is removed before the ChordPro
  check (`chords.drop_stray_brackets`), and the save and Convert warnings
  list it ("Removed a stray ] on line 53."). An unclosed `[` is still an
  error. Directives, tablature and comment lines are left alone.
- **Confirmed:** a rhythm line of chords without slashes, `[| Am Bm7 Cmaj7
  D |]`, becomes `| [Am] [Bm7] [Cmaj7] [D] |` and transposes.
- **Tests** (made-up content):
  - a stray `]` saves with the warning and the chords around it transpose;
  - Convert lists it;
  - an unclosed `[` is still an error;
  - directives and tablature are left alone;
  - the rhythm line transposes.
- **Disk:** the first run stopped with drive C: full. After the user freed
  space, the leftover `test_chord_newver_db` from the failed run was
  removed by one small test run with `--noinput`, as `check.ps1` can't
  answer Django's prompt.
- **Notes:** [[Design-Decisions]] (Phase 7, chart marks) and [[Worship]].
- **Verified:** `scripts/check.ps1` passed. Ruff lint and format were
  clean, `manage.py check` was clean, and no migrations were missing. 678
  tests passed (7 new), with 97% coverage (`chords.py` 97%, `sheets.py`
  95%).

## 2026-11-20: ChordPro import and chart-mark choices approved

- **Approved:** the user approved the ChordPro import choices and the
  chart-mark display choices.
- **Recorded** in [[Design-Decisions]] (Phase 7, importing a ChordPro
  file):
  - the separate Import button;
  - the file's key wins over one already chosen;
  - files over the 20,000-character sheet limit are refused at import;
  - rhythm lines are converted in ChordPro files too.

  The display choices were already there: a capo and Nashville numbers
  count as a different key for the note, and N.C., x2 and footnote marks
  stay plain.
- Checks: documentation only, no code changed, so `scripts/check.ps1` was
  not run.

## 2026-11-20: kept marks shown apart in the viewer

On branch `phase-7-chords`; not merged yet.

- **Viewer:** marks kept as written (ChordPro annotations, `[*text]`) are
  shown in grey italic, apart from chords. When the sheet has such marks
  and is shown away from its own key (another key, a capo or Nashville
  numbers), a note under the sheet says "Some marks were kept as written
  and aren't transposed." (`Segment.kept`, `Rendered.kept_not_moved`).
- **Not affected:** N.C., repeat and footnote marks are standard marks;
  they get neither the style nor the note.
- **Tests:**
  - kept marks flagged, chords not;
  - the note only with kept marks and away from the sheet's key (including
    with a capo or numbers);
  - on the lineup song page: the note with the service key, none in the
    sheet's own key, and none without kept marks.
- **Notes:** [[Design-Decisions]] (Phase 7, chart marks) and [[Worship]].
- **Verified:** `scripts/check.ps1` passed. Ruff lint and format were
  clean, `manage.py check` was clean, and no migrations were missing. 671
  tests passed (5 new), with 97% coverage.

## 2026-11-20: optional chords and chart marks; unknown chords no longer block saving

On branch `phase-7-chords`; not merged yet. From the click-through:
Worship Together marks optional chords in parentheses (`[(F#m7)]`), and
saving failed with "isn't a chord".

- **Optional chords** in parentheses transpose and keep their parentheses
  (`chords.chord_in`). `(F#m7)` in E is `(G#m7)` in F#; Nashville numbers
  show `(2m7)`.
- **Chart marks:** N.C., `x2`, `(x2)` and footnote marks (`*`, `†`) are
  kept as written and never transposed (`chords.is_mark`). `D*` moves its
  chord and keeps the mark.
- **Unknown marks:** anything else unreadable in brackets is kept as a
  ChordPro annotation, `[*Zz9]`, shown as written and never transposed
  (`chords.keep_unread`). Convert and Save list them in a warning ("These
  marks were kept as written and won't transpose: line 35 …"), and the
  sheet still saves. An annotation shows without its star.
- **Hard errors** stay only for broken ChordPro: an unclosed bracket, a
  directive not alone on its line, a section never closed, or no chord at
  all. A sheet whose only bracket is an unknown mark therefore says "no
  chords".
- **Tests** (made-up content):
  - "(F#m7)" transposes with its parentheses;
  - N.C. and x2 are kept and not transposed;
  - "[Zz9]" saves as an annotation with the warning, on Save and on
    Convert;
  - an unclosed bracket and other broken ChordPro are still errors;
  - tablature is left alone;
  - optional chords work in pasted charts.

  Two earlier tests changed: an unknown chord used to block a save, and an
  annotation used to show its star.
- **Notes:** [[Design-Decisions]] (Phase 7), the [[workflow-spec]] and
  [[Worship]].
- **Verified:** `scripts/check.ps1` passed. Ruff lint and format were
  clean, `manage.py check` was clean, and no migrations were missing. 666
  tests passed (8 new), with 97% coverage (`chords.py` 96%, `sheets.py`
  95%).

## 2026-11-20: Worship Together ChordPro: bracketed rhythm lines, section names

On branch `phase-7-chords`; not merged yet. A bug from the click-through:
Worship Together's ChordPro downloads write a rhythm line inside one
bracket, `[| D / / G | / / / / |]`, and saving failed with "isn't a chord".

- **Fixed:** a bracket holding bar lines (`|` or `||`) or beat slashes is
  read as a rhythm line, with spaces or none. Each chord gets its own
  bracket, `| [D] / / [G] | / / / / |`, so it transposes
  (`chords.bracketed_rhythm`). One that can't be read becomes a comment.
  A rhythm line never blocks saving.
- **Added:** plain section lines in a ChordPro file show as section
  labels, like `[Verse]` in a pasted chart (`chords.section_line`):
  - Intro, Verse, Pre-Chorus, Chorus, Bridge, Interlude, Instrumental,
    Outro, Ending and Tag;
  - with an optional number and colon.
- **Tests** (made-up content):
  - a bracketed rhythm line with spaces (D to E gives E and A), with none,
    and with `||` bars;
  - an unreadable one becoming a comment while the sheet saves;
  - "Verse 1" and "Outro" shown as labels;
  - a whole Worship Together-style file imported, saved and transposed.
- **Notes:** [[Design-Decisions]] (Phase 7, import), the [[workflow-spec]]
  and [[Worship]].
- **Verified:** `scripts/check.ps1` passed. Ruff lint and format were
  clean, `manage.py check` was clean, and no migrations were missing. 658
  tests passed (9 new), with 97% coverage (`chords.py` 96%).

## 2026-11-20: import a ChordPro file

On branch `phase-7-chords`; not merged yet. An approved Phase 7 addition.

- **Import a ChordPro file** on the chord sheet form, beside the text box:
  - accepts .cho, .chopro, .chordpro, .pro and .txt files up to 200 KB,
    in UTF-8 (a byte order mark is fine);
  - gives a clear message for a wrong type, a file too large, one not in
    UTF-8, an empty file, or no file;
  - puts the text in the box for the person to check, then they save as
    usual. The file isn't stored (`sheets.read_import`);
  - the key comes from `{key:}` or `{k:}` and fills the Key field, which
    the person can change;
  - other directives stay in the text and don't touch the song's fields.
- **Rhythm lines** such as `|D//G|////|` (optionally after "Intro:") get
  their chords in brackets, so they transpose (`chords.rhythm_line`). An
  unreadable one becomes a comment, never a save error. Tablature is left
  as written.
- **Team members:** their imports stay pending, like pastes.
- **Recorded** in [[Design-Decisions]] (Phase 7), the [[Development-Plan]]
  and the [[workflow-spec]]: a person still brings in each chart, and
  nothing is fetched from any site. [[Worship]] is updated too.
- **Verified:** `scripts/check.ps1` passed. Ruff lint and format were
  clean, `manage.py check` was clean, and no migrations were missing. 649
  tests passed (15 new), with 97% coverage (`chords.py` 96%, `sheets.py`
  94%).

## 2026-11-20: Phase 7 part A approved; minor-key note on Nashville numbers

On branch `phase-7-chords`; not merged yet.

- **Approved and recorded** in [[Design-Decisions]] (Phase 7, "Approved
  after part A"), the [[workflow-spec]] (chords and playback) and the
  [[Glossary]]:
  - flats for C major and A minor;
  - Nashville numbers in a minor key count from the minor tonic and
    ignore a capo;
  - capo 0 to 7, with the easy shapes marked;
  - a personal transpose only in the page address;
  - one approved sheet per song, with the approve and discard rules;
  - "required" doesn't block confirming: missing sheets are marked;
  - one pending sheet per team member per song;
  - the lineup song page;
  - the Worship Together web-search link;
  - the audit trail holds no sheet text.
- **Added:** in Nashville view on a minor-key song, the viewer says
  "Numbers count from the minor key (1 = A minor)". `Key.long_name` gives
  "A minor" and "Bb major".
- **Glossary:** Personal Transpose and Nashville Numbers added; Chord
  Sheet notes one approved sheet per song.
- **Notes:** [[Worship]] (the minor-key note).
- **Verified:** `scripts/check.ps1` passed. Ruff lint and format were
  clean, `manage.py check` was clean, and no migrations were missing. 634
  tests passed (2 new), with 97% coverage.

## 2026-11-20: Phase 7, part A: chord sheets, the viewer and keys

Branch `phase-7-chords`. Built from [[Design-Decisions]] (Phase 7) and
[[0009-transposition-on-the-server]].

- **Decision change:** ChordSheetJS turned out to be GPL-2.0-only. The
  user chose a small converter in Python instead. Updated:
  - [[0009-transposition-on-the-server]];
  - [[Design-Decisions]];
  - the [[workflow-spec]];
  - the [[Development-Plan]];
  - the [[Concept-Brief]];
  - the [[Glossary]];
  - [[Technology-Stack]].

  Nothing from ChordSheetJS is vendored.
- **Models** (migration `songs/0005_chord_sheets`):
  - Chord Sheet: the ChordPro text and its key, pending or approved, at
    most one approved per song;
  - `Song.recording_key`;
  - the permissions `view_lyrics`, `view_chordsheet`, `add_chordsheet`
    and `approve_chordsheet`.
- **`apps/songs/chords.py`:** checks ChordPro (each message names the
  line); converts chords over words; renders any key, with sharps or flats
  following the key, slash chords, a capo and Nashville numbers.
- **`apps/songs/sheets.py`:**
  - approvers add a sheet at any time, approved at once;
  - team members paste one for a confirmed lineup song without a sheet,
    and it stays pending until approved;
  - approve and discard; Find chords links.
- **`apps/songs/viewer.py`:** the key, ±1, capo, numbers and
  practise-along, from the query string; htmx re-renders the sheet.
- **Screens:**
  - the song page's Chord sheet card and the sheet form (Convert, Save);
  - the lineup song page;
  - the chord sheet counts on the lineup page and card;
  - the key history on the Key and notes page;
  - the song page shows lyrics only with `view_lyrics` (review F13);
  - the recording's key on the song form and page.
- **Default roles:**
  - Worship Leader and Pastoral Staff: `view_lyrics`, and view, add and
    approve chord sheets;
  - Team Member: view and add chord sheets.
- **Tests:**
  - `apps/songs/tests/test_chords.py` and `test_chordsheets.py`;
  - `apps/worship/tests/test_lineup_songs.py`;
  - one existing song page test now gives its user `view_lyrics`;
  - new builders in [[Code-Conventions]]: `make_lineup`,
    `make_chord_sheet` and `HYMN_SHEET`.
- **Notes:** [[Worship]] (part A, permissions, roles); [[00-Home]] (status
  was still "Phase 5 done"); [[Development-Plan]] (part A ticked, Phase 7
  in progress).
- **Verified:** `scripts/check.ps1` passed. Ruff lint and format were
  clean, `manage.py check` was clean, and no migrations were missing. 632
  tests passed (68 new), with 97% coverage (`chords.py` 95%, `sheets.py`
  95%).

## 2026-11-20: Phase 7 decisions

The user approved five Phase 7 design decisions. They are recorded in
[[Design-Decisions]] (Phase 7), the [[workflow-spec]] (chords and
playback; Spotify safeguards), the [[Development-Plan]] (Phase 7 items
and "done when"), the [[Concept-Brief]] (playback, chord sheets and keys)
and the [[Glossary]].

1. **Transposition on the server**
   ([[0009-transposition-on-the-server]], new):
   - Python handles the service key, a personal transpose, capo positions
     and Nashville numbers; a key change re-renders with htmx;
   - the normal test suite covers it;
   - ChordSheetJS only converts pasted charts to ChordPro in the browser,
     and the server checks the saved ChordPro.
2. **The keys a song was sung in** replace "a key from a singer's range":
   its service keys in confirmed lineups, most recent first.
3. **Practise-along:** a person enters the recording's key on the song;
   without it, the toggle is hidden.
4. **Lyrics (review F13):** full lyrics on the song page only for people
   who plan, through a permission. Team members see the words through the
   chord sheet.
5. **No web request waits on Spotify (review F10):** a 429 fails fast,
   including saving the playlist and Find on Spotify, which today waits
   up to 30 seconds. The worker keeps its single short wait.

Also: [[Glossary]] gains Chord Sheet and Recording Key, and the Service
Key entry mentions the key history; [[00-Home]] lists decision 0009.
Checks: documentation only, no code changed, so `scripts/check.ps1` was not
run.

## 2026-11-20: README

- Added `README.md` at the project root, the first page someone opening
  the repository sees. It says:
  - what CHORD does, and what's built and what's next;
  - the stack;
  - quick-start commands, linking to [[Environment-Setup]] for the full
    steps;
  - how to run the website and the search worker, and how to try
    suggestions without Spotify;
  - the checks script, the folder layout, and where the docs start
    ([[00-Home]]);
  - the rules on secrets, Spotify data and lyrics.
- Checks: documentation only, no code changed, so `scripts/check.ps1` was
  not run.

## 2026-11-19: Phase 6 part B approved; "swapped in" feedback label

On branch `phase-6-lineups`; not merged yet.

- **Approved and recorded** in [[Design-Decisions]] (Phase 6), the
  [[workflow-spec]] (step 11, song usage, attendance report) and the
  [[Glossary]] (Suggestion Feedback, Song Usage):
  - **the feedback labels:** regenerated and pool songs leave none, and
    confirming again replaces the feedback;
  - **usage counting:** the report counts past services only; ranking
    counts every confirmed lineup of an earlier service;
  - **the overused highlight:** a song sung again sooner than the repeat
    window;
  - **the report permissions:** `worship.view_song_usage` for Worship
    Leader and Pastoral Staff; attendance reuses `record_attendance`.
- **Changed:** an alternative chosen in a swap now gets its own label,
  **swapped in** (a positive, like kept), so Phase 9 can tell it from a
  top pick that stayed. A swapped-in song that is later swapped out or
  removed is labelled swapped or removed.
- **Migration `worship/0009_feedback_swapped_in`:** the new label choice.
  Nothing is backfilled: lineups reviewed earlier kept no record of which
  "kept" songs came from a swap.
- **Notes:** [[Worship]] (feedback labels).
- **Verified:** `scripts/check.ps1` passed. Ruff lint and format were
  clean, `manage.py check` was clean, and no migrations were missing. 564
  tests passed (2 new), with 97% coverage (`feedback.py` 97%).

## 2026-11-19: Phase 6, part B: feedback, song usage and reports (Phase 6 done)

On branch `phase-6-lineups`. The phase is not merged yet.

- **Suggestion Feedback** (migration `worship/0008`; `feedback.py`):
  - while a lineup is reviewed, `Lineup.suggestion_outcomes` follows each
    suggestion placed in it: kept, swapped or removed. Regenerating
    forgets the songs it replaces, and pool songs leave none;
  - confirming saves the rows, replacing an earlier confirmation's;
  - the features are only the lyrics-based scores and the church's own
    data (`SuggestionFeedback.FEATURES`). No Spotify field, no Trusted
    Artist bonus, no version choice, no genre-filter record;
  - existing lineups start with their placed suggestions as kept.
- **Song usage** (`usage.py`, review F3): `ranking.song_usage()` reads the
  confirmed lineups of services, not cancelled, before the one being
  ranked. Familiarity and recent use now count.
- **Reports** (`reports.py`, `/worship/reports/`):
  - song usage, with a period filter and CSV export, highlighting songs
    sung again within the repeat window;
  - attendance, the headcount per service held, which doesn't exist until
    a headcount is recorded;
  - a new permission, `worship.view_song_usage`, for Worship Leader and
    Pastoral Staff. The attendance report uses `record_attendance`.
- **Wording:** the feel-mismatch reason now reads "Its feel (upbeat)
  doesn't match this slot, which asks for slow, but it fit best."
- **Notes:**
  - [[Worship]];
  - [[Design-Decisions]] (song usage done; the wording);
  - [[Glossary]] (Suggestion Feedback, Song Usage);
  - [[Development-Plan]] (Phase 6 done);
  - [[00-Home]].
- **Verified:** `scripts/check.ps1` passed. Ruff lint and format were
  clean, `manage.py check` was clean, and no migrations were missing. 562
  tests passed (23 new), with 97% coverage (`feedback.py` 96%,
  `reports.py` 95%, `lineups.py` 99%).

## 2026-11-19: Phase 6, part A click-through: four display fixes

On branch `phase-6-lineups`, from the user's click-through.

- **Feel reasons follow the slot.** A lineup song now stores only its
  theme reasons (match, tags, other versions). Its feel reason is worked
  out for the slot it is in now (`LineupItem.slot_reason`, from the new
  `sequencing.slot_reason`), so a song moved, swapped, added or
  regenerated into a slot never shows another slot's feel.
- **Full names.** A shared `display_name` (`apps/core/people.py`) and
  `{{ user|person_name }}` filter give the full name, or the username when
  there is none.
  - The lineup page already used it for "Confirmed by", "Sent back by" and
    the Mark: on the development database, "Pastor" is named "Church
    Pastor".
  - "About this search" ("Asked for … by") and the song page ("Reviewed
    by") printed usernames; both now use it.
- **No nested brackets.** "Other versions in the pool" now reads "Title,
  Artist; Title, Artist". The lineup audit lists songs the same way.
- **Arrows.** ↑ and ↓ show only where `lineups.allowed_moves` allows the
  move. The server still refuses the same moves; moving into a locked
  song's place now reads "<song> can't move into a locked song's place."
- **Migration `worship/0007_lineup_reason_text`:**
  - drops the feel reasons already stored on lineup songs;
  - rewrites saved "Other versions" reasons, on lineup songs and on
    suggestions, into the new form;
  - updates the help text of `LineupItem.reasons`.
- **Notes:**
  - [[Worship]];
  - [[Code-Conventions]] (naming people; no nested brackets).
- **Verified:** `scripts/check.ps1` passed. Ruff lint and format were
  clean, `manage.py check` was clean, and no migrations were missing. 539
  tests passed (13 new), with 97% coverage.

## 2026-11-19: Phase 6, part A review: the Mark, and adding any pool song

On branch `phase-6-lineups`, after the user reviewed part A.

- **Approved and recorded:** the user approved eight of part A's choices.
  They are now in [[Design-Decisions]] (Phase 6, "Approved after part A"),
  the [[workflow-spec]] and the [[Glossary]]:
  - default permissions come from `DEFAULT_ROLE_PERMISSIONS`;
  - both the leader and the pastor can save suggestions as the lineup;
    Office Staff can't see lineups;
  - locking isn't an edit, and a locked song stays put;
  - reopening or sending back clears the mark; confirming again clears
    the note;
  - a cancelled service's lineup can't be confirmed; a past service's can;
  - swap and regenerate use the latest finished run;
  - a never-confirmed draft is a 404 for team members;
  - leaders see theme notes.
- **Changed: adding from the pool.** Any pool song can now be added,
  except one a person marked "Not a worship song". Songs that failed the
  Worship Check, or were never checked, can be added and show a warning in
  the review and on the Add page. The team doesn't see the warning.
- **Changed: the leader's edits are marked.** The leader's edit to a
  confirmed lineup without the pastor's lock keeps it confirmed and marks
  it "Changed by <name>", with the time; no lock follows. Only the latest
  mark shows: the pastor's "Edited by" replaces it, and reopening or
  sending back clears it.
- **Model:** the mark is now general: `edited_at`, `edited_by` and
  `edited_with_final_say` replace `pastor_edited_at` and
  `pastor_edited_by`. Migration `0006_lineups` was regenerated in place,
  because it was never applied or pushed.
- **Notes:**
  - [[Design-Decisions]];
  - [[workflow-spec]] (roles, step 10);
  - [[Glossary]] (Locked Song and Mark added; Pastor's Lock updated);
  - [[Worship]].
- **Verified:** `scripts/check.ps1` passed. Ruff lint and format were
  clean, `manage.py check` was clean, and no migrations were missing. 526
  tests passed (9 more than part A), with 97% coverage (`lineups.py` 99%,
  the lineup views 97%).

## 2026-11-19: Phase 6, part A: lineups, review and the final say

Branch `phase-6-lineups`. Built from [[Design-Decisions]] (Phase 6) and
[[0008-final-say-permission]], with findings F4, F5 and F7 of the
[[2026-11-19-Workflow-Review]].

- **Models** (migration `worship/0006_lineups`):
  - Lineup: draft or confirmed, the source run, the latest confirmation,
    the pastor's lock, the "Edited by" mark, and the send-back note;
  - Lineup Item: song, slot, order, Service Key, notes, reasons and a lock;
  - the permissions `view_lineup`, `add_lineup`, `change_lineup` and
    `finalize_lineup`.
- **Rules** (`apps/worship/lineups.py`):
  - save the reviewed suggestions as the lineup (its own copy, F4);
  - swap, lock, reorder, remove, add from the pool, key and notes, and
    regenerate around locked songs; never two songs with the same title;
  - confirm, the pastor's lock, the mark, reopen and send back, all
    checked against `finalize_lineup`, never a role name.
- **F7:** a cancelled or past service gets no suggestions
  (`suggesting.planning_closed`) and no new lineup. A cancelled service's
  lineup can't be confirmed.
- **F5:** `can_plan`'s `change_lineup` now exists. The worship leader now
  sees theme notes; team members still don't.
- **Default roles:**
  - Pastoral Staff: view, add, change and finalize;
  - Worship Leader: view, add and change;
  - Team Member: view.

  Granted through `DEFAULT_ROLE_PERMISSIONS`, which the post_migrate sync
  applies on every `migrate` (the project's way of granting new
  permissions; see `accounts/migrations/0003`).
- **Labels:** a new `pastor` Label (default "Pastor").
- **Screens:**
  - the lineup page, swap, Add a song, Key and notes, and Send back;
  - a lineup card on the service page;
  - in the suggestions panel, "Save these songs as the lineup". The
    panel hides "Find songs" for cancelled or past services.
- **Other changes:**
  - `suggesting._feel_weight` became `feel_weight`, so regenerating uses
    the run's feel weight;
  - a new test builder, `make_search_run`;
  - the church tests' Label data now includes the `pastor` Label.
- **Notes:**
  - [[Worship]] (lineups, permissions, roles, settings);
  - [[Church-Setup]] (Labels);
  - [[Accounts]];
  - [[Glossary]] (Service Key);
  - [[Code-Conventions]] (builder);
  - [[Development-Plan]] (part A ticked; Phase 6 in progress; F7 added);
  - [[00-Home]].
- **Verified:** `scripts/check.ps1` passed. Ruff lint and format were
  clean, `manage.py check` was clean, and no migrations were missing. 517
  tests passed (73 new), with 97% coverage (`lineups.py` 99%, the lineup
  views 96%).

## 2026-11-19: workflow review; Phase 6 lineup decisions

- **Review:** [[2026-11-19-Workflow-Review]] reviewed the code on `master`
  (`239d167`) against the [[workflow-spec]], following [[Review-Prompt]].
  Verdict: mostly follows the flow, and no hard rule is broken. It made 14
  findings (F1 to F14), each sorted as must fix before Phase 6, fix during
  Phase 6, or later. Read-only: Ruff lint and format check passed,
  `manage.py check` was clean, there were no missing migrations, and 444
  tests passed (coverage not run).
- **Decisions approved by the user (F1, F2, F6):**
  - the final say is the permission `worship.finalize_lineup`, held by
    Pastoral Staff by default and by the Administrator. Code checks the
    permission, never a role name. There is a new church Label, `pastor`
    (default "Pastor");
  - the pastor's edits to a draft don't lock the worship leader out. The
    pastor's lock starts when the pastor confirms a lineup, or edits a
    confirmed one, and lasts until the pastor reopens it;
  - a reopened lineup counts as unconfirmed: team members see a "being
    revised" note instead;
  - the mark reads "Edited by <pastor Label> (<person's name>)", with the
    time;
  - sending back returns a lineup to draft with a note; it adds no state;
  - overused songs are highlighted in the song usage report, not given a
    report of their own.
- **Also aligned:**
  - F14: the spec now has one Spotify connection per user, as in
    Design-Decisions;
  - F8: song usage is computed from confirmed lineups, not stored.
- **Notes:**
  - [[0008-final-say-permission]] (new);
  - [[Design-Decisions]] (Phase 6, and the Phase 8 notification);
  - [[workflow-spec]] (roles, step 10, hard rules, tables);
  - [[Development-Plan]] (Phase 6 items and "done when");
  - [[Glossary]] (Final Say, Pastor's Lock and Send Back added; Lineup
    updated);
  - [[00-Home]] (links).
- **Readings approved by the user:**
  - "the pastor's lock" is the name, kept apart from the lock on a song;
  - only holders of the final say can send a lineup back, and sending back
    a confirmed lineup reopens it;
  - "overused" means sung again within the church's repeat window.
- **[[Concept-Brief]] updated to match, with the user's agreement:**
  - the pastor's lock starts only when the pastor confirms a lineup, or
    edits a confirmed one;
  - the mark reads "Edited by <pastor Label> (<name>)", with the time;
  - Spotify has one connection per user (the Admin row).
- Checks: documentation only, no code changed, so `scripts/check.ps1` was
  not run.

## 2026-11-18: theme tags keep today's rule

Tag options measured on the 23 seeded hymns with the ONNX models (in
memory; nothing changed), aiming for 3 to 5 sensible tags per song:

| Option | Tags per song | Songs with 3–5 tags | Faith given to |
|---|---|---|---|
| Today (0.5 or more, best four) | 3.7 | 21/23 | most hymns |
| (a) stand out on the model's margin, stricter | 2.6 | 14/23 | most hymns |
| (a) stand out on the model's margin, looser | 4.0 | 21/23 | 18/23 |
| (a) against each tag's average over the pool | 4.1 | 18/23 | 2/23 |
| (c) lyrics embedding against tag name and keywords | 2.3–3.4 | 8–16/23 | — |

- **Kept today's rule.** "(a) against each tag's average" was the most
  specific, but it makes a song's tags depend on the rest of the pool,
  bringing back the relative-score problem the fixed relevance scale just
  removed, and it gave Christ the Lord Is Risen Today "Birth of Jesus".
  The margin variants were close to today's tags or too few; (c) missed
  obvious tags (Silent Night without Birth of Jesus).
- Recorded "(a) against each tag's average" in the [[Development-Plan]]'s
  Future experiments, to revisit when the pool is larger. Updated
  [[Design-Decisions]] (the decision), the plan's Phase 5 follow-up list,
  [[Worship]] and [[00-Home]], which had it as open.
- Checks: documentation only, no code changed, so `scripts/check.ps1` was
  not run.

## 2026-11-18: unset feel costs half a step; theme-tag options measured

- **Placement:** a song whose feel isn't known now costs half a step (0.075
  with the default feel weight) in a slot that asks for a feel, so it never
  beats a known close match. In the before-and-after comparison, Come, Thou
  Fount (feel unset, 0.39) had taken Praise from Blessed Assurance
  (upbeat, 0.52). Updated: [[Design-Decisions]], [[workflow-spec]] step 8,
  [[Worship]].
- **Theme tags, measured only** on the 23 seeded hymns with the ONNX
  models, aiming for 3 to 5 tags per song: (a) stand-out on probabilities
  or margins, (a) against each tag's own average margin, and (c) lyrics
  embedding against each tag's name and keywords. Results are in
  Design-Decisions (Phase 5 follow-up). Nothing applied.
- Verified: `scripts/check.ps1` passed: Ruff lint and format,
  `manage.py check` clean, no missing migrations, 444 tests passed, 97%
  coverage.

## 2026-11-18: Phase 5 smoke-test fixes

The user's first live smoke test (seeded hymns, then Spotify) found nine
issues; the agreed fixes are in [[Design-Decisions]] (Phase 5 follow-up).

- **Fixed scale:** relevance and match labels come from the engine's
  `similarity_range`, not the pool; "doesn't match the theme well" added.
  Default weights recalibrated (familiarity 0.2, season 0.15, recent use
  0.3); a migration moves a church still on the old defaults.
- **Feel:** placement treats feel as a preference with a feel mismatch
  weight (a setting, 0.15); feel is left blank when the analysis isn't
  sure (a migration queues unreviewed songs for analysis again); one-click
  feel correction in the panel, kept by later analysis (`feel_reviewed`).
- **Worship check:** the pass mark is a church setting (Settings → Worship
  check), with the optional rule for artists not on the Trusted Artists
  list, off by default and applied after the model. Changing the rules or
  the list rechecks unreviewed songs without a model. One-click "Not a
  worship song". Each search's genre-filter result is recorded on the run,
  for information only.
- **Versions** of one song are grouped after ranking and one is kept; the
  pool keeps all. A lineup never holds two songs with the same title.
- A hint in the panel when the theme has no notes.
- `seed_hymns` now adds 23 public-domain hymns, with eight carols, four
  slow hymns and two Easter hymns.
- Fixed: a similarity exactly on a label's line could get the label below
  (floating point); relevance is now rounded first.
- **Measured, not changed:** a "neutral" class for theme tags can't help;
  the zero-shot model has only two classes. Awaiting a decision.
- Notes: [[Worship]], [[Glossary]] (Pass Mark, Worship Check Settings,
  Version; Feel and Worship Check reworded), [[0006-onnx-runtime-for-song-analysis]]
  update, [[Code-Conventions]], [[Environment-Setup]] (with the smoke-test
  commands), [[workflow-spec]] steps 6 to 9, the [[Development-Plan]]
  (follow-up list, and tempo from LRCLIB as a future experiment), and
  Design-Decisions (follow-up section; Phase 9 now also excludes the new
  artist rule, the kept version and the genre record from training).
- Verified:
  - `scripts/check.ps1` passed: Ruff lint and format, `manage.py check`
    clean, no missing migrations, 442 tests passed (404 before), 97%
    coverage.
  - Before-and-after rankings computed in memory with the ONNX models on
    the smoke-test runs ("Grace and salvation", "The birth of Jesus"); the
    two "Good News" recordings and three "Silent Night" versions now count
    once each.
  - Not applied to the development database yet: run `migrate`.

## 2026-11-18: Phase 5, song suggestions

- **The suggestion pipeline** ([[Worship]]), from the work in progress
  committed earlier: Suggestion Settings, Seasons, Search Runs and
  Suggestions; search phrases, Spotify search with the unfiltered retry,
  cleanup, lyrics, analysis, ranking over the whole pool, sequencing into
  the song slots, and reasons.
- **Fixed** in that work: `phrases.py` counted each chosen phrase twice,
  so a run searched about half the phrases the settings asked for.
- **Built to [[Design-Decisions]], Phase 5:**
  - the model's worship score (`Song.worship_model_score`, lyrics only)
    kept apart from the Trusted Artist bonus (`worship_score`); a
    migration queues analysed songs to be analysed again;
  - the Spotify safeguards in `apps/songs/spotify.py`, with the shared
    block saved as **Spotify Limit** rows; a quota pause makes a run rank
    the pool instead; Spotify requests and 429s are recorded on each run;
    Find on Spotify never fetches a pooled track and shows a pause;
  - one search worker, enforced by a PostgreSQL advisory lock
    (`apps/core/locks.py`), which `process_songs` also takes;
  - suggestions only for `worship.suggest_songs` (Worship Leader and
    Pastoral Staff by default).
- **Screens:** the Suggested lineup panel on the service page (HTMX
  progress while a run works), and Seasons and Suggestion settings in the
  worship settings.
- **`manage.py seed_hymns`**: nine public-domain hymns, to try
  suggestions without Spotify.
- **Notes:** [[0007-search-worker]] (new); [[0006-onnx-runtime-for-song-analysis]]
  update note; [[Glossary]] (Worship Check, Trusted Artist, and six new
  terms); [[Code-Conventions]]; [[Environment-Setup]]; `AGENTS.md` (one
  worker, and where the safeguards live); the [[Development-Plan]] Phase 5
  ticked and set Done; Design-Decisions' Phase 5 heading set done.
- Verified:
  - `scripts/check.ps1` passed: Ruff lint and format, `manage.py check`
    clean, no missing migrations, 404 tests passed (298 before), 97%
    coverage. The guard test passed.
  - Not verified live: Spotify (no credentials in `.env` yet) and the ONNX
    models on the new pipeline. The tests use FakeHttp and the keyword
    engine.
  - The migrations were not applied to the development database; run
    `python manage.py migrate`.

## 2026-11-18: the user's decisions on the remaining contradictions

- **Source order:** the [[Concept-Brief]] now ranks after
  [[Design-Decisions]] and before the [[workflow-spec]], in `AGENTS.md`
  and in the header of Design-Decisions.
- **Notifications:** Phase 6 shows an "Edited by pastor" mark with its
  time to everyone who can see the lineup, with no notification system.
  Phase 8 notifies the assigned team members in the app. Changed in
  Design-Decisions (Phases 6 and 8), the spec and the plan.
- **Spotify playlist:** saved automatically on confirmation; with no
  connection, or on a 429, it is skipped and a "Save to Spotify" button
  lets the leader retry. Changed in Design-Decisions (Phase 7), the spec
  and the plan.
- **One worker:** Phase 5 enforces it with a PostgreSQL advisory lock
  taken at worker startup; `claim_next_run` stays. Changed in
  Design-Decisions (Phase 5, with a test and a reminder to update the
  Worship note, decision 0006 and the Glossary with the code), the spec
  and the plan.
- **Office Staff** stays: added to the brief's roles table and the spec as
  an optional role that keeps the member directory up to date.
- **[[Development-Plan]]:**
  - the out-of-scope line now matches the brief;
  - Phase 5 now lists the Design-Decisions items: the raw model score,
    suggestions hidden from team members, the Spotify safeguards, one
    worker, the missing tests, and the notes to update;
  - Phase 6 now has the pastor's rules and the tests for each role;
  - Phase 7 now has Find chords, the chord-sheet count per lineup, the
    practise-along toggle, and the automatic playlist;
  - Phase 8 now has in-app notifications;
  - Phase 9 now excludes Spotify data from the training features, with a
    test;
  - the Phase 10 Development Mode question is moved to "Decided since".
- [[Project-Overview]] and [[00-Home]]: theme text as model input, and
  the brief's full out-of-scope list. [[0003-editable-roles]]: a dated
  update note (five default roles; the finance and records examples are
  out of scope).
- The spec's "What to produce" section moved to [[Review-Prompt]]
  (`04-Development/Reviews/`).
- Checks: documentation only, no code changed, so `scripts/check.ps1` was
  not run. Every `[[link]]` in the changed notes resolves.

## 2026-11-18: vault aligned with the updated brief and design decisions

- `AGENTS.md`, the [[Concept-Brief]] and [[Design-Decisions]] were updated
  by the user, answering the open questions of the workflow review
  (`docs/workflow-review.md`). The rest of the vault now follows them:
  - [[workflow-spec]]: theme text as model input, live versions, ranking
    the whole pool, the raw model score and the Trusted Artist bonus,
    suggestions hidden from team members, the pastor's decision rules,
    training features, chord sheets allowed early with approval of team
    members' pastes, encrypted tokens, the playback 429 fallback, a new
    Spotify safeguards section, an undeletable Administrator, and which
    expected tables are stored as fields.
  - [[0005-worship-planning-scope]]: the brief's longer out-of-scope list,
    the main module's priority, the stack departures (ONNX Runtime, JSON
    embeddings instead of pgvector; job queue still to record), Members
    beyond the basic directory, and the Administrator role.
  - [[Development-Plan]] Phase 7: chord sheets allowed before
    confirmation, approval of team members' pastes as a permission,
    encrypted Spotify tokens, the playback 429 fallback, the safeguards for
    server-side calls, and the Design-Decisions tests.
  - [[00-Home]]: links to the workflow spec and Design-Decisions, and the
    Phase 5 status note.
- Branch: `master` (Phase 4) was merged into `phase-4-song-pool` first, so
  these notes build on the Phase 4 vault.
- Checks: documentation only, no code changed, so `scripts/check.ps1` was
  not run. Links were checked by hand.

## 2026-11-17: Phase 4, the song pool

- **[[Worship]]'s song pool** (`apps/songs`):
  - Song, Theme Tag (30 neutral tags seeded, with keywords) and Trusted
    Artist (empty);
  - the Spotify client (app token, paged search, genre filter with an
    unfiltered retry, one track by ID) and the LRCLIB client (one request
    at a time, fallback search, Retry-After);
  - the ML engine: ONNX Runtime models or the keyword stand-in
    ([[0006-onnx-runtime-for-song-analysis]]), and `manage.py
    download_models`;
  - analysis from lyrics only: worship check, up to four theme tags, feel
    guess and embedding; a reviewed song keeps its corrections;
  - `manage.py process_songs` for lyrics and analysis;
  - the song library: list with filters, song page, editing, Check again,
    Find on Spotify, and the two settings lists;
  - default-role permissions and the audit trail.
- Shared pieces: `apps/core/http.py` (every outside call) and, in
  `apps/core/testing.py`, `ChordTestRunner` (network blocked, keyword
  engine), `FakeHttp` and `make_song`.
- Model choice: the 13 MB xtremedistil zero-shot model was tried and
  dropped for DeBERTa-v3-xsmall (96 MB). On four public-domain hymns and
  four invented secular songs, DeBERTa passed every hymn (0.86 to 0.999)
  and failed every secular song (0.01 or less). An invented love song in
  church imagery also passed (0.85); people correct such cases.
- Verified:
  - `scripts/check.ps1` passed: Ruff clean, `manage.py check` clean, no
    missing migrations, 298 tests passed, 97% coverage. The guard test
    passed. `ml/onnx.py` is 52% covered: tests never load a model.
  - By hand: `download_models` fetched both models, and the ONNX engine
    analysed the eight sample texts in about 1 s each. Three live LRCLIB
    lookups gave the expected found, found and not found.
  - Not verified live: Spotify, because no credentials are in `.env` yet.
    Its client is tested against the documented response shapes.
  - Migrations applied to the development database.

## 2026-11-17: Phase 3, worship schedule and themes; the scope change

- **Scope.** The project now follows the [[Concept-Brief]]
  ([[0005-worship-planning-scope]]). The [[Development-Plan]] was rewritten
  around it: Phases 3 to 10 are new, and Giving, Records, Services,
  Ministries and Events are out of scope.
- **Re-scoped the configuration layer:**
  - Modules are now Members, Worship, Teams and Announcements. A Module
    can span several apps and can need another Module ([[Church-Setup]]).
  - Labels are now member, worship service, sermon and lineup.
  - Default roles are now Administrator, Office Staff, Pastoral Staff,
    Worship Leader and Team Member ([[Accounts]]).
  - Two data migrations tidy existing installations: stale Module switches
    and Labels are dropped, and unused obsolete roles are removed.
- **[[Worship]]** (`apps/worship`), first part:
  - Service Templates with Song Slots, and one seeded neutral template;
  - Worship Services, the schedule list and the month calendar;
  - "Schedule weeks ahead" for templates with a usual day and time;
  - Themes with Series, and notes shown only to people who plan;
  - a headcount per service;
  - default-role permissions and the audit trail.
- Shared pieces: `apps/core/music.py` (Feel); a church-edited list's title
  can follow a Label; test builders `make_service` and `make_theme`.
- Installed the ML runtime chosen for later phases (ONNX Runtime,
  tokenizers, NumPy, huggingface-hub); nothing uses it yet.
- Verified:
  - `scripts/check.ps1` passed: Ruff clean, `manage.py check` clean, no
    missing migrations, 197 tests passed, 97% coverage. The guard test
    passed.
  - Migrations applied to the development database.

## 2026-11-16: Phase 2, Members

- [[Members]] (`apps/members`):
  - Member, Membership Status (with "counts as active"), Household and
    Household Roles, with neutral defaults seeded;
  - list, detail, add, edit, archive and restore;
  - the own-record page, private photos and files;
  - CSV import (preview, problem report, duplicate check) and CSV export
    using the same columns;
  - the privacy rules applied to lists, search, forms, import and export;
  - default role permissions.
- Shared pieces in `apps/core`:
  - church-edited lists (`ChoiceItem`, `SettingList`, `setting_list_urls`);
  - Custom Fields (`CustomFieldDefinition`, `CustomFieldsFormMixin`;
    [[0004-custom-field-values-as-json]]);
  - private file storage (`PRIVATE_MEDIA_ROOT`, `private_file_response`,
    `PrivateFileInput`).
- The "Members" Module now opens from the navigation and dashboard. The
  account menu shows "My member record" for linked accounts.
- Fixed while testing:
  - an import file with only blank headers was reported as "no rows"
    instead of "empty";
  - the household list wasn't reliably ordered;
  - the permission matrix tests now submit every role's ticks, as the page
    does.
- Verified:
  - `scripts/check.ps1` passed: Ruff clean, `manage.py check` clean, no
    missing migrations, 150 tests passed, 97% coverage. The
    guard test passed.
  - Migrations applied to the development database.

## 2026-11-16: Phase 1, Church Setup and Access

- [[Church-Setup]] (`apps/church`):
  - the Church Profile, as a single row, with its logo, currency and time
    zone;
  - the Module registry, `ModuleRequiredMixin` and navigation for
    switched-on Modules only;
  - Labels, with the `{% label %}` template tag;
  - the three-step setup wizard and the settings pages;
  - the dashboard.
- [[Accounts]]:
  - Roles on Django groups, with six seeded default roles
    ([[0003-editable-roles]]);
  - the permission matrix;
  - user management (add, edit, deactivate, set password);
  - My profile, password change, and password reset by email;
  - rules that protect the last administrator.
- Audit trail (`apps/audit`): `AuditEvent` and the
  `snapshot`/`diff`/`record_change` helpers, used by every Phase 1 screen,
  and the audit log page.
- Shared pieces in `apps/core`: `FilteredListView`, `FormPageMixin` and
  `form_page.html`, plus pagination and search templates. Also new: 403 and
  404 pages, and styled checkbox lists.
- Fixed while testing:
  - saving a new Church Profile over the existing row lost its creation
    time;
  - checkbox lists put the checkbox class on their outer wrapper;
  - the audit `diff()` ignored deleted values.
- Added Pillow 13.0.0 (image uploads).
- Verified:
  - `scripts/check.ps1` passed: Ruff clean, `manage.py check` clean, no
    missing migrations, 84 tests passed, 98% coverage. The guard test
    passed.
  - On the development server, protected pages redirect to sign in, and
    the sign-in and password reset pages render.

## 2026-11-15: Phase 0, engineering baseline

- Made the first Git commit (the foundation) and did Phase 0 on the
  branch `phase-0-baseline`.
- Added `apps/core`:
  - shared abstract models (`TimeStampedModel`, `PublicIdModel`);
  - a project form renderer that gives every form Bootstrap markup;
  - shared test-data builders;
  - the home page.
- Added the base template, with Bootstrap 5.3.3 and HTMX 2.0.4 stored in
  `static/vendor/` ([[0002-server-rendered-ui]]).
- Added sign in and sign out ([[Accounts]]).
- Added `scripts/check.ps1` and coverage.py.
- Added the denomination-free guard test.
- Documented the conventions in [[Code-Conventions]].
- Verified:
  - `scripts/check.ps1` passed: Ruff clean, `manage.py check` clean, no
    missing migrations, 13 tests passed, 100% coverage.
  - The guard test failed as expected on a temporary file containing a
    banned word; the file was then removed.
  - On the development server: an anonymous visitor to `/` is redirected
    to sign in, the sign-in page shows the Bootstrap form, and the vendor
    files are served (HTTP 200).

## 2026-11-15: Development plan

- Wrote the [[Development-Plan]]: ten phases for the management side, from
  the engineering baseline to hardening. The music features (ML song
  recommendation, playback, chord sheet viewer) are deferred to Phase 10.
- Each phase has task checklists and a "done when" condition, and the plan
  has a shared definition of done.
- No code changed.

## 2026-11-15: Documentation vault

- Set up this Obsidian vault in `docs/CHORD-Vault/`.
- Moved the glossary and the decision record into the vault so all project
  documentation lives in one place.

## 2026-11-15: Core design rule

- Decided that churches configure what they do instead of choosing a
  denomination: [[0001-configure-behavior-not-identity]].
- Defined the project's terms in [[Glossary]] and sketched the
  [[Services]] module.
- Added agent instructions (`AGENTS.md`, `CLAUDE.md`) so future development
  follows the rule.

## 2026-11-15: Project foundation

- Created the Django 5.2 project (`config/`) with settings read from `.env`.
- Created PostgreSQL database `chord_newver_db`, separate from the original
  CHORD's.
- Added the custom user model in `apps/accounts` and ran the initial
  migrations.
- Verified: `manage.py check` clean, Ruff clean, database connection to
  PostgreSQL 17 confirmed.
