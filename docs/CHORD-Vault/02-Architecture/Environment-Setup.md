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

## Checks before calling work done

```powershell
ruff check .
ruff format --check .
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test
```

## Setting up on a new machine

1. Install Python 3.14 and PostgreSQL 17.
2. Create the database: `createdb -U chord_user -E UTF8 chord_newver_db`.
3. `py -3.14 -m venv .venv`, then `pip install -r requirements.txt`.
4. Copy `.env.example` to `.env` and fill in `DJANGO_SECRET_KEY` and
   `DB_PASSWORD`.
5. `python manage.py migrate`.
