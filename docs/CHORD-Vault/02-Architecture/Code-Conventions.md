# Code Conventions

How the code is organised, and the shared pieces every Module reuses.
Rows marked _(planned)_ are agreed in the [[Development-Plan]] but not built
yet.

| Topic          | Convention                                                                                                                       |
| -------------- | -------------------------------------------------------------------------------------------------------------------------------- |
| App layout     | One Django app per Module in `apps/`. Shared code is in `apps/core`, and the audit trail in `apps/audit`.                        |
| Shared models  | `apps/core/models.py`: `TimeStampedModel` (created/updated) and `PublicIdModel` (UUID used in URLs, so IDs can't be guessed).    |
| Business rules | _(planned)_ `services.py` functions in each app. Service Request steps go in `apps/services/workflow.py`.                       |
| UI             | Django templates, Bootstrap 5 and HTMX from `static/vendor/` ([[0002-server-rendered-ui]]). Pages extend `templates/base.html`.  |
| Page titles    | Every page sets `{% block title %}`; the base adds " · " and the church name.                                                    |
| Forms          | `{{ form }}` is enough. The project form renderer adds the Bootstrap classes and error markup (`apps/core/forms.py`).            |
| Form pages     | Simple create and edit pages use `FormPageMixin` and `templates/form_page.html`, with no template of their own.                  |
| Lists          | `FilteredListView` (`apps/core/views.py`): pagination and `?q=` search over `search_fields`, plus the `includes/list_toolbar.html` and `includes/pagination.html` templates. |
| Permissions    | Views use `LoginRequiredMixin` and `PermissionRequiredMixin`; a user without permission gets a 403 page. Templates check `perms.app.codename`. |
| Module pages   | Every view of a Module puts `ModuleRequiredMixin` (with `module = "<code>"`) first, so a switched-off Module's pages return 404. |
| Church wording | UI text for concepts in the Labels list uses `{% label %}` ([[Church-Setup]]).                                                   |
| HTMX requests  | `base.html` sends the CSRF token in every HTMX request header.                                                                   |
| Deleting       | Users are deactivated, never deleted. _(planned)_ Members, giving, records and requests are archived or reversed.               |
| Money          | _(planned)_ `DecimalField`, in the currency set in the Church Profile.                                                           |
| Files          | The church logo is in `media/church/`. _(planned)_ Private uploads are served only through permission-checked views.            |

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
  - `TEST_PASSWORD`
- Every view gets tests for both an allowed user and a refused user.
- `apps/core/tests/test_denomination_free.py` enforces
  [[0001-configure-behavior-not-identity]]. It fails if "denomination",
  "tradition" or "religion" appears in project code, templates, static
  files or seed data. Third-party files in `static/vendor/` are not scanned.
- Coverage is measured by `scripts/check.ps1`. Migrations and tests are
  excluded from the figure.
