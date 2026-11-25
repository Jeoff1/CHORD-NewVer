# Environment Setup

## Database

- PostgreSQL 17, running locally as the Windows service `postgresql-x64-17`.
- Database `chord_newver_db`, owned by `chord_user`. It is separate from the
  original CHORD's `chord_db`.
- Connection settings come from `.env` (`DB_NAME`, `DB_USER`, `DB_PASSWORD`,
  `DB_HOST`, `DB_PORT`). `.env` is never committed; `.env.example` lists the
  keys without secret values.

## Running the project

From the `CHORD-NewVer` folder in PowerShell:

```powershell
.\.venv\Scripts\activate
python manage.py migrate
python manage.py createsuperuser   # first time only
python manage.py runserver
```

Then open <http://127.0.0.1:8000/> and sign in. On a new database, the
first administrator (the superuser) is taken to the setup wizard. Other
administrators are users given the Administrator role under
**Administration → Users**.

## Uploaded files

- `media/` holds public uploads (the church logo).
- `protected_media/` holds private uploads (member photos and files).
  Neither folder is in Git; both must be included in backups along with
  the database.

## Songs: Spotify, lyrics and models

- **Spotify:** create an app in the Spotify developer dashboard and put its
  `SPOTIFY_CLIENT_ID` and `SPOTIFY_CLIENT_SECRET` in `.env`. Without them,
  Find on Spotify says Spotify isn't set up.
- **Each user's Spotify account** (playback and playlists):
  - make a token key and put it in `.env` as `SPOTIFY_TOKEN_KEY`:
    `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`.
    It encrypts users' tokens. Keep it out of Git; changing it disconnects
    everyone. Without it, "Spotify account" says Spotify isn't set up;
  - in the Spotify dashboard, add the Redirect URI
    `http://127.0.0.1:8000/worship/songs/spotify/callback/` (Spotify allows
    plain http only for 127.0.0.1, not `localhost`, so open CHORD at
    `http://127.0.0.1:8000/`). A server with another address sets
    `SPOTIFY_REDIRECT_URI` to its own HTTPS callback;
  - in Development Mode, Spotify lets only the users added under the
    app's **User Management** connect (up to 5), and the app's owner needs
    Premium. Full playback in the browser needs Premium too; everyone else
    gets the embedded player.
- **The Church Spotify Account** (optional; church settings, Spotify tab):
  it takes one of the User Management slots in Development Mode, like a
  person does, and doesn't need Premium (it only holds playlists). It uses
  the same Redirect URI.
- **Models:** `python manage.py download_models` fetches the two ONNX
  models (about 120 MB) into `ml_models/`
  ([[0006-onnx-runtime-for-song-analysis]]). Check the free disk space
  first; the command refuses to leave less than 200 MB. To run without
  them, set `ML_ENGINE=keyword`.
- **Which engine runs:** `ML_ENGINE` in `.env` picks it. When `.env` has
  no `ML_ENGINE` line, CHORD uses `onnx`, the downloaded models. The tests
  always use `keyword`, whatever `.env` says. See the smoke test below for
  how to check.
- **The search worker:** song suggestions need it running, in its own
  terminal: `python manage.py run_worker` (stop it with Ctrl+C). Run
  **one** only: a second one refuses to start ([[0007-search-worker]]).
  Between searches it fetches lyrics and analyses new songs.
- **Lyrics and analysis without the worker:** `python manage.py
  process_songs` (add `-v 2` to list each song) fetches lyrics from LRCLIB
  one at a time and analyses new songs. It refuses to run while the worker
  runs. Set `LRCLIB_USER_AGENT` to name the installation and a contact
  page.
- **Trying suggestions without Spotify:** `python manage.py seed_hymns --church <slug>`
  adds 23 public-domain hymns and carols to the song pool. Once the worker has
  analysed them, a service with a theme can use "Rank the song pool only".

### Smoke test: suggestions with the real models

From the `CHORD-NewVer` folder in PowerShell, without activating the
virtual environment:

