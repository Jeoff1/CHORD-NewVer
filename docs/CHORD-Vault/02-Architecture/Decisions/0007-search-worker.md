---
status: accepted
---

# One search worker, a management command polling the database

Song searches call Spotify and LRCLIB one request at a time and run the ML
models, so they can't run in a web request. They run in **one** search
worker, `manage.py run_worker`, which polls the `SearchRun` table for
waiting runs and works through songs that need lyrics or analysis between
them. It holds a PostgreSQL advisory lock while it runs, so a second worker
(or `process_songs`) refuses to start. Recorded with Phase 5 (2026-11-18);
the [[Concept-Brief]] suggested Celery or BullMQ
([[0005-worship-planning-scope]]).

## Considered Options

- **Celery (or another job queue) with a Redis or RabbitMQ broker**: the
  brief's suggestion. It adds a broker to install and run beside
  PostgreSQL, for one church with five users or fewer and one job at a
  time. Rejected as more to run than the work needs.
- **Running the search in the web request**: a search takes minutes and
  would load the models into the web process. Rejected.
- **Several workers sharing a lock around Spotify and LRCLIB calls**: only
  needed if one worker can't keep up. The safeguards say to run one worker
  ([[Design-Decisions]], Phase 5), so the lock guards the whole worker
  instead.

## Consequences

- Runs are claimed with `SELECT … FOR UPDATE SKIP LOCKED`, which would
  also be safe with several workers; the advisory lock is what keeps it to
  one.
- When the worker starts, runs left "running" by a worker that stopped are
  marked failed. This is safe only because no other worker can be running.
- The lock belongs to the worker's database session: PostgreSQL releases
  it if the process dies, so a crashed worker never blocks the next one.
- If nothing runs the worker, runs stay "waiting"; after a few minutes the
  service page says how to start it.
