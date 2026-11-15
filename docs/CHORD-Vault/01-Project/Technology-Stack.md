# Technology Stack

| Part             | Choice                         |
| ---------------- | ------------------------------ |
| Language         | Python 3.14                    |
| Web framework    | Django 5.2 (LTS)               |
| Database         | PostgreSQL 17                  |
| Database driver  | psycopg 3                      |
| Settings         | `.env` file via python-dotenv  |
| Linting/format   | Ruff                           |
| UI               | Django templates, Bootstrap 5.3, HTMX 2.0 (stored in `static/vendor/`; see [[0002-server-rendered-ui]]) |
| Test coverage    | coverage.py                    |
| Documentation    | This Obsidian vault            |

Exact package versions are pinned in `requirements.txt`.
