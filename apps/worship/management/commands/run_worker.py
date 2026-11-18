"""The search worker: carries out queued Search Runs, and between them
fetches lyrics and analyses new songs (decision 0007).

Run **one** worker only. It holds a PostgreSQL advisory lock while it runs,
so a second worker (or ``process_songs``) refuses to start: this keeps
Spotify and LRCLIB to one caller at a time (Design-Decisions, Phase 5).
"""

import time

from django.core.management.base import BaseCommand, CommandError

from apps.core.locks import SEARCH_WORKER, LockHeld, advisory_lock
from apps.songs.lyrics import LrclibClient
from apps.songs.ml import EngineUnavailable, get_engine
from apps.songs.pool import process_pending
from apps.worship import suggesting

BACKLOG_BATCH = 5
ALREADY_RUNNING = (
    "Another search worker (or process_songs) is already running. Only one "
    "may run at a time, so Spotify and LRCLIB get one request at a time."
)


class Command(BaseCommand):
    help = (
        "Run the search worker: find songs for queued suggestion requests, "
        "then fetch lyrics and analyse new songs. Only one may run. Stop it "
        "with Ctrl+C."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--once",
            action="store_true",
            help="Stop when nothing is left to do, instead of waiting for more.",
        )
        parser.add_argument(
            "--interval",
            type=float,
            default=3.0,
            help="Seconds to wait between checks when idle.",
        )

    def handle(self, *args, once=False, interval=3.0, **options):
        try:
            with advisory_lock(SEARCH_WORKER):
                self.run(once, interval)
        except LockHeld as error:
            raise CommandError(ALREADY_RUNNING) from error

    def run(self, once, interval):
        # Safe only because no other worker can be running (the lock).
        stale = suggesting.fail_stale_runs()
        if stale:
            self.stdout.write(f"Marked {stale} interrupted run(s) as failed.")
        self.stdout.write("Search worker started.")
        lyrics_client = LrclibClient()
        try:
            while True:
                if self.work_once(lyrics_client):
                    continue
                if once:
                    break
                time.sleep(interval)
        except KeyboardInterrupt:
            self.stdout.write("Search worker stopped.")

    def work_once(self, lyrics_client):
        """Do one piece of work; False when there was nothing to do."""
        run = suggesting.claim_next_run()
        if run is not None:
            self.stdout.write(f"Finding songs for {run.service}")
            suggesting.execute(run, lyrics_client=lyrics_client)
            self.stdout.write(f"  {run.get_status_display()}: {run.message}")
            return True
        try:
            result = process_pending(
                lyrics_client=lyrics_client, engine=get_engine, limit=BACKLOG_BATCH
            )
        except EngineUnavailable as error:
            self.stderr.write(str(error))
            return False
        handled = (
            result.lyrics_found
            + result.lyrics_missing
            + result.lyrics_failed
            + result.analysed
        )
        if handled:
            self.stdout.write(
                f"Songs: {result.lyrics_found} lyrics found, {result.analysed} analysed."
            )
        return bool(handled)
