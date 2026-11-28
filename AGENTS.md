# CHORD (new version) agent guidance

CHORD is a worship planning system: a service's theme becomes a confirmed
song lineup with tracks, chord sheets and keys. Its scope is the concept
brief in `docs/CHORD-Vault/01-Project/Concept-Brief.md` (decision 0005).

## Scope and priorities

**The main module is the theme-based song lineup.** CHORD's core is
building a service's song lineup from its theme: the people who plan choose
the songs, helped by the pipeline that suggests songs fitting the theme
from Spotify (since 2026-11-26 the lineup comes first and suggestions
assist, decision 0015), followed by review, confirmation, chord sheets,
keys and playback.
It comes first: when effort or time is limited, finish and polish this
module before any supporting module, and never let supporting work delay it.

**Exception (approved 2026-11-24):** the adviser's requests of 24 Nov
(Phase 9A in the Development Plan) come before Phase 9, learning to rank.
Phase 9 is built only if time remains before the final presentation
(1–4 Dec 2026). Phase 9B, the Church Platform (approved 2026-11-25,
decision 0014), comes before the rest of Phase 9A. The rest of the
core-first rule still holds.

**Top priority (approved 2026-11-26): Phase 9C, guided service planning.**
The owner's changes to planning a worship service come before everything
else still to build (A6, A7, Phase 9 and Phase 10): four steps (Theme,
the church's Praise Team, Song Lineup, Confirm) with a next-step panel
that tells the pastor what to do and where to click. It is part of the
main module, so the core-first rule agrees with it.

**Supporting church management stays minimal.** Build only what helps the
worship workflow, in its smallest useful form:

- Service scheduling and service templates
- Occasions such as weddings, baptisms and funerals, as their own Module
  apart from worship services: booked by the pastor or requested by church
  members, sharing the calendar (decision 0013); no lineup or team, and no
  fees, requirements or church records
- Church Member role, batch accounts, user history and printable member
  reports (Phase 9A)
- Themes (sermon series removed from the screens on 2026-11-28)
- Team roster: assignments, availability and swap requests
- Member directory: retired on 2026-11-28 (`settings.RETIRED_MODULES`;
  its code, data and tests stay). A church's people are its Users, under
  Members in the sidebar. Don't bring it back without asking
- Announcements to the whole team or one service team
- Attendance as a headcount per service
- Song usage report

**Out of scope:** giving and finance (including fees for occasions),
records, ministries, events, leadership appointment or ordination
workflows, SMS messaging, check-in and follow-up, and per-person attendance
(the adviser's "who attended a service" is on hold until the user decides).
Raise it with
the user before building any of them. When unsure whether a feature is
minimal enough, ask, and suggest the smallest version that serves worship
planning.

## Core rule: configure behavior, not identity

CHORD serves any Christian church and never asks for its denomination
(see `docs/CHORD-Vault/02-Architecture/Decisions/0001-configure-behavior-not-identity.md`).
Every feature follows this:

- **Every Module ships in every installation.** A church switches a Module
  on or off; a switched-off Module is hidden, and its data stays intact.
- **Church practice is data the church enters.** Anything that differs
  between churches (which kinds of service it holds, their song slots,
  theme tags, seasons, team parts, search genres, ranking weights) is a
  model or setting the church edits, with neutral defaults. Wording is the
  exception: see Labels below.
- **Code branches only on settings.** Write `if template.repeats_weekly`,
  never a check on denomination, tradition or church name. When a feature
  seems to need "if church X does Y", add a setting for Y.
- **Optional steps disappear when unused.** A church that defines no
  seasons gets no season scoring; one that never records a headcount sees
  no attendance report.
- **Use the Labels in UI text** for concepts whose wording differs
  between churches (member, worship service, sermon, lineup, team). Since
  2026-11-28 churches no longer edit them: every church sees CHORD's
  neutral defaults (the owner's decision), but code still reads them
  through the Labels helpers, never as hard-coded words.
- **Denomination-free.** Denomination, Tradition and religion stay out of
  models, forms, seed data, fixtures and UI copy.

Before finishing any feature, check every new model, form, seed row and
condition against this rule.

## Outside services and models

- **Spotify data is never model input or a training feature.** Spotify
  supplies candidates and playback only. The models read only LRCLIB lyrics,
  the church's theme text (the text of a sermon PDF and of the main
  scripture passage included) and the
  church's own tags, and ranking features
  come from the church's own data. The Spotify artist name, title, album,
  track ID and length, and any score adjusted by them (such as the Trusted
  Artist bonus), never reach a model or a training set.
- **Store only these Spotify fields:** track ID, title, artist, album and
  length, plus the ID of a playlist CHORD itself created, used only to find
  and update that playlist, never as model input or a training feature
  (decision 0010). Never store audio.
- **Lyrics come only from LRCLIB,** never from Spotify or an unofficial
  Spotify lyrics endpoint.
- **Never call Spotify Recommendations, Audio Features or Audio Analysis.**
- **Never scrape Ultimate Guitar** or use its private or mobile API. Chord
  sheets are pasted in by people and converted to ChordPro.
- **Spotify calls follow the safeguards** in
  `04-Development/Design-Decisions.md`: stop on the first 429, respect
  Retry-After across all processes, never retry in a loop, pause all Spotify
  calls on `QUOTA_EXCEEDED`, and run only one worker. `SpotifyClient`
  (`apps/songs/spotify.py`) applies them; never call Spotify around it.
  The worker holds a PostgreSQL advisory lock (`apps/core/locks.py`), so a
  second worker or `process_songs` refuses to start.
- **LRCLIB requests go one at a time,** and every result is cached.
- **OpenStreetMap** (map tiles and Nominatim's address lookup) is used
  only by the browser, in the church address's location picker
  (`church/location_picker.js`), only when the person acts, at most one
  lookup a second, with OpenStreetMap credited. The spot is never stored
  or sent to CHORD: only the address text is saved.
- **Tests never use the network or load a model.** Use the stand-ins the
  project provides; a test that needs Spotify, LRCLIB or a real model is
  wrong.
- Lyrics and chord sheets are copyrighted: keep them inside the
  church's installation, and never put them in fixtures, seed data, the vault or
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
- **Workflow spec:** `workflow-spec.md` describes the intended workflow.
- **Design decisions:** `04-Development/Design-Decisions.md` holds agreed
  decisions and safeguards, grouped by phase. Before starting a phase, read
  its section and build what it lists, including its tests. Don't build
  items for a later phase early. At the end of the phase, say which of its
  items are done and which tests cover them.

## Agreed design: what wins, and when to ask

When sources disagree, follow them in this order:

1. The rules in this file
2. Numbered decision records in `02-Architecture/Decisions/`
3. `04-Development/Design-Decisions.md`
4. `01-Project/Concept-Brief.md`
5. `workflow-spec.md`
6. `04-Development/Development-Plan.md`

If a lower source contradicts a higher one, flag it and fix the lower one
after I agree; never quietly follow the lower one.

Workflow rules that hold in every phase:

- Team members see a lineup only after it is confirmed.
- The pastor's decision on a lineup is final. Build this as a permission
  held by the pastoral role, never as a check on a role name, so it follows
  the core rule above.
- If a task would break any rule in this file or an agreed decision, stop
  and ask me first. Explain the conflict and suggest an option that keeps
  the rule. If something is unclear, ask instead of guessing.
- When I approve a design change, update `Design-Decisions.md`,
  `workflow-spec.md` and, for a hard-to-reverse choice, a numbered decision
  record, in the same task, and mention it in your summary.

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
  docs. That includes the Spotify client secret and the token encryption
  key. Users' Spotify tokens are stored in the database **encrypted**
  (Fernet, key from `.env`), and never shown or logged.
- Run `.\scripts\check.ps1 -Quick` (lint, format, Django checks,
  migrations, every test in parallel; about a minute) after each change.
  Run the full `.\scripts\check.ps1` (the same, with coverage) before
  committing or calling work done; it must pass. The Git pre-commit hook
  (`scripts/git-hooks/`) runs it on every commit that changes more than
  docs; never bypass it with `--no-verify`.