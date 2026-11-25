# Code Conventions

How the code is organised, and the shared pieces every Module reuses.
Rows marked _(planned)_ are agreed in the [[Development-Plan]] but not built
yet.

| Topic          | Convention                                                                                                                       |
| -------------- | -------------------------------------------------------------------------------------------------------------------------------- |
| App layout     | Each Module is one or more Django apps in `apps/` (Worship is `apps/worship` and `apps/songs`; Teams is `apps/teams`; Occasions is `apps/occasions`; Announcements is `apps/announcements`); the Module registry lists them. Shared code is in `apps/core`, the audit trail in `apps/audit`, and in-app Notifications in `apps/notifications` (core: always on; send one with `notifications.services.notify`). |
| Shared models  | `apps/core/models.py`: `TimeStampedModel` (created/updated) and `PublicIdModel` (UUID used in URLs, so IDs can't be guessed).    |
| Business rules | Plain functions outside the views, tested directly. A small app keeps them in `services.py` (e.g. `apps/members/services.py`); Teams keeps its rules in `apps/teams/rostering.py`. The worship apps name each file for what it decides (e.g. `apps/worship/scheduling.py`), because "service" there means a Worship Service. |
| Large apps     | `apps/worship` splits `models/` and `views/` into one file per area (`schedule.py`, …); `models/__init__.py` exports every model. |
| UI             | Django templates, Bootstrap 5 and HTMX from `static/vendor/` ([[0002-server-rendered-ui]]). Pages extend `templates/base.html`.  |
| Page patterns  | A page's header, "More" menu, section tabs, status pills and two columns are shared ([[Design-System]], "Page patterns"): `{% page_header %}`, `{% more_menu %}`, `includes/section_tabs.html`, `includes/status_pill.html`. A Module's settings page is registered with `apps/core/settings_menu.py` (it then shows in the Settings hub); what a Module adds to the dashboard is registered with `apps/church/dashboard.py`. |
| Design system  | The owner's colours, fonts, icons, dark mode, back link and player card: [[Design-System]]. Restyle through `static/css/chord.css` and Bootstrap's variables; icons from `templates/includes/icons/`; a page's back link is `templates/includes/back_link.html`. |
| Page titles    | Every page sets `{% block title %}`; the base adds " · " and the church name.                                                    |
| Forms          | `{{ form }}` is enough. The project form renderer adds the Bootstrap classes and error markup (`apps/core/forms.py`).            |
| Form pages     | Simple create and edit pages use `FormPageMixin` and `templates/form_page.html`, with no template of their own. A page that needs more extends `form_page.html` and fills `form_extra` (inside the form, above the buttons) or `after_form` (below the card), as `accounts/user_form.html` does. |
| Lists          | `FilteredListView` (`apps/core/views.py`): pagination and `?q=` search over `search_fields`, plus the `includes/list_toolbar.html` and `includes/pagination.html` templates. |
| Permissions    | Views use `LoginRequiredMixin` and `PermissionRequiredMixin`; a user without permission gets a 403 page. Templates check `perms.app.codename`. |
| Module pages   | Every view of a Module puts `ModuleRequiredMixin` (with `module = "<code>"`) first, so a switched-off Module's pages return 404. A Module's `view_permission` (`apps/church/modules.py`) is the permission its main page needs; the navigation and dashboard list it only for people who hold it. |
| Church wording | UI text for concepts in the Labels list uses `{% label %}` ([[Church-Setup]]).                                                   |
| Naming people  | Text that names who did something uses the full name, or the username when there is none: `display_name(user)` (`apps/core/people.py`), or `{{ user\|person_name }}` with `{% load people %}`. Never print a user object directly. |
| Brackets       | Don't nest brackets in text: list songs as "Title, Artist" separated by semicolons, since artist names may hold brackets, such as "Charles Wesley (1739)". |
| HTMX requests  | `base.html` sends the CSRF token in every HTMX request header.                                                                   |
| Page scripts   | A page's own script lives in `apps/<app>/static/<app>/` and is loaded with `defer` from its include (e.g. `songs/player.js`). It reads the CSRF token from the body's `hx-headers`. |
| Deleting       | Users are deactivated and members archived, never deleted. Church-edited list items and Custom Fields are switched off. Worship services are cancelled, not deleted. |
| Between Modules | A Module never imports a Module that builds on it. It sends a signal instead, which the other Module connects to in its `AppConfig.ready()`: Worship sends `apps.worship.signals.lineup_changed`, and Teams turns it into Notifications. Core apps (Accounts, Audit, Notifications) may be imported by any Module. Accounts asks the Modules what a role change takes away through `apps/accounts/role_changes.py`: a Module registers a finder there (Teams: `apps/teams/leaving.py`). The Worship calendar shows other Modules' bookings through `apps/worship/bookings.py`: Occasions registers a source there. A Module's `view_permission` may be a tuple, any one of which opens it. |
| Row locks      | When two people can race for one thing (taking a swap, or assigning someone while they add a blackout), lock the row with `select_for_update` inside `transaction.atomic()`, and re-check the rules after the lock. With `select_related` on a nullable foreign key, lock only the row itself: `select_for_update(of=("self",))`. When there is no one row to lock (booking a time on the calendar), take a transaction lock: `wait_for_transaction_lock(BOOKINGS)` (`apps/core/locks.py`). |
| Dates and times | Stored in UTC and shown in the church's time zone, which the middleware activates for each request. Code that runs outside a request (rules, the worker) asks `scheduling.church_time_zone()`. |
| Files          | Only the church logo is public (`media/church/`). Personal files use private storage (see below). |

## Audit trail

Record every change to sensitive data with `apps/audit/services.py`:

1. Take `before = snapshot(obj, FIELDS)` **when the form is built**
   (`get_form_kwargs`), because a ModelForm copies its data onto the
   instance while validating.
2. After saving, call `record_change(request.user, obj, action, diff(before,
   snapshot(obj, FIELDS)))`.
   - For a new object use `diff({}, after)`.
   - For a deleted object use `diff(before, {})`.
   - A change with no differences is not recorded.

`FIELDS` maps a display label to an attribute name or a function. Never put
password values in it.

Sign-ins, sign-outs and failed sign-ins are recorded apart, in
`audit.SignInEvent`, from Django's sign-in signals (`apps/audit/signins.py`),
so `AuditEvent` holds only changes to data. Signing a test client in
(`force_login`) records a sign-in there too, never an `AuditEvent`.

A CSV a person downloads escapes cells a spreadsheet would run as a formula
(starting with `=`, `+`, `-` or `@`) with a leading apostrophe
(`apps/members/accounts.py`, `_safe`). Events are listed at `/audit/` for users with
`audit.view_auditevent`.

## Church-edited lists

For any list a church defines (statuses, roles, types, funds), build the
model on `ChoiceItem` (`apps/core/setting_lists.py`). It provides a name,
description, sort order and active switch, plus `.active()` and
`.usable(current)` for form choices. Declare its pages with a
`SettingList(...)` and `setting_list_urls(config, route_prefix=...)`:

- You get list, add and edit pages, gated by the Module and by
  permissions, with audit.
- Items are switched off, never deleted. The list's Active column is a
  switch for people with the change permission: ticking it saves at once
  (HTMX; a Save button without JavaScript) through `<url_prefix>_switch`,
  which posts the state wanted, so a second click or a page left open
  never flips an item the wrong way. The change is audited.
- `nav=` adds tabs that link sibling settings lists.
- `title=` can be a function of the request when the title uses a Label
  (e.g. "Sermon series").

Seed neutral defaults with a data migration.

## Custom Fields

Church-defined fields ([[0004-custom-field-values-as-json]]):

1. Subclass `CustomFieldDefinition` (`apps/core/custom_fields.py`) and add
   a unique constraint on `key` within its scope.
2. Add a `custom_data` JSONField to the record.
3. Use `CustomFieldsFormMixin` on the form: call
   `add_custom_fields(definitions, include_private=...)` in `__init__` and
   `save_custom_fields(upload_folder)` in `save()`. Override
   `custom_file_url()` to link existing files.

Show values with `custom_values(...)`. For CSV import, read text with
`definition.parse_text()`, and display stored values with
`definition.display()`.

## Private files

Personal files (member photos, uploaded documents) use
`get_private_storage` (`apps/core/storage.py`):

- Files are stored under `PRIVATE_MEDIA_ROOT` (`protected_media/`, which
  Git ignores) and have no URL.
- Upload paths come from `random_upload_name(folder, filename)`, wrapped
  in a module-level function.
- Serve a file from a permission-checked view with
  `private_file_response(name, inline=...)`. Only images are shown inline;
  everything else downloads.
- Edit forms show the current file with `PrivateFileInput(url=...)`.

## Outside services and models

- Every call to an outside service goes through `apps/core/http.py`
  `request()`, which returns a `Response` with any status and raises
  `HttpError` only when there is no answer. Each service gets a client
  module that turns statuses into its own error (e.g. `SpotifyError`).
- Clients take `sleep` (and `clock`) arguments, so tests check waiting
  without waiting.
- ML goes through `apps/songs/ml/get_engine()`, which `settings.ML_ENGINE`
  picks ([[0006-onnx-runtime-for-song-analysis]]). Engines offer
  `embed(texts)` and `score(text, labels)`, and declare a
  `similarity_range` (the similarity of unrelated texts and of a close
  match), which ranking uses as its fixed scale; nothing else touches a
  model.
- Church rules that use Spotify data, such as the Trusted Artist bonus and
  the rule for artists not on the list, are applied after the model in
  `apps/songs/analysis.py` (`decide_check`), never inside an engine, and
  are never training features.
- Only lyrics and the church's own text go into an engine. Lyrics are
  never logged, printed or put in the audit trail.
- Spotify calls go through `SpotifyClient` only, which applies the
  safeguards ([[Design-Decisions]], Phase 5): it checks the shared block
  (`spotify.current_block()`, a `SpotifyLimit` row) before every request,
  saves and logs every 429, and raises `SpotifyRateLimited` or
  `SpotifyPaused`. By default it fails fast on a 429, as every web request
  must (review F10); only the search worker builds it with
  `may_wait=True`, which waits out one short Retry-After and retries once. Catch `SpotifyPaused` where a
  feature can carry on without Spotify; show `block_message()` to people.
  The client counts `calls` and keeps `limits` for the caller to record.
- A user's own Spotify account goes through `apps/songs/connections.py`:
  `connection_for(user)`, `access_token(connection, client)` (refreshed
  and saved as needed) and `call_with_token(connection, client, call)`
  (refreshes once when Spotify refuses the token); the same functions
  work on `church_account()`, the Church Spotify Account, which only
  playlists use. Tokens are encrypted
  with `connections.encrypt`; never log, print or audit them. Functions
  that hold them use `sensitive_variables`.
- Work that calls Spotify or LRCLIB outside a web request runs in the
  search worker ([[0007-search-worker]]). A command that does such work
  takes `advisory_lock(SEARCH_WORKER)` (`apps/core/locks.py`) and refuses
  to run when `LockHeld` is raised.

## A new Module's permissions

Model permissions appear in the permission matrix automatically, once the
Module's app is listed in the Module registry. To give default roles a new
permission, add it to `DEFAULT_ROLE_PERMISSIONS` in
`apps/accounts/roles.py` ([[0003-editable-roles]]).

## Tests

- Tests live in `apps/<app>/tests/test_*.py` and use Django's test runner
  on a temporary PostgreSQL test database.
- `apps/core/testing.py` has the shared test-data builders. Add new
  builders there instead of repeating setup code in each test.
  - `make_user(roles=[...], perms=[...], church=None)`: a user with a
    Membership in `church` (the first church by default; `church=False`
    for none). `perms` go on a role of the user's own, because
    permissions come only from roles ([[0014-church-platform]]).
  - `make_church(name="Other Church")`: a church with its defaults, as
    registering one gives (`seed_church`)
  - `make_administrator()`
  - `complete_setup(**profile_fields)`
  - `make_member(**fields)`
  - `make_service(**fields)`: a worship service a week from now, on the
    seeded template
  - `make_theme(service=None, **fields)`
  - `make_song(tags=(), **fields)`: a song with a unique Spotify ID
  - `make_search_run(service, songs, placed=None)`: a finished Search Run
    that ranked `songs` in order, the first ones placed one per slot
  - `make_lineup(service, songs, keys=(), confirmed=True)`: a lineup stored
    directly, with service keys
  - `make_chord_sheet(song, chordpro=HYMN_SHEET, key="G", approved=True)`:
    a chord sheet; `HYMN_SHEET` is a public-domain hymn in ChordPro
  - `make_occasion_type(**fields)`: an active Occasion Type, 120 minutes
  - `make_occasion(occasion_type=None, **fields)`: an Occasion two weeks
    from now, stored directly (no clash check)
  - `make_team_part(name=None)`: a Team Part with a unique name (the
    seeded defaults exist too)
  - `make_team_profile(user, parts=())`
  - `make_assignment(service, person, part=None, reply="pending")`: an
    Assignment stored directly (the rules refuse past services); the
    person gets the part in their Team Profile
  - `TEST_PASSWORD`
  - `SPOTIFY_TEST_SETTINGS`: use with `override_settings(**...)` for
    Spotify set up with made-up credentials and token key.
  - `make_spotify_connection(user, access=..., refresh=..., expires_in=3600)`:
    a connection with made-up tokens, stored encrypted.
  - `close_file_response(response)`: closes a file download in a test
    without also closing the test database connection.
  - `quiet_logger(test, name="apps.songs.spotify")`: silences a logger
    for one test, such as the Spotify client's 429 warnings.
- Spotify tests use `TestCase` (the client reads the shared block from the
  database) and pass the client a fake `clock` and `sleep`, so waiting
  moves the fake clock instead of the test. A test of "another process"
  opens a second connection with `connections.create_connection("default")`
  and closes it at the end.
- The test runner (`ChordTestRunner`, `TEST_RUNNER` in settings) blocks the
  network, sets `ML_ENGINE` to "keyword", clears the Spotify credentials
  and uses the fast MD5 password hasher (tests only). The setup lives in
  `apps/core/test_environment.py` so that each parallel worker runs it
  too; `apps/core/tests/test_test_environment.py` checks it. Tests run in
  parallel processes, each with its own database copy and in-memory cache,
  so a test must not depend on another test's state. A test that needs an outside service wraps the code in
  `FakeHttp()`, replies with `web.reply(method, url_prefix, data)` (or a
  function of the call), and checks `web.calls`. Lyrics in tests are
  invented or public domain.
- Tests that upload files use `override_settings(MEDIA_ROOT=...)` or
  `override_settings(PRIVATE_MEDIA_ROOT=...)` with a temporary folder.
- A test that two people at once really wait on a row lock needs committed
  data, so it uses `TransactionTestCase` with `serialized_rollback = True`
  (which restores the seeded rows afterwards) and two threads, each
  closing its database connection when done. Pause the first inside the
  lock by patching a function it calls after locking
  (`apps/teams/tests/test_swaps.py`, `SimultaneousTakeTests`).
- Every view gets tests for both an allowed user and a refused user.
- `apps/core/tests/test_denomination_free.py` enforces
  [[0001-configure-behavior-not-identity]]. It fails if "denomination",
  "tradition" or "religion" appears in project code, templates, static
  files or seed data. Third-party files in `static/vendor/` are not scanned.
- Coverage is measured by `scripts/check.ps1`. Migrations and tests are
  excluded from the figure.
