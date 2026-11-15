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
4. The tests, under coverage.
5. The coverage report.

The tests create and remove a temporary database, `test_chord_newver_db`,
which `chord_user` is allowed to create.

## Setting up on a new machine

1. Install Python 3.14 and PostgreSQL 17.
2. Create the database: `createdb -U chord_user -E UTF8 chord_newver_db`.
3. `py -3.14 -m venv .venv`, then `pip install -r requirements.txt`.
4. Copy `.env.example` to `.env` and fill in `DJANGO_SECRET_KEY` and
   `DB_PASSWORD`.
5. `python manage.py migrate`.
