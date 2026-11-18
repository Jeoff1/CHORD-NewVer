"""Fetch lyrics for new songs and analyse them, one LRCLIB request at a time."""

from django.core.management.base import BaseCommand, CommandError

from apps.songs.lyrics import LrclibClient
from apps.songs.ml import EngineUnavailable, get_engine
from apps.songs.pool import process_pending


class Command(BaseCommand):
    help = (
        "Fetch lyrics for songs that need them and analyse songs with new "
        "lyrics (worship check, theme tags, feel and embedding)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--limit", type=int, default=None, help="Handle at most this many songs."
        )

    def handle(self, *args, limit=None, verbosity=1, **options):
        report = self.stdout.write if verbosity > 1 else None
        try:
            result = process_pending(
                lyrics_client=LrclibClient(),
                engine=get_engine,
                limit=limit,
                report=report,
            )
        except EngineUnavailable as error:
            raise CommandError(str(error)) from error
        self.stdout.write(
            self.style.SUCCESS(
                f"Lyrics found for {result.lyrics_found}, not found for "
                f"{result.lyrics_missing}, lookup failed for {result.lyrics_failed}; "
                f"{result.analysed} analysed."
            )
        )
