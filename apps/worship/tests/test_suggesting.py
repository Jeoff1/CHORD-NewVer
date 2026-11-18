"""Search Runs from a theme to placed, explained songs (pipeline stages 2
to 9), and the search worker. Spotify and LRCLIB are FakeHttp; the ML
engine is the keyword engine. Lyrics are public domain (seed_hymns)."""

import datetime
import tempfile
from io import StringIO

from django.core.management import CommandError, call_command
from django.db import connections
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.core.locks import SEARCH_WORKER, advisory_lock
from apps.core.testing import (
    FakeHttp,
    complete_setup,
    make_service,
    make_theme,
    make_user,
    quiet_logger,
)
from apps.songs import lyrics, spotify
from apps.songs.lyrics import LrclibClient
from apps.songs.management.commands.seed_hymns import HYMNS, seed_hymns
from apps.songs.ml.keyword import KeywordEngine
from apps.songs.models import Song, SpotifyLimit
from apps.songs.spotify import SpotifyClient
from apps.worship import suggesting
from apps.worship.models import SearchRun, Suggestion
from apps.worship.suggesting import RunRefused

Status = SearchRun.Status
SEARCH = f"{spotify.API}/search"
WORDS = {title: words for title, _, words in HYMNS}
SECULAR = "Driving down the highway in my car\nRadio playing low beneath the stars"

# What the fake Spotify finds for every search.
FOUND = [
    ("id-holy", "Holy, Holy, Holy", "Choir One"),
    ("id-joyful", "Joyful, Joyful, We Adore Thee", "Choir Two"),
    ("id-crown", "Crown Him with Many Crowns", "Choir One"),
    ("id-crown-live", "Crown Him with Many Crowns (Live)", "Choir One"),
    ("id-karaoke", "Holy, Holy, Holy (Karaoke Version)", "Sing Along"),
    ("id-highway", "Highway Song", "Road Band"),
]


def api_track(spotify_id, title, artist):
    return {
        "id": spotify_id,
        "name": title,
        "artists": [{"name": artist}],
        "album": {"name": "Album"},
        "duration_ms": 200_000,
    }


def lrclib_reply(call):
    title = call["params"]["track_name"]
    words = WORDS.get(title) or (SECULAR if title == "Highway Song" else None)
    return (200, {"plainLyrics": words}) if words else (404, {})


def outside_world(search_reply=None):
    """A fake Spotify and LRCLIB."""
    web = FakeHttp()
    web.reply("POST", spotify.TOKEN_URL, {"access_token": "t", "expires_in": 3600})
    web.reply(
        "GET",
        SEARCH,
        search_reply
        or {"tracks": {"items": [api_track(*found) for found in FOUND], "next": None}},
    )
    web.reply("GET", f"{lyrics.API}/get", lrclib_reply)
    web.reply("GET", f"{lyrics.API}/search", [])
    return web


class SuggestingTestCase(TestCase):
    def setUp(self):
        complete_setup()
        quiet_logger(self)
        self.leader = make_user(roles=["worship_leader"])
        self.service = make_service()
        make_theme(
            self.service,
            title="Holy is the Lord",
            notes="We praise God almighty, holy and glorious. Crown him king.",
        )

    def queue(self, use_spotify=True):
        run = suggesting.request_run(self.service, self.leader, use_spotify=use_spotify)
        return suggesting.claim_next_run() or run

    def execute(self, run):
        return suggesting.execute(
            run,
            spotify=SpotifyClient("id", "secret", sleep=lambda s: None),
            lyrics_client=LrclibClient("CHORD test", sleep=lambda s: None),
            engine=KeywordEngine(),
        )


class QueueTests(SuggestingTestCase):
    def test_a_run_needs_a_posted_theme(self):
        service = make_service()
        with self.assertRaisesMessage(RunRefused, "Post the service's theme"):
            suggesting.request_run(service, self.leader)

    def test_one_run_at_a_time_per_service(self):
        suggesting.request_run(self.service, self.leader)
        with self.assertRaisesMessage(RunRefused, "already being found"):
            suggesting.request_run(self.service, self.leader)
        other = make_theme(title="Hope").service
        suggesting.request_run(other, self.leader)  # another service may run

    def test_the_oldest_waiting_run_is_claimed_first(self):
        first = suggesting.request_run(self.service, self.leader)
        second = suggesting.request_run(make_theme().service, self.leader)
        claimed = suggesting.claim_next_run()
        self.assertEqual(claimed, first)
        self.assertEqual(claimed.status, Status.RUNNING)
        self.assertIsNotNone(claimed.started_at)
        self.assertEqual(suggesting.claim_next_run(), second)
        self.assertIsNone(suggesting.claim_next_run())

    def test_runs_left_running_by_a_stopped_worker_fail(self):
        run = self.queue()
        self.assertEqual(suggesting.fail_stale_runs(), 1)
        run.refresh_from_db()
        self.assertEqual(run.status, Status.FAILED)
        self.assertIn("worker stopped", run.message)

    def test_a_long_wait_suggests_the_worker_is_not_running(self):
        run = suggesting.request_run(self.service, self.leader)
        self.assertFalse(suggesting.worker_seems_stopped(run))
        later = timezone.now() + datetime.timedelta(minutes=3)
        self.assertTrue(suggesting.worker_seems_stopped(run, later))


