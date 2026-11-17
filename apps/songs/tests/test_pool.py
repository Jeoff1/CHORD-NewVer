"""Adding songs, fetching lyrics and processing the pool."""

import io
from unittest import mock

from django.core.management import CommandError, call_command
from django.test import TestCase
from django.utils import timezone

from apps.core.testing import FakeHttp, make_song
from apps.songs import lyrics, pool
from apps.songs.lyrics import LrclibClient, LyricsResult
from apps.songs.ml import EngineUnavailable
from apps.songs.models import Song
from apps.songs.spotify import Track

GET = f"{lyrics.API}/get"
FIND = f"{lyrics.API}/search"
# Public domain (Holy, Holy, Holy, 1826).
HYMN = "Holy, holy, holy, Lord God Almighty\nEarly in the morning our song shall rise"


def lrclib():
    return LrclibClient("CHORD test", delay=0, sleep=lambda seconds: None)


class StubLyrics:
    def __init__(self, result=None, error=None):
        self.result, self.error, self.calls = result, error, []

    def lookup(self, *args):
        self.calls.append(args)
        if self.error:
            raise self.error
        return self.result


class AddFromSpotifyTests(TestCase):
    def test_adds_a_new_track_once(self):
        track = Track("abc", "Morning Song", ("Band", "Guest"), "Album", 200_400)
        song, created = pool.add_from_spotify(track)
        self.assertTrue(created)
        self.assertEqual(song.artist, "Band, Guest")
        self.assertEqual(song.length_seconds, 200)
        self.assertEqual(song.lyrics_status, Song.LyricsStatus.PENDING)
        again, created = pool.add_from_spotify(track)
        self.assertFalse(created)
        self.assertEqual(again.pk, song.pk)

    def test_spotify_id_is_unique_but_may_be_blank(self):
        make_song(spotify_id="")
        make_song(spotify_id="")
        self.assertEqual(Song.objects.filter(spotify_id="").count(), 2)


class FetchLyricsTests(TestCase):
    def test_saves_found_lyrics_and_asks_for_analysis(self):
        song = make_song(
            title="Holy",
            artist="Choir, Guest",
            album="Hymns",
            length_seconds=180,
            analysed_at=timezone.now(),
        )
        client = StubLyrics(LyricsResult(Song.LyricsStatus.FOUND, HYMN))
        pool.fetch_lyrics(song, client)
        song.refresh_from_db()
        self.assertEqual(client.calls, [("Holy", "Choir", "Hymns", 180)])
        self.assertEqual(song.lyrics, HYMN)
        self.assertEqual(song.lyrics_status, Song.LyricsStatus.FOUND)
        self.assertIsNotNone(song.lyrics_checked_at)
        self.assertIsNone(song.analysed_at)

    def test_unchanged_lyrics_keep_the_analysis(self):
        analysed = timezone.now()
        song = make_song(lyrics=HYMN, analysed_at=analysed)
        pool.fetch_lyrics(song, StubLyrics(LyricsResult(Song.LyricsStatus.FOUND, HYMN)))
        song.refresh_from_db()
        self.assertEqual(song.analysed_at, analysed)

    def test_failed_lookup_keeps_old_lyrics(self):
        song = make_song(lyrics=HYMN)
        pool.fetch_lyrics(song, StubLyrics(error=lyrics.LyricsError("down")))
        song.refresh_from_db()
        self.assertEqual(song.lyrics_status, Song.LyricsStatus.FAILED)
        self.assertEqual(song.lyrics, HYMN)

    def test_check_again(self):
        song = make_song(
            lyrics_status=Song.LyricsStatus.MISSING, analysed_at=timezone.now()
        )
        pool.check_again(song)
        song.refresh_from_db()
        self.assertEqual(song.lyrics_status, Song.LyricsStatus.PENDING)
        self.assertIsNone(song.analysed_at)


class ProcessPendingTests(TestCase):
    def test_fetches_then_analyses_one_request_at_a_time(self):
        found = make_song(title="Holy")
        missing = make_song(title="Unknown")
        make_song(title="Done", lyrics_status=Song.LyricsStatus.MISSING)

        def get(call):
            if call["params"]["track_name"] == "Holy":
                return 200, {"plainLyrics": HYMN}
            return 404, {"name": "TrackNotFound"}

        reports = []
        with FakeHttp() as web:
            web.reply("GET", GET, get)
            web.reply("GET", FIND, [])
            result = pool.process_pending(
                lyrics_client=lrclib(), engine=None, report=reports.append
            )
        self.assertEqual(web.paths(), [GET, GET, FIND])
        self.assertEqual(
            (result.lyrics_found, result.lyrics_missing, result.analysed), (1, 1, 1)
        )
        found.refresh_from_db()
        missing.refresh_from_db()
        self.assertEqual(found.worship_check, Song.WorshipCheck.ACCEPTED)
        self.assertEqual(missing.lyrics_status, Song.LyricsStatus.MISSING)
        self.assertEqual(missing.worship_check, Song.WorshipCheck.UNCHECKED)
        self.assertIn("Analysed: Holy (Test Artist) - Worship song", reports)
        # Lyrics are copyrighted: they never appear in a report.
        self.assertNotIn("Almighty", " ".join(reports))

    def test_engine_loads_only_when_something_needs_analysis(self):
        loads = []
        result = pool.process_pending(
            lyrics_client=lrclib(), engine=lambda: loads.append(1)
        )
        self.assertEqual(loads, [])
        self.assertEqual(result.analysed, 0)

    def test_limit(self):
        for _ in range(3):
            make_song()
        client = StubLyrics(LyricsResult(Song.LyricsStatus.MISSING))
        result = pool.process_pending(lyrics_client=client, limit=2)
        self.assertEqual(len(client.calls), 2)
        self.assertEqual(result.lyrics_missing, 2)

    def test_counts_failed_lookups(self):
        make_song()
        client = StubLyrics(error=lyrics.LyricsError("down"))
        self.assertEqual(pool.process_pending(lyrics_client=client).lyrics_failed, 1)


class ProcessSongsCommandTests(TestCase):
    def test_reports_what_it_did(self):
        make_song(lyrics=HYMN, lyrics_status=Song.LyricsStatus.FOUND)
        out = io.StringIO()
        call_command("process_songs", "--limit", "5", "-v", "2", stdout=out)
        self.assertIn("Analysed:", out.getvalue())
        self.assertIn("1 analysed.", out.getvalue())

    def test_missing_models_stop_it_with_the_reason(self):
        make_song(lyrics=HYMN, lyrics_status=Song.LyricsStatus.FOUND)

        def unavailable():
            raise EngineUnavailable("Run download_models.")

        with mock.patch(
            "apps.songs.management.commands.process_songs.get_engine", unavailable
        ):
            with self.assertRaisesMessage(CommandError, "Run download_models."):
                call_command("process_songs", stdout=io.StringIO())
