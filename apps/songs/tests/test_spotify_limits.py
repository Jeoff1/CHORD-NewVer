"""The Spotify safeguards (Design-Decisions, Phase 5), with Spotify mocked.

A fake clock stands in for time: waiting moves it forward, so no test
really waits. Only the search worker waits out a Retry-After; web requests
fail fast (workflow review F10).
"""

import datetime
import logging
from unittest import mock

from django.test import TestCase, override_settings
from django.urls import reverse

from apps.core.testing import FakeHttp, complete_setup, make_user, quiet_logger
from apps.songs import spotify
from apps.songs.models import SpotifyLimit
from apps.songs.spotify import (
    SpotifyClient,
    SpotifyPaused,
    SpotifyRateLimited,
    current_block,
)

SEARCH = f"{spotify.API}/search"
START = datetime.datetime(2026, 11, 22, 1, 0, tzinfo=datetime.UTC)
EMPTY = {"tracks": {"items": [], "next": None}}
Reason = SpotifyLimit.Reason


class Clock:
    def __init__(self):
        self.now = START
        self.waits = []

    def __call__(self):
        return self.now

    def sleep(self, seconds):
        self.waits.append(seconds)
        self.now += datetime.timedelta(seconds=seconds)

    def advance(self, seconds):
        self.now += datetime.timedelta(seconds=seconds)


def spotify_web():
    web = FakeHttp()
    web.reply("POST", spotify.TOKEN_URL, {"access_token": "t", "expires_in": 3600})
    return web


def searches(web):
    return [call for call in web.calls if call["path"] == SEARCH]


def block(seconds, reason=Reason.RATE_LIMIT, at=START):
    return SpotifyLimit.objects.create(
        occurred_at=at,
        reason=reason,
        retry_after=seconds,
        blocked_until=at + datetime.timedelta(seconds=seconds),
    )