class SpotifyRunTests(SuggestingTestCase):
    def test_a_run_finds_ranks_places_and_explains_songs(self):
        run = self.queue()
        with outside_world() as web:
            self.execute(run)
        run.refresh_from_db()
        self.assertEqual(run.status, Status.DONE, run.message)
        self.assertEqual(run.progress, 100)
        self.assertEqual(len(run.phrases), 4)
        self.assertEqual(run.pages_read, 4)  # four phrases, one page each
        # The live copy and the karaoke track were cleaned away.
        self.assertEqual(run.songs_found, 4)
        self.assertEqual(run.songs_added, 4)
        self.assertFalse(Song.objects.filter(spotify_id="id-karaoke").exists())
        searches = [c for c in web.calls if c["path"] == SEARCH]
        self.assertEqual(run.spotify_calls, 1 + len(searches))
        self.assertEqual(run.spotify_limits, [])
        self.assertTrue(all("genre:worship" in c["params"]["q"] for c in searches))
        self.assertIn(
            "Searched 4 phrases (4 pages): 4 songs found, 4 new.", run.message
        )

        # Only songs whose lyrics pass the worship check are ranked.
        highway = Song.objects.get(spotify_id="id-highway")
        self.assertEqual(highway.worship_check, Song.WorshipCheck.REJECTED)
        suggestions = list(run.suggestions.select_related("song", "slot"))
        self.assertTrue(suggestions)
        self.assertNotIn(highway, [s.song for s in suggestions])
        self.assertEqual(run.songs_ranked, len(suggestions))
        self.assertTrue(all(s.reasons for s in suggestions))
        placed, others = suggesting.results(run)
        self.assertEqual(len(placed), min(4, len(suggestions)))
        self.assertEqual(
            [s.slot.position for s in placed], sorted(s.slot.position for s in placed)
        )
        self.assertEqual(len(placed) + len(others), len(suggestions))

    def test_songs_already_in_the_pool_skip_the_lyrics_lookup(self):
        Song.objects.create(
            spotify_id="id-holy",
            title="Holy, Holy, Holy",
            artist="Choir One",
            lyrics=WORDS["Holy, Holy, Holy"],
            lyrics_status=Song.LyricsStatus.FOUND,
        )
        run = self.queue()
        with outside_world() as web:
            self.execute(run)
        looked_up = [
            c["params"]["track_name"] for c in web.calls if "lrclib" in c["url"]
        ]
        self.assertNotIn("Holy, Holy, Holy", looked_up)
        self.assertIn("Joyful, Joyful, We Adore Thee", looked_up)

    def test_a_spotify_error_ends_the_run_with_a_clear_message(self):
        run = self.queue()
        with outside_world() as web:
            web.reply("GET", SEARCH, {}, status=503)
            self.execute(run)
        run.refresh_from_db()
        self.assertEqual(run.status, Status.FAILED)
        self.assertEqual(run.message, "Spotify answered 503.")
        self.assertIsNotNone(run.finished_at)

    def test_without_spotify_credentials_the_run_says_so(self):
        run = self.queue()
        suggesting.execute(run, engine=KeywordEngine())  # credentials are cleared
        run.refresh_from_db()
        self.assertEqual(run.status, Status.FAILED)
        self.assertIn("SPOTIFY_CLIENT_ID", run.message)

    def test_a_429_stops_the_run_and_the_next_run_calls_no_spotify(self):
        run = self.queue()
        with outside_world() as web:
            web.reply("GET", SEARCH, {}, status=429, headers={"retry-after": "600"})
            self.execute(run)
        run.refresh_from_db()
        self.assertEqual(run.status, Status.FAILED)
        self.assertIn("Spotify asked CHORD to wait until", run.message)
        self.assertEqual(len(run.spotify_limits), 1)
        self.assertEqual(run.spotify_limits[0]["retry_after"], 600)
        self.assertEqual(run.spotify_limits[0]["reason"], "rate_limit")
        self.assertEqual(run.spotify_calls, 2)  # the token and one search

        again = self.queue()
        with outside_world() as web:
            self.execute(again)
        again.refresh_from_db()
        self.assertEqual(web.calls, [])
        self.assertEqual(again.status, Status.FAILED)
        self.assertEqual(again.spotify_calls, 0)

    def test_quota_exceeded_pauses_spotify_and_ranks_the_pool(self):
        seed_hymns()
        run = self.queue()
        with outside_world() as web:
            web.reply("GET", SEARCH, {"reason": "QUOTA_EXCEEDED"}, status=429)
            self.execute(run)
        run.refresh_from_db()
        self.assertEqual(run.status, Status.DONE, run.message)
        self.assertTrue(run.fell_back)
        self.assertIn("paused Spotify", run.message)
        self.assertIn("Ranked", run.message)
        self.assertNotIn("Searched", run.message)
        self.assertTrue(run.suggestions.exists())
        self.assertEqual(SpotifyLimit.objects.get().reason, SpotifyLimit.Reason.QUOTA)
        self.assertEqual(len([c for c in web.calls if c["path"] == SEARCH]), 1)

    def test_quota_exceeded_with_an_empty_pool_says_why(self):
        run = self.queue()
        with outside_world() as web:
            web.reply("GET", SEARCH, {"reason": "QUOTA_EXCEEDED"}, status=429)
            self.execute(run)
        run.refresh_from_db()
        self.assertEqual(run.status, Status.FAILED)
        self.assertIn("paused Spotify", run.message)
        self.assertIn("No songs could be ranked", run.message)


