# CHORD

A worship planning system for churches. The pastor posts a service's theme,
CHORD suggests songs whose lyrics fit it, the worship leader shapes the
lineup, and the team sees the confirmed songs with their keys.

CHORD works for any Christian church and never asks for a denomination:
what differs between churches (kinds of service, song slots, theme tags,
seasons, wording) is set by each church.

## What it does

- **Schedule and themes:** worship services from church-defined templates,
  each with a theme (title, scripture, notes) and an optional sermon series.
- **Song suggestions:** the theme becomes search phrases; CHORD finds songs on
  Spotify, fetches lyrics from LRCLIB, checks whether they read as worship
  songs, and ranks them by how well the lyrics match the theme, with the
  reason for each pick.
- **Lineups:** the suggestions become a draft lineup that the worship leader
  can swap, lock, reorder and re-key. The leader or the pastor confirms it,
  and the pastor has the final say. The team sees a lineup only once it is
  confirmed.
- **Reports:** song usage (with CSV export), and attendance as a headcount
  per service.
- **Church setup:** users and roles, the church's own wording (Labels),
  Modules that can be switched on and off, an audit trail, and a member
  directory.

Coming next: chord sheets and Spotify playback, team rosters and
announcements, and learning to rank from people's choices.

## Built with

Python 3.14, Django 5.2, PostgreSQL 17, server-rendered templates with
Bootstrap 5 and HTMX, and ONNX Runtime for the song analysis models. Song
data comes from the Spotify Web API; lyrics come from LRCLIB.

## Getting started

You need Python 3.14 and PostgreSQL 17. From the project folder in
PowerShell:

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env      # then fill in DJANGO_SECRET_KEY and DB_PASSWORD
python manage.py migrate
python manage.py download_models # the song analysis models, about 120 MB
python manage.py createsuperuser
git config core.hooksPath scripts/git-hooks  # run the checks before every commit
```

The database is `chord_newver_db`, owned by `chord_user` with permission to
create databases (the tests need it). The full steps, including creating the
database, are in
[`docs/CHORD-Vault/02-Architecture/Environment-Setup.md`](docs/CHORD-Vault/02-Architecture/Environment-Setup.md).

## Running it

CHORD needs two terminals, each with the environment activated:

```powershell
python manage.py runserver   # the website, at http://127.0.0.1:8000/
python manage.py run_worker  # the search worker (run only one)
```

Sign in with the superuser account; the setup wizard runs the first time.
To try suggestions without Spotify, run `python manage.py seed_hymns` to
add public-domain hymns, then use "Rank the song pool only" on a service.

Spotify search needs `SPOTIFY_CLIENT_ID` and `SPOTIFY_CLIENT_SECRET` in
`.env`, from an app on the Spotify developer dashboard. Without them,
everything else still works.

## Checks

```powershell
.\scripts\check.ps1          # full check with coverage, before committing
.\scripts\check.ps1 -Quick   # the same without coverage, after each change
```

It runs Ruff (lint and format), Django's checks, a missing-migrations check,
and the full test suite in 4 parallel processes, with coverage. The tests
never use the network or load a real model. With the Git hook turned on
(last line of Getting started), the full check runs before every commit
that changes more than docs, and a failure stops the commit.

## Project layout

| Folder           | What's in it                                           |
| ---------------- | ------------------------------------------------------ |
| `apps/worship`   | Schedule, themes, suggestions, lineups and reports     |
| `apps/songs`     | The song pool, Spotify and LRCLIB clients, song analysis |
| `apps/church`    | Church profile, Modules, Labels and the setup wizard   |
| `apps/accounts`  | Users and roles                                        |
| `apps/members`   | The member directory                                   |
| `apps/audit`     | The audit trail                                        |
| `apps/core`      | Shared models, views and test helpers                  |
| `config`         | Django settings and URLs                               |
| `docs/CHORD-Vault` | All project documentation (an Obsidian vault)        |

## Documentation

Start at [`docs/CHORD-Vault/00-Home.md`](docs/CHORD-Vault/00-Home.md). It
links the concept brief, the workflow spec, the architecture decisions, the
module notes, the development plan and the development log. `AGENTS.md`
holds the rules for anyone, person or AI, working on the code.

## A few rules

- Secrets live only in `.env`, which is never committed.
- Spotify data is never used as input to the song models or for training.
  The models read only lyrics, the church's theme text and its own tags.
- Lyrics and chord sheets are copyrighted: they stay inside the installation
  and never go into the repository, fixtures or logs.