class SafeguardTests(TestCase):
    def setUp(self):
        self.clock = Clock()
        quiet_logger(self)  # test_every_429_is_logged... checks the log

    def new_client(self, *, may_wait=False):
        """A new client: another request or process, sharing the database.
        Web requests never wait; the search worker passes ``may_wait``."""
        return SpotifyClient(
            "id", "secret", may_wait=may_wait, sleep=self.clock.sleep, clock=self.clock
        )

    def worker_client(self):
        return self.new_client(may_wait=True)

    # Rule 1: stop on the first 429.

    def test_a_429_stops_and_nothing_calls_spotify_before_retry_after(self):
        with spotify_web() as web:
            web.reply("GET", SEARCH, {}, status=429, headers={"retry-after": "120"})
            spotify_client = self.new_client()
            with self.assertRaises(SpotifyRateLimited) as raised:
                spotify_client.search_tracks("grace")
            self.assertNotIsInstance(raised.exception, SpotifyPaused)
            sent = len(web.calls)
            self.clock.advance(119)
            with self.assertRaises(SpotifyRateLimited):
                spotify_client.search_tracks("hope")
            self.assertEqual(len(web.calls), sent)
        self.assertEqual(len(searches(web)), 1)
        self.assertEqual(self.clock.waits, [])
        limit = SpotifyLimit.objects.get()
        self.assertEqual(limit.reason, Reason.RATE_LIMIT)
        self.assertEqual(limit.retry_after, 120)
        self.assertEqual(limit.blocked_until, START + datetime.timedelta(seconds=120))
        self.assertIn("asked CHORD to wait until", str(raised.exception))

    # Rule 2: the wait is shared by every process.

    def test_the_block_holds_for_another_process_or_request(self):
        block(60)
        with spotify_web() as web:
            with self.assertRaises(SpotifyRateLimited):
                self.new_client().search_tracks("grace")
            with self.assertRaises(SpotifyRateLimited):
                self.new_client().get_track("id1")
        self.assertEqual(web.calls, [])

    def test_calls_resume_once_retry_after_has_passed(self):
        block(60)
        self.clock.advance(60)
        with spotify_web() as web:
            web.reply("GET", SEARCH, EMPTY)
            self.new_client().search_tracks("grace")
        self.assertEqual(len(searches(web)), 1)

    def test_the_longest_block_wins(self):
        block(30)
        long = block(600, Reason.LONG_WAIT)
        self.assertEqual(current_block(START), long)
        self.assertIsNone(current_block(START + datetime.timedelta(seconds=600)))

    # Rule 3: after waiting, retry at most once (the search worker only).

    def test_a_short_wait_is_waited_out_and_the_request_retried(self):
        answers = iter([(429, {}), (200, EMPTY)])
        with spotify_web() as web:
            web.reply(
                "GET", SEARCH, lambda call: next(answers), headers={"retry-after": "3"}
            )
            self.worker_client().search_tracks("grace")
        self.assertEqual(self.clock.waits, [3])
        self.assertEqual(len(searches(web)), 2)
        self.assertEqual(SpotifyLimit.objects.count(), 1)

    def test_a_request_is_retried_at_most_once(self):
        with spotify_web() as web:
            web.reply("GET", SEARCH, {}, status=429, headers={"retry-after": "2"})
            with self.assertRaises(SpotifyRateLimited):
                self.worker_client().search_tracks("grace")
        self.assertEqual(self.clock.waits, [2])
        self.assertEqual(len(searches(web)), 2)
        self.assertEqual(SpotifyLimit.objects.count(), 2)

    def test_a_wait_too_long_to_wait_out_stops_without_retrying(self):
        wait = spotify.MAX_WAIT_SECONDS + 1
        with spotify_web() as web:
            web.reply("GET", SEARCH, {}, status=429, headers={"retry-after": str(wait)})
            with self.assertRaises(SpotifyRateLimited):
                self.worker_client().search_tracks("grace")
        self.assertEqual(self.clock.waits, [])
        self.assertEqual(len(searches(web)), 1)

    def test_a_429_without_retry_after_stops_for_a_few_seconds(self):
        with spotify_web() as web:
            web.reply("GET", SEARCH, {}, status=429)
            with self.assertRaises(SpotifyRateLimited):
                self.new_client().search_tracks("grace")
        limit = SpotifyLimit.objects.get()
        self.assertIsNone(limit.retry_after)
        self.assertEqual(
            limit.blocked_until,
            START + datetime.timedelta(seconds=spotify.DEFAULT_RETRY_AFTER),
        )

    # Rule 4: a Retry-After over an hour is a quota lockout.

    def test_a_retry_after_over_an_hour_pauses_spotify(self):
        with spotify_web() as web:
            web.reply("GET", SEARCH, {}, status=429, headers={"retry-after": "7200"})
            with self.assertRaises(SpotifyPaused) as raised:
                self.new_client().search_tracks("grace")
        limit = SpotifyLimit.objects.get()
        self.assertEqual(limit.reason, Reason.LONG_WAIT)
        self.assertTrue(limit.is_pause)
        self.assertEqual(limit.blocked_until, START + datetime.timedelta(hours=2))
        self.assertEqual(self.clock.waits, [])
        self.assertIn("paused", str(raised.exception))

    # Rule 5: QUOTA_EXCEEDED pauses every Spotify call.

    def test_quota_exceeded_pauses_spotify(self):
        with spotify_web() as web:
            web.reply("GET", SEARCH, {"reason": "QUOTA_EXCEEDED"}, status=429)
            with self.assertRaises(SpotifyPaused) as raised:
                self.new_client().search_tracks("grace")
            self.clock.advance(3600)
            with self.assertRaises(SpotifyPaused):
                self.new_client().search_tracks("hope")
        self.assertEqual(len(searches(web)), 1)
        limit = SpotifyLimit.objects.get()
        self.assertEqual(limit.reason, Reason.QUOTA)
        self.assertEqual(limit.blocked_until, START + spotify.QUOTA_PAUSE)
        self.assertIn("limit for this app was reached", str(raised.exception))
        self.assertIn("songs already in the pool", str(raised.exception))

    def test_quota_pause_follows_retry_after_when_given(self):
        body = {"error": {"status": 429, "reason": "QUOTA_EXCEEDED"}}
        with spotify_web() as web:
            web.reply("GET", SEARCH, body, status=429, headers={"retry-after": "60"})
            with self.assertRaises(SpotifyPaused):
                self.new_client().search_tracks("grace")
        limit = SpotifyLimit.objects.get()
        self.assertEqual(limit.reason, Reason.QUOTA)
        self.assertEqual(limit.blocked_until, START + datetime.timedelta(seconds=60))

    # Rule 9: usage is counted.

    def test_calls_and_limits_are_counted(self):
        answers = iter([(429, {}), (200, EMPTY)])
        spotify_client = self.worker_client()
        with spotify_web() as web:
            web.reply(
                "GET", SEARCH, lambda call: next(answers), headers={"retry-after": "1"}
            )
            spotify_client.search_tracks("grace")
        self.assertEqual(spotify_client.calls, 3)  # the token and two searches
        self.assertEqual(len(spotify_client.limits), 1)
        self.assertEqual(spotify_client.limits[0].retry_after, 1)

    def test_every_429_is_logged_with_its_reason_and_retry_after(self):
        logging.getLogger("apps.songs.spotify").disabled = False
        with spotify_web() as web:
            web.reply("GET", SEARCH, {}, status=429, headers={"retry-after": "45"})
            with self.assertLogs("apps.songs.spotify", "WARNING") as logs:
                with self.assertRaises(SpotifyRateLimited):
                    self.new_client().search_tracks("grace")
        self.assertIn("429 (Rate limit), Retry-After 45 s", logs.output[0])

    def test_the_token_request_is_safeguarded_too(self):
        with FakeHttp() as web:
            web.reply(
                "POST", spotify.TOKEN_URL, {}, status=429, headers={"retry-after": "90"}
            )
            with self.assertRaises(SpotifyRateLimited):
                self.new_client().search_tracks("grace")
        self.assertEqual(len(web.calls), 1)
        self.assertEqual(SpotifyLimit.objects.get().retry_after, 90)


