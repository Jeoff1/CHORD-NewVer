# CHORD (new version) agent guidance

CHORD is a worship planning system: a service's theme becomes a confirmed
song lineup with tracks, chord sheets and keys. Its scope is the concept
brief in `docs/CHORD-Vault/01-Project/Concept-Brief.md` (decision 0005).
Giving, records, requested services, ministries and events are out of
scope; raise it with the user before building any of them.

## Core rule: configure behavior, not identity

CHORD serves any Christian church and never asks for its denomination
(see `docs/CHORD-Vault/02-Architecture/Decisions/0001-configure-behavior-not-identity.md`).
Every feature follows this:

- **Every Module ships in every installation.** A church switches a Module
  on or off; a switched-off Module is hidden, and its data stays intact.
- **Church practice is data the church enters.** Anything that differs
  between churches (which kinds of service it holds, their song slots,
  theme tags, seasons, team parts, search genres, ranking weights,
  wording) is a model or setting the church edits, with neutral defaults.
- **Code branches only on settings.** Write `if template.repeats_weekly`,
  never a check on denomination, tradition or church name. When a feature
  seems to need "if church X does Y", add a setting for Y.
- **Optional steps disappear when unused.** A church that defines no
  seasons gets no season scoring; one that never records a headcount sees
  no attendance report.
- **Use the church's Labels in UI text** for concepts whose wording differs
  between churches (member, worship service, sermon, lineup).
- **Denomination-free.** Denomination, Tradition and religion stay out of
  models, forms, seed data, fixtures and UI copy.

Before finishing any feature, check every new model, form, seed row and
condition against this rule.

## Outside services and models

- **Spotify data is never model input.** Spotify supplies candidates and
  playback only. The models read lyrics from LRCLIB and the church's own
  tags, and ranking features come from the church's own data.
- **Tests never use the network or load a model.** Use the stand-ins the
  project provides; a test that needs Spotify, LRCLIB or a real model is
  wrong.
- Lyrics and chord sheets are copyrighted: keep them inside the
  installation, and never put them in fixtures, seed data, the vault or
  logs. Seed data may use public-domain hymns only.

## Documentation: the Obsidian vault

All project documentation lives in the Obsidian vault `docs/CHORD-Vault/`.
Start at `00-Home.md` before changing code in an area, and read the module
note for that area.

- **Glossary:** `01-Project/Glossary.md`. Use its terms in code, notes and
  UI; add a term there as soon as it is settled.
- **Decisions:** `02-Architecture/Decisions/NNNN-slug.md` (numbered, from
  `Templates/Decision.md`). Record a decision there when it is hard to
  reverse, would surprise a later reader, and was a real trade-off. Flag any
  change that contradicts an existing decision instead of overriding it.
- **Module notes:** `03-Modules/<Module>.md` (from `Templates/Module.md`).
- **Code conventions:** `02-Architecture/Code-Conventions.md` lists the
  shared pieces every Module reuses (module gating, Labels, audit trail,
  list and form views, test builders); read it before writing code.
- **Development plan:** `04-Development/Development-Plan.md` sets the build
  order. Work on the current phase, follow its slice steps and definition of
  done, and tick a task only once its checks pass. When a phase finishes,
  set its **Status** in the plan's phase table, then end the report to the
  user with two lists taken from that table: **Phases done** and **Phases
  left**.

Every development task ends with the vault matching the code:

1. Add a dated entry at the top of `04-Development/Development-Log.md`
   saying what changed and which checks ran, with their results.
2. Update the affected module note (create it from the template when work on
   a module starts), including the church settings the module uses.
3. Update the module table and **Current status** in `00-Home.md`.

Mark something built or complete only after its tests and checks pass.
Link notes with Obsidian `[[Note-Name]]` links, and keep notes describing
what the code does now: edit or delete statements that are no longer true.
Secrets stay out of the vault.

## Project facts

- PostgreSQL database `chord_newver_db`, separate from the original CHORD's
  `chord_db`. Settings come from `.env` (template: `.env.example`).
- Custom user model `accounts.User` (`apps/accounts`). Keep it as the user
  model.
- Secrets and real passwords go only in `.env`, never in code, Git, logs or
  docs. That includes the Spotify client secret; users' Spotify tokens are
  stored in the database and never shown or logged.
- Run `.\scripts\check.ps1` (lint, format, Django checks, migrations,
  tests with coverage) before calling work done; it must pass.
