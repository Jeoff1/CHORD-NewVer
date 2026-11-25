"""Phase 9B (decision 0014): one search worker serves every church.

Two churches queue a Search Run each, with different Suggestion Settings,
Theme Tags, Trusted Artists and Worship Check rules. One worker, holding
the one advisory lock, carries out both in a row: each run reads only its
own church's settings and songs, and the Spotify block the first run meets
(a shared ``SpotifyLimit``) also holds for the second church.
"""

from io import StringIO
from unittest import mock

from django.core.management import call_command
from django.db import connections
from django.test import TestCase, override_settings

from apps.core.locks import SEARCH_WORKER, LockHeld, advisory_lock
from apps.core.testing import (
    SPOTIFY_TEST_SETTINGS,
    FakeHttp,
    complete_setup,
    first_church,
    make_church,
    make_service,
    make_theme,
    make_user,
    quiet_logger,
)
from apps.songs import lyrics, spotify
from apps.songs.management.commands.seed_hymns import seed_hymns
from apps.songs.models import Song, SpotifyLimit, ThemeTag, TrustedArtist
from apps.songs.models import WorshipCheckSettings as CheckSettings
from apps.songs.pool import fetch_lyrics
from apps.worship import suggesting
from apps.worship.models import SearchRun, SuggestionSettings

SEARCH = f"{spotify.API}/search"
Status = SearchRun.Status
UnlistedRule = CheckSettings.UnlistedRule


def lock_is_held():
    """Whether the worker's advisory lock is held, asked from a second
    database connection, as another worker would."""
    session = connections.create_connection("default")
    try:
        with advisory_lock(SEARCH_WORKER, connection=session):
            return False
    except LockHeld:
        return True
    finally:
        session.close()


@override_settings(**SPOTIFY_TEST_SETTINGS)
class TwoChurchesOneWorkerTests(TestCase):
    def setUp(self):
        quiet_logger(self)
        self.a = complete_setup()
        self.b = make_church("Grace Chapel")
        complete_setup(self.b)

        # Church A: the usual rules; keeps 3 suggestions.
        settings_a = SuggestionSettings.load(self.a)
        settings_a.suggestions_kept = 3
        settings_a.weight_familiarity = 0.2
        settings_a.save()
        TrustedArtist.objects.create(church=self.a, name="John Newton (1779)")

        # Church B: songs by artists not on its list wait for a person; its
        # only trusted artist is another; only its own tag is switched on;
        # keeps 2 suggestions, with other weights.
        settings_b = SuggestionSettings.load(self.b)
        settings_b.suggestions_kept = 2
        settings_b.weight_familiarity = 0.9
        settings_b.save()
        check_b = CheckSettings.load(self.b)
        check_b.unlisted_rule = UnlistedRule.REVIEW
        check_b.save()
        TrustedArtist.objects.create(church=self.b, name="Reginald Heber (1826)")
        ThemeTag.objects.for_church(self.b).update(is_active=False)
        self.b_tag = ThemeTag.objects.create(
            church=self.b, name="Zebulon holiness", keywords="holy, almighty"
        )

        # Each church's own copy of the public-domain hymns.
        seed_hymns(self.a)
        seed_hymns(self.b)

        self.runs = []
        for church in (self.a, self.b):
            leader = make_user(church=church, roles=["worship_leader"])
            service = make_service(church=church)
            make_theme(
                service,
                title="Holy is the Lord",
                notes="We praise God almighty, holy and glorious.",
            )
            self.runs.append(suggesting.request_run(service, leader))

    def run_worker(self):
        held = []
        real_execute = suggesting.execute

        def watched_execute(run, **kwargs):
            held.append((run.service.church_id, lock_is_held()))
            return real_execute(run, **kwargs)

        with FakeHttp() as web:
            web.reply(
                "POST", spotify.TOKEN_URL, {"access_token": "t", "expires_in": 3600}
            )
            # Church A's search meets Spotify's quota block.
            web.reply("GET", SEARCH, {"reason": "QUOTA_EXCEEDED"}, status=429)
            web.reply("GET", f"{lyrics.API}/get", {}, status=404)
            web.reply("GET", f"{lyrics.API}/search", [])
            with mock.patch.object(suggesting, "execute", watched_execute):
                call_command("run_worker", "--once", stdout=StringIO())
        for run in self.runs:
            run.refresh_from_db()
        return web, held

    def test_each_run_uses_its_own_church_under_one_lock_and_one_block(self):
        web, held = self.run_worker()
        run_a, run_b = self.runs

        # One worker, one lock, both runs in a row, oldest first.
        self.assertEqual(held, [(self.a.pk, True), (self.b.pk, True)])
        self.assertEqual(run_a.status, Status.DONE, run_a.message)
        self.assertEqual(run_b.status, Status.DONE, run_b.message)

        # The block Church A met is shared: Church B never called Spotify.
        searches = [call for call in web.calls if call["path"] == SEARCH]
        self.assertEqual(len(searches), 1)
        self.assertEqual(SpotifyLimit.objects.get().reason, SpotifyLimit.Reason.QUOTA)
        self.assertTrue(run_a.fell_back)
        self.assertTrue(run_b.fell_back)
        self.assertEqual(run_b.spotify_calls, 0)

        # Each church's Suggestion Settings: Church A keeps 3 of its ranked
        # songs. Church B's rule holds back every hymn whose artist isn't on
        # its list, so only its trusted artist's hymn is suggested at all.
        self.assertEqual(run_a.suggestions.count(), 3)
        self.assertEqual(
            [s.song.title for s in run_b.suggestions.all()], ["Holy, Holy, Holy"]
        )
        self.assertEqual(run_a.weights["familiarity"], 0.2)
        self.assertEqual(run_b.weights["familiarity"], 0.9)

        # Each church's songs only, tagged with its own Theme Tags.
        for run, church in ((run_a, self.a), (run_b, self.b)):
            songs = Song.objects.filter(suggestions__run=run)
            self.assertFalse(songs.exclude(church=church).exists())
            own_tags = set(
                ThemeTag.objects.for_church(church).values_list("pk", flat=True)
            )
            self.assertTrue(set(run.theme_tags) <= own_tags)
            used = set(
                Song.objects.for_church(church).values_list("tags", flat=True)
            ) - {None}
            self.assertTrue(used <= own_tags)
        self.assertEqual(run_b.theme_tags, [self.b_tag.pk])

        # Each church's Worship Check rules: a hymn whose lyrics alone pass
        # (same lyrics, same score in both churches) is a worship song in
        # Church A, and waits for a person in Church B, whose rule holds back
        # artists not on its list.
        trusted = ["John Newton (1779)", "Reginald Heber (1826)"]
        passed_on_lyrics = (
            Song.objects.for_church(self.a)
            .filter(worship_model_score__gte=0.5)
            .exclude(artist__in=trusted)
        )
        self.assertTrue(passed_on_lyrics.exists())
        for song in passed_on_lyrics:
            in_b = Song.objects.get(church=self.b, title=song.title)
            self.assertEqual(in_b.worship_model_score, song.worship_model_score)
            self.assertEqual(song.worship_check, Song.WorshipCheck.ACCEPTED)
            self.assertEqual(in_b.worship_check, Song.WorshipCheck.UNCHECKED)

        # Each church's Trusted Artists: the bonus follows its own list only.
        for title, church_trusting, other in (
            ("Amazing Grace", self.a, self.b),
            ("Holy, Holy, Holy", self.b, self.a),
        ):
            trusted_copy = Song.objects.get(church=church_trusting, title=title)
            plain_copy = Song.objects.get(church=other, title=title)
            self.assertGreater(
                trusted_copy.worship_score, trusted_copy.worship_model_score
            )
            self.assertEqual(plain_copy.worship_score, plain_copy.worship_model_score)