class WebRequestFailFastTests(TestCase):
    """No web request waits on a Spotify Retry-After (workflow review F10)."""

    def setUp(self):
        quiet_logger(self)
        complete_setup()
        # Any real sleep in this class is a failure.
        patcher = mock.patch(
            "apps.songs.spotify.time.sleep",
            side_effect=AssertionError("A web request waited on Spotify."),
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_a_web_client_sends_one_request_never_sleeps_and_records_the_block(self):
        clock = Clock()
        with spotify_web() as web:
            web.reply("GET", SEARCH, {}, status=429, headers={"retry-after": "3"})
            with self.assertRaises(SpotifyRateLimited):
                SpotifyClient("id", "secret", clock=clock).search_tracks("grace")
        self.assertEqual(len(searches(web)), 1)
        self.assertEqual(clock.waits, [])
        self.assertEqual(SpotifyLimit.objects.get().retry_after, 3)

    @override_settings(SPOTIFY_CLIENT_ID="id", SPOTIFY_CLIENT_SECRET="secret")
    def test_find_on_spotify_fails_fast_on_a_429(self):
        self.client.force_login(make_user(perms=["songs.view_song", "songs.add_song"]))
        with spotify_web() as web:
            web.reply("GET", SEARCH, {}, status=429, headers={"retry-after": "3"})
            response = self.client.get(reverse("songs:spotify_search"), {"q": "grace"})
        self.assertEqual(len(searches(web)), 1)
        self.assertContains(response, "Spotify asked CHORD to wait until")
        self.assertIsNotNone(current_block())

    def test_the_worker_still_waits_out_one_short_retry_after(self):
        clock = Clock()
        answers = iter([(429, {}), (200, EMPTY)])
        with spotify_web() as web:
            web.reply(
                "GET", SEARCH, lambda call: next(answers), headers={"retry-after": "2"}
            )
            SpotifyClient(
                "id", "secret", may_wait=True, sleep=clock.sleep, clock=clock
            ).search_tracks("grace")
        self.assertEqual(clock.waits, [2])
        self.assertEqual(len(searches(web)), 2)
