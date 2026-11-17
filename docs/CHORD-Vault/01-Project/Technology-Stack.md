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
| ML runtime       | ONNX Runtime, `tokenizers`, NumPy; models fetched with `huggingface-hub` ([[0006-onnx-runtime-for-song-analysis]]) |
| ML models        | all-MiniLM-L6-v2 (embeddings, Apache-2.0); deberta-v3-xsmall-zeroshot-v1.1-all-33 (zero-shot, MIT) |
| Outside services | Spotify Web API (search; later playback), LRCLIB (lyrics), through `apps/core/http.py` (standard library `urllib`) |
| Documentation    | This Obsidian vault            |

Exact package versions are pinned in `requirements.txt`.
