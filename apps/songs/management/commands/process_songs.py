"""Fetch lyrics for new songs and analyse them, one LRCLIB request at a time.

It takes the search worker's lock, so it refuses to run while the worker
does: LRCLIB must get one request at a time across processes.
"""

from django.core.management.base import BaseCommand, CommandError

from apps.core.locks import SEARCH_WORKER, LockHeld, advisory_lock
from apps.songs.lyrics import LrclibClient
from apps.songs.ml import EngineUnavailable, get_engine
from apps.songs.pool import process_pending


class Command(BaseCommand):
    help = (
        "Fetch lyrics for songs that need them and analyse songs with new "
        "lyrics (worship check, theme tags, feel and embedding). Refuses to "
        "run while the search worker runs; the worker does this work itself."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--limit", type=int, default=None, help="Handle at most this many songs."
        )

    def handle(self, *args, limit=None, verbosity=1, **options):
        report = self.stdout.write if verbosity > 1 else None
        try:
            with advisory_lock(SEARCH_WORKER):
                result = process_pending(
                    lyrics_client=LrclibClient(),
                    engine=get_engine,
                    limit=limit,
                    report=report,
                )
        except LockHeld as error:
            raise CommandError(
                "The search worker is running, and it fetches lyrics and analyses "
                "songs itself. Only one may run at a time."
            ) from error
        except EngineUnavailable as error:
            raise CommandError(str(error)) from error
        self.stdout.write(
            self.style.SUCCESS(
                f"Lyrics found for {result.lyrics_found}, not found for "
                f"{result.lyrics_missing}, lookup failed for {result.lyrics_failed}; "
                f"{result.analysed} analysed."
            )
        )
