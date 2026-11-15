# Development Log

Newest entries first. Template: `Templates/Development-Log-Entry`.

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
