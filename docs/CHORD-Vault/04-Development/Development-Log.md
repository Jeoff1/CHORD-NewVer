# Development Log

Newest entries first. Template: `Templates/Development-Log-Entry`.

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