```powershell
# 1. Download the models into ml_models/ (once; about 120 MB)
.\.venv\Scripts\python.exe manage.py download_models

# 2. Check the app uses them: expect "ML_ENGINE: onnx" and "Missing models: none"
.\.venv\Scripts\python.exe manage.py shell -c 'from django.conf import settings; from apps.songs.ml.catalog import MODELS; print(''ML_ENGINE:'', settings.ML_ENGINE); print(''Models folder:'', settings.ML_MODELS_DIR); print(''Missing models:'', [m.folder for m in MODELS if not m.is_installed(settings.ML_MODELS_DIR)] or ''none'')'

#    Then load them: expect "Engine loaded: onnx:all-MiniLM-L6-v2"
.\.venv\Scripts\python.exe manage.py shell -c 'from apps.songs.ml import get_engine; print(''Engine loaded:'', get_engine().name)'

# 3. Terminal 1: the web server
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py runserver

# 3. Terminal 2: the search worker (only one)
.\.venv\Scripts\python.exe manage.py run_worker
```

- In Windows PowerShell 5.1, the `shell -c` code uses only single quotes
  (doubled inside the outer ones): PowerShell drops double quotes from the
  arguments it passes to Python.
- `keyword` instead of `onnx` means `.env` sets `ML_ENGINE=keyword`;
  delete that line. A song analysed by the other engine is analysed again
  by the worker, since embeddings from different engines don't compare.
- With `SPOTIFY_CLIENT_ID` and `SPOTIFY_CLIENT_SECRET` set, "Find songs"
  calls Spotify for real. To try the pipeline without it, run
  `.\.venv\Scripts\python.exe manage.py seed_hymns --church <slug>` and use "Rank the song
  pool only".

## Email

Without email settings, emails such as password reset links print in the
`runserver` console. To send real email, set the `DJANGO_EMAIL_*` keys
listed in `.env.example`.

## Checks before calling work done

```powershell
.\scripts\check.ps1
```

It runs, in order and stopping at the first failure:
1. Ruff lint and format check.
2. `manage.py check`.
3. A check for missing migrations.
4. The tests, under coverage, in 4 parallel processes.
5. The coverage report, combined from every process.

The full check takes about 70 seconds. Two lighter forms help while
working:

```powershell
.\scripts\check.ps1 -Quick                          # every test, no coverage (~65 s)
.\scripts\check.ps1 -Quick -Tests apps.songs        # one app's tests only
```

Use `-Quick` after each change; run the full check before every commit.
The script runs numpy's OpenBLAS with one thread per test process
(`OPENBLAS_NUM_THREADS=1`), so the parallel processes don't run Windows
out of memory when the C: drive is nearly full.
The Git hook `scripts/git-hooks/pre-commit` does that automatically once
turned on (step 7 of the setup below): it runs the full check before each
commit and stops the commit if anything fails. A commit that changes only
`docs/` or `*.md` files skips it. The hook checks the files on disk, so
unstaged changes count too. Git never copies hooks between clones, so each
clone turns it on once.
A `-Tests` run never counts as done on its own. `-Workers N` changes the
number of test processes (default 4; each opens its own database
connection, and memory is tight while C: is nearly full).

The tests create and remove a temporary database, `test_chord_newver_db`,
plus one copy per process (`test_chord_newver_db_1` to `_4`), which
`chord_user` is allowed to create. They run with `--noinput`, so one left
behind by an interrupted run (for example when the disk filled up) is
replaced without a prompt.

## Setting up on a new machine

1. Install Python 3.14 and PostgreSQL 17.
2. Create the database: `createdb -U chord_user -E UTF8 chord_newver_db`.
3. `py -3.14 -m venv .venv`, then `pip install -r requirements.txt`.
4. Copy `.env.example` to `.env` and fill in `DJANGO_SECRET_KEY` and
   `DB_PASSWORD` (and the Spotify keys, when available).
5. `python manage.py migrate`.
6. `python manage.py download_models`.
7. `git config core.hooksPath scripts/git-hooks`, so the full check runs
   before every commit.