class PoolRunTests(SuggestingTestCase):
    def test_a_run_on_a_seeded_pool_is_ranked_and_explained_without_spotify(self):
        # The Phase 5 "done when": no outside service at all.
        seed_hymns()
        run = self.queue(use_spotify=False)
        with FakeHttp() as web:
            self.execute(run)
        run.refresh_from_db()
        self.assertEqual(web.calls, [])
        self.assertEqual(run.status, Status.DONE, run.message)
        self.assertEqual(run.songs_analysed, len(HYMNS))
        self.assertEqual(
            run.message, f"Ranked {run.songs_ranked} worship songs from the pool."
        )
        placed, _ = suggesting.results(run)
        self.assertEqual(len(placed), 4)
        for suggestion in placed:
            self.assertTrue(suggestion.reasons[0].startswith("Its lyrics match"))

    def test_an_empty_pool_fails_with_a_hint(self):
        run = self.queue(use_spotify=False)
        self.execute(run)
        run.refresh_from_db()
        self.assertEqual(run.status, Status.FAILED)
        self.assertIn("Try searching Spotify.", run.message)

    def test_a_removed_theme_fails_the_run(self):
        run = self.queue(use_spotify=False)
        self.service.theme.delete()
        run.service.refresh_from_db()
        self.execute(SearchRun.objects.get(pk=run.pk))
        run.refresh_from_db()
        self.assertEqual(run.status, Status.FAILED)
        self.assertIn("theme was removed", run.message)

    @override_settings(ML_ENGINE="onnx")
    def test_missing_models_fail_the_run(self):
        with tempfile.TemporaryDirectory() as empty:
            with override_settings(ML_MODELS_DIR=empty):
                run = self.queue(use_spotify=False)
                suggesting.execute(run)
        run.refresh_from_db()
        self.assertEqual(run.status, Status.FAILED)
        self.assertIn("download_models", run.message)

    def test_an_unexpected_error_fails_the_run_and_is_logged(self):
        quiet_logger(self, "apps.worship.suggesting")

        class Broken(KeywordEngine):
            def embed(self, texts):
                raise RuntimeError("boom")

        run = self.queue(use_spotify=False)
        suggesting.execute(run, engine=Broken())
        run.refresh_from_db()
        self.assertEqual(run.status, Status.FAILED)
        self.assertIn("search worker's log", run.message)

    def test_theme_tags_are_found_from_the_theme(self):
        tags = suggesting.theme_tag_ids(
            "Grace and favor, undeserved kindness", KeywordEngine()
        )
        self.assertTrue(tags)

    def test_results_keep_slot_order(self):
        seed_hymns()
        run = self.queue(use_spotify=False)
        self.execute(run)
        placed, others = suggesting.results(run)
        self.assertEqual(
            [s.slot.name for s in placed], ["Opening", "Praise", "Worship", "Response"]
        )
        self.assertTrue(all(s.slot_id is None for s in others))
        self.assertEqual(
            Suggestion.objects.filter(run=run).count(), len(placed) + len(others)
        )


class WorkerTests(SuggestingTestCase):
    def test_the_worker_carries_out_a_queued_run(self):
        seed_hymns()
        run = suggesting.request_run(self.service, self.leader, use_spotify=False)
        out = StringIO()
        call_command("run_worker", "--once", stdout=out)
        run.refresh_from_db()
        self.assertEqual(run.status, Status.DONE, run.message)
        self.assertIn("Finding songs for", out.getvalue())

    def test_the_worker_fails_runs_a_stopped_worker_left_running(self):
        run = self.queue()
        out = StringIO()
        call_command("run_worker", "--once", stdout=out)
        run.refresh_from_db()
        self.assertEqual(run.status, Status.FAILED)
        self.assertIn("Marked 1 interrupted run(s) as failed.", out.getvalue())

    def test_a_second_worker_refuses_to_start(self):
        session = connections.create_connection("default")
        try:
            with advisory_lock(SEARCH_WORKER, connection=session):
                with self.assertRaisesMessage(CommandError, "Only one may run"):
                    call_command("run_worker", "--once", stdout=StringIO())
        finally:
            session.close()
        # Released: a worker starts again.
        call_command("run_worker", "--once", stdout=StringIO())

    def test_the_worker_works_through_the_song_backlog_between_runs(self):
        seed_hymns()
        out = StringIO()
        call_command("run_worker", "--once", stdout=out)
        self.assertFalse(Song.objects.filter(analysed_at=None).exists())
        self.assertIn("analysed", out.getvalue())
