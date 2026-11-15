# Code Conventions

How the code is organised. Rows marked _(planned)_ are agreed in the
[[Development-Plan]] but not built yet.

| Topic          | Convention                                                                                                                       |
| -------------- | -------------------------------------------------------------------------------------------------------------------------------- |
| App layout     | One Django app per Module in `apps/`. Shared code is in `apps/core`.                                                             |
| Shared models  | `apps/core/models.py`: `TimeStampedModel` (created/updated) and `PublicIdModel` (UUID used in URLs, so IDs can't be guessed).     |
| Business rules | _(planned)_ `services.py` functions in each app. Service Request steps go in `apps/services/workflow.py`.                        |
| UI             | Django templates, Bootstrap 5 and HTMX from `static/vendor/` ([[0002-server-rendered-ui]]). Pages extend `templates/base.html`.   |
| Page titles    | Every page sets `{% block title %}`; the base adds " · CHORD".                                                                   |
| Forms          | `{{ form }}` is enough. The project form renderer adds the Bootstrap classes and error markup (`apps/core/forms.py`).             |
| HTMX requests  | `base.html` sends the CSRF token in every HTMX request header.                                                                   |
| Lists          | _(planned)_ Paginated, searchable and filterable through one shared list mixin.                                                  |
| Deleting       | _(planned)_ Members, giving, records and requests are archived or reversed, never hard-deleted.                                  |
| Money          | _(planned)_ `DecimalField`; currency set in the Church Profile (default PHP).                                                    |
| Files          | _(planned)_ Uploads go to private media and are served only through permission-checked views.                                    |

## Tests

- Tests live in `apps/<app>/tests/test_*.py` and use Django's test runner
  on a temporary PostgreSQL test database.
- `apps/core/testing.py` has shared test-data builders, starting with
  `make_user()` and `TEST_PASSWORD`. Add new builders there instead of
  repeating setup code in each test.
- `apps/core/tests/test_denomination_free.py` enforces
  [[0001-configure-behavior-not-identity]]. It fails if "denomination",
  "tradition" or "religion" appears in project code, templates, static files
  or seed data. Third-party files in `static/vendor/` are not scanned.
- Coverage is measured by `scripts/check.ps1`. Migrations and tests are
  excluded from the figure.
