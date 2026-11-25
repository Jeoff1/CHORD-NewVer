"""The song pool's commands: seeding public-domain hymns, and
``process_songs`` respecting the search worker's lock."""

from io import StringIO

from django.core.management import CommandError, call_command
from django.db import connections
from django.test import TestCase

from apps.core.locks import SEARCH_WORKER, LockHeld, advisory_lock
from apps.core.testing import first_church
from apps.songs.management.commands.seed_hymns import HYMNS
from apps.songs.models import Song


def other_session():
    """A second database connection: another process, as PostgreSQL sees it."""
    connection = connections.create_connection("default")
    return connection


class SeedHymnsTests(TestCase):
    def test_seeds_each_hymn_once_with_its_lyrics_found(self):
        out = StringIO()
        call_command("seed_hymns", church=first_church().slug, stdout=out)
        call_command("seed_hymns", church=first_church().slug, stdout=out)
        hymns = Song.objects.filter(spotify_id="")
        self.assertEqual(hymns.count(), len(HYMNS))
        self.assertIn(f"Added {len(HYMNS)} of {len(HYMNS)}", out.getvalue())
        self.assertIn(f"Added 0 of {len(HYMNS)}", out.getvalue())
        amazing = hymns.get(title="Amazing Grace")
        self.assertEqual(amazing.lyrics_status, Song.LyricsStatus.FOUND)
        self.assertIn("how sweet the sound", amazing.lyrics)
        self.assertIsNone(amazing.analysed_at)

    def test_seeded_hymns_are_analysed_like_any_song(self):
        call_command("seed_hymns", church=first_church().slug, stdout=StringIO())
        call_command("process_songs", stdout=StringIO())
        hymns = Song.objects.filter(spotify_id="")
        self.assertFalse(hymns.filter(analysed_at=None).exists())
        self.assertTrue(hymns.filter(worship_check=Song.WorshipCheck.ACCEPTED).exists())


class WorkerLockTests(TestCase):
    def test_process_songs_refuses_while_the_worker_runs(self):
        session = other_session()
        try:
            with advisory_lock(SEARCH_WORKER, connection=session):
                with self.assertRaisesMessage(CommandError, "search worker is running"):
                    call_command("process_songs", stdout=StringIO())
        finally:
            session.close()

    def test_the_lock_is_one_session_at_a_time(self):
        session = other_session()
        try:
            with advisory_lock(SEARCH_WORKER):
                with self.assertRaises(LockHeld):
                    with advisory_lock(SEARCH_WORKER, connection=session):
                        pass  # pragma: no cover
            with advisory_lock(SEARCH_WORKER, connection=session):
                pass  # free again once released
        finally:
            session.close()
