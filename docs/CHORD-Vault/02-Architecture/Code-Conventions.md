# Code Conventions

How the code is organised, and the shared pieces every Module reuses.
Rows marked _(planned)_ are agreed in the [[Development-Plan]] but not built
yet.

| Topic          | Convention                                                                                                                       |
| -------------- | -------------------------------------------------------------------------------------------------------------------------------- |
| App layout     | Each Module is one or more Django apps in `apps/` (Worship is `apps/worship` and `apps/songs`); the Module registry lists them. Shared code is in `apps/core`, and the audit trail in `apps/audit`. |
| Shared models  | `apps/core/models.py`: `TimeStampedModel` (created/updated) and `PublicIdModel` (UUID used in URLs, so IDs can't be guessed).    |
| Business rules | Plain functions outside the views, tested directly. A small app keeps them in `services.py` (e.g. `apps/members/services.py`). The worship apps name each file for what it decides (e.g. `apps/worship/scheduling.py`), because "service" there means a Worship Service. |
| Large apps     | `apps/worship` splits `models/` and `views/` into one file per area (`schedule.py`, …); `models/__init__.py` exports every model. |
| UI             | Django templates, Bootstrap 5 and HTMX from `static/vendor/` ([[0002-server-rendered-ui]]). Pages extend `templates/base.html`.  |
| Page titles    | Every page sets `{% block title %}`; the base adds " · " and the church name.                                                    |
| Forms          | `{{ form }}` is enough. The project form renderer adds the Bootstrap classes and error markup (`apps/core/forms.py`).            |
| Form pages     | Simple create and edit pages use `FormPageMixin` and `templates/form_page.html`, with no template of their own.                  |
| Lists          | `FilteredListView` (`apps/core/views.py`): pagination and `?q=` search over `search_fields`, plus the `includes/list_toolbar.html` and `includes/pagination.html` templates. |
| Permissions    | Views use `LoginRequiredMixin` and `PermissionRequiredMixin`; a user without permission gets a 403 page. Templates check `perms.app.codename`. |
| Module pages   | Every view of a Module puts `ModuleRequiredMixin` (with `module = "<code>"`) first, so a switched-off Module's pages return 404. |
| Church wording | UI text for concepts in the Labels list uses `{% label %}` ([[Church-Setup]]).                                                   |
| HTMX requests  | `base.html` sends the CSRF token in every HTMX request header.                                                                   |
| Deleting       | Users are deactivated and members archived, never deleted. Church-edited list items and Custom Fields are switched off. Worship services are cancelled, not deleted. |
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
password values in it. Events are listed at `/audit/` for users with
`audit.view_auditevent`.

## Church-edited lists

For any list a church defines (statuses, roles, types, funds), build the
model on `ChoiceItem` (`apps/core/setting_lists.py`). It provides a name,
description, sort order and active switch, plus `.active()` and
`.usable(current)` for form choices. Declare its pages with a
`SettingList(...)` and `setting_list_urls(config, route_prefix=...)`:

- You get list, add and edit pages, gated by the Module and by
  permissions, with audit.
- Items are switched off, never deleted.
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
  `embed(texts)` and `score(text, labels)`; nothing else touches a model.
- Only lyrics and the church's own text go into an engine. Lyrics are
  never logged, printed or put in the audit trail.

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
  - `make_user(roles=[...], perms=[...])`
  - `make_administrator()`
  - `complete_setup(**profile_fields)`
  - `make_member(**fields)`
  - `make_service(**fields)`: a worship service a week from now, on the
    seeded template
  - `make_theme(service=None, **fields)`
  - `make_song(tags=(), **fields)`: a song with a unique Spotify ID
  - `TEST_PASSWORD`
  - `close_file_response(response)`: closes a file download in a test
    without also closing the test database connection.
- The test runner (`ChordTestRunner`, `TEST_RUNNER` in settings) blocks the
  network, sets `ML_ENGINE` to "keyword" and clears the Spotify
  credentials. A test that needs an outside service wraps the code in
  `FakeHttp()`, replies with `web.reply(method, url_prefix, data)` (or a
  function of the call), and checks `web.calls`. Lyrics in tests are
  invented or public domain.
- Tests that upload files use `override_settings(MEDIA_ROOT=...)` or
  `override_settings(PRIVATE_MEDIA_ROOT=...)` with a temporary folder.
- Every view gets tests for both an allowed user and a refused user.
- `apps/core/tests/test_denomination_free.py` enforces
  [[0001-configure-behavior-not-identity]]. It fails if "denomination",
  "tradition" or "religion" appears in project code, templates, static
  files or seed data. Third-party files in `static/vendor/` are not scanned.
- Coverage is measured by `scripts/check.ps1`. Migrations and tests are
  excluded from the figure.