class SharedLyricsLookupTests(TestCase):
    """Owner's answer to question 1: a track another church already looked
    up on LRCLIB reuses that answer instead of asking again."""

    def setUp(self):
        self.a = first_church()
        self.b = make_church("Grace Chapel")

    def test_a_track_another_church_looked_up_isnt_asked_again(self):
        Song.objects.create(
            church=self.a,
            spotify_id="track-1",
            title="Hymn",
            artist="Choir",
            lyrics="Holy, holy, holy",
            lyrics_status=Song.LyricsStatus.FOUND,
            lyrics_checked_at="2026-11-20T10:00:00Z",
        )
        theirs = Song.objects.create(
            church=self.b, spotify_id="track-1", title="Hymn", artist="Choir"
        )
        with FakeHttp() as web:
            fetch_lyrics(theirs, lyrics.LrclibClient("CHORD test", sleep=lambda s: 0))
        self.assertEqual(web.calls, [])
        theirs.refresh_from_db()
        self.assertEqual(theirs.lyrics, "Holy, holy, holy")
        self.assertEqual(theirs.lyrics_status, Song.LyricsStatus.FOUND)

    def test_a_new_track_is_looked_up(self):
        mine = Song.objects.create(
            church=self.b, spotify_id="track-2", title="Hymn", artist="Choir"
        )
        with FakeHttp() as web:
            web.reply("GET", f"{lyrics.API}/get", {"plainLyrics": "Words"})
            fetch_lyrics(mine, lyrics.LrclibClient("CHORD test", sleep=lambda s: 0))
        self.assertEqual(len(web.calls), 1)

    def test_a_failed_lookup_isnt_reused(self):
        Song.objects.create(
            church=self.a,
            spotify_id="track-3",
            title="Hymn",
            artist="Choir",
            lyrics_status=Song.LyricsStatus.FAILED,
            lyrics_checked_at="2026-11-20T10:00:00Z",
        )
        theirs = Song.objects.create(
            church=self.b, spotify_id="track-3", title="Hymn", artist="Choir"
        )
        with FakeHttp() as web:
            web.reply("GET", f"{lyrics.API}/get", {"plainLyrics": "Words"})
            fetch_lyrics(theirs, lyrics.LrclibClient("CHORD test", sleep=lambda s: 0))
        self.assertEqual(len(web.calls), 1)
