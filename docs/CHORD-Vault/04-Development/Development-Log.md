# Development Log

Newest entries first. Template: `Templates/Development-Log-Entry`.

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
