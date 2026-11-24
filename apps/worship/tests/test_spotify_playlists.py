"""Saving a confirmed lineup as a Spotify playlist, "Save to Spotify", and
playback on the lineup song page (Design-Decisions, Phase 7). Spotify is
faked; tokens are made up. Saving never stops a confirmation, and no web
request waits on Spotify (workflow review F10)."""

import datetime
import json
from unittest import mock

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.core.testing import (
    SPOTIFY_TEST_SETTINGS,
    FakeHttp,
    complete_setup,
    make_lineup,
    make_service,
    make_song,
    make_spotify_connection,
    make_user,
    quiet_logger,
)
from apps.songs import spotify
from apps.songs.models import SpotifyLimit
from apps.worship import lineups, playlists
from apps.worship.models import Lineup

CREATE = f"{spotify.API}/me/playlists"
ITEMS = f"{spotify.API}/playlists/"


def spotify_calls(web):
    return [call for call in web.calls if call["path"].startswith(spotify.API)]


def playlist_web(playlist_id="pl1"):
    web = FakeHttp()
    web.reply("POST", CREATE, {"id": playlist_id}, status=201)
    web.reply("PUT", ITEMS, {"snapshot_id": "s1"})
    return web


@override_settings(**SPOTIFY_TEST_SETTINGS)
class PlaylistTestCase(TestCase):
    def setUp(self):
        complete_setup()
        quiet_logger(self)
        # A web request that sleeps fails the test (F10).
        patcher = mock.patch(
            "apps.songs.spotify.time.sleep",
            side_effect=AssertionError("A web request waited on Spotify."),
        )
        patcher.start()
        self.addCleanup(patcher.stop)
        self.leader = make_user(roles=["worship_leader"])
        self.pastor = make_user(roles=["pastoral_staff"])
        self.member = make_user(roles=["team_member"])
        self.service = make_service()
        self.first = make_song(title="First Song", spotify_id="trackAAAAAAAAAAAAAAAAA")
        self.second = make_song(
            title="Second Song", spotify_id="trackBBBBBBBBBBBBBBBBB"
        )
        self.lineup = make_lineup(
            self.service, [self.first, self.second], confirmed=False
        )
        self.lineup_url = reverse(
            "worship:lineup", kwargs={"public_id": self.service.public_id}
        )

    def confirm(self, user):
        self.client.force_login(user)
        return self.client.post(
            reverse(
                "worship:lineup_confirm", kwargs={"public_id": self.service.public_id}
            ),
            follow=True,
        )

    def save_to_spotify(self, user):
        self.client.force_login(user)
        return self.client.post(
            reverse(
                "worship:lineup_save_playlist",
                kwargs={"public_id": self.service.public_id},
            ),
            follow=True,
        )

    def fresh(self):
        return Lineup.objects.get(pk=self.lineup.pk)


class ConfirmSavesThePlaylistTests(PlaylistTestCase):
    def test_confirming_saves_the_playlist_for_a_connected_leader(self):
        make_spotify_connection(self.leader, access="leader-access")
        with playlist_web() as web:
            page = self.confirm(self.leader)
        lineup = self.fresh()
        self.assertTrue(lineup.is_confirmed)
        create, items = spotify_calls(web)
        self.assertEqual(create["headers"]["Authorization"], "Bearer leader-access")
        body = json.loads(create["body"])
        self.assertFalse(body["public"])
        self.assertTrue(body["name"].startswith(self.service.name))
        self.assertEqual(items["path"], f"{spotify.API}/playlists/pl1/items")
        self.assertEqual(
            json.loads(items["body"])["uris"],
            [
                "spotify:track:trackAAAAAAAAAAAAAAAAA",
                "spotify:track:trackBBBBBBBBBBBBBBBBB",
            ],
        )
        self.assertEqual(lineup.spotify_playlist_id, "pl1")
        self.assertEqual(lineup.spotify_playlist_owner, self.leader)
        self.assertEqual(
            lineup.spotify_playlist_tracks,
            ["trackAAAAAAAAAAAAAAAAA", "trackBBBBBBBBBBBBBBBBB"],
        )
        self.assertContains(page, "Saved to your Spotify")
        self.assertContains(page, "https://open.spotify.com/playlist/pl1")
        self.assertNotContains(page, ">Save to Spotify<")

    def test_the_pastors_confirmation_saves_to_the_pastors_account(self):
        make_spotify_connection(self.pastor, access="pastor-access")
        make_spotify_connection(self.leader, access="leader-access")
        with playlist_web() as web:
            self.confirm(self.pastor)
        self.assertEqual(
            spotify_calls(web)[0]["headers"]["Authorization"], "Bearer pastor-access"
        )
        self.assertEqual(self.fresh().spotify_playlist_owner, self.pastor)

    def test_without_a_connection_the_lineup_is_confirmed_and_save_to_spotify_shows(
        self,
    ):
        with FakeHttp() as web:
            page = self.confirm(self.leader)
        self.assertTrue(self.fresh().is_confirmed)
        self.assertEqual(web.calls, [])
        self.assertContains(page, "Confirmed: the team can see it now.")
        self.assertContains(page, "Save to Spotify")
        self.assertContains(page, "Connect your Spotify account first.")
        self.assertEqual(self.fresh().spotify_playlist_id, "")

    def test_on_a_429_the_lineup_is_confirmed_without_waiting_and_save_to_spotify_shows(
        self,
    ):
        make_spotify_connection(self.leader)
        with FakeHttp() as web:
            web.reply("POST", CREATE, {}, status=429, headers={"retry-after": "20"})
            page = self.confirm(self.leader)
        lineup = self.fresh()
        self.assertTrue(lineup.is_confirmed)
        self.assertEqual(len(spotify_calls(web)), 1)  # one request, no retry
        self.assertEqual(SpotifyLimit.objects.get().retry_after, 20)  # the block
        self.assertEqual(lineup.spotify_playlist_id, "")
        self.assertContains(page, "The Spotify playlist wasn&#x27;t saved")
        self.assertContains(page, ">Save to Spotify</button>")

    def test_during_a_spotify_block_confirming_sends_nothing_and_offers_the_button(
        self,
    ):
        make_spotify_connection(self.leader)
        now = timezone.now()
        SpotifyLimit.objects.create(
            occurred_at=now,
            reason=SpotifyLimit.Reason.QUOTA,
            blocked_until=now + datetime.timedelta(hours=24),
        )
        with FakeHttp() as web:
            page = self.confirm(self.leader)
        self.assertTrue(self.fresh().is_confirmed)
        self.assertEqual(web.calls, [])
        self.assertContains(page, ">Save to Spotify</button>")

    def test_a_429_after_the_playlist_was_made_keeps_it_for_the_next_try(self):
        make_spotify_connection(self.leader)
        with FakeHttp() as web:
            web.reply("POST", CREATE, {"id": "pl1"}, status=201)
            web.reply("PUT", ITEMS, {}, status=429, headers={"retry-after": "5"})
            self.confirm(self.leader)
        lineup = self.fresh()
        self.assertEqual(
            (lineup.spotify_playlist_id, lineup.spotify_playlist_tracks), ("pl1", [])
        )
        SpotifyLimit.objects.all().delete()
        with playlist_web() as web:
            self.save_to_spotify(self.leader)
        # The same playlist is filled; no second one is made.
        self.assertEqual([call["method"] for call in spotify_calls(web)], ["PUT"])
        self.assertEqual(len(self.fresh().spotify_playlist_tracks), 2)

    def test_songs_not_on_spotify_are_left_out(self):
        not_on_spotify = make_song(title="Public Domain Hymn", spotify_id="")
        lineups.add_from_pool(self.lineup, not_on_spotify, None, self.leader)
        make_spotify_connection(self.leader)
        with playlist_web() as web:
            page = self.confirm(self.leader)
        self.assertEqual(len(json.loads(spotify_calls(web)[1]["body"])["uris"]), 2)
        self.assertContains(page, "1 song not on Spotify was left out.")

    @override_settings(SPOTIFY_CLIENT_ID="", SPOTIFY_TOKEN_KEY="")
    def test_without_spotify_set_up_nothing_is_offered(self):
        with FakeHttp() as web:
            page = self.confirm(self.leader)
        self.assertTrue(self.fresh().is_confirmed)
        self.assertEqual(web.calls, [])
        self.assertNotContains(page, "Save to Spotify")


class SaveToSpotifyTests(PlaylistTestCase):
    def setUp(self):
        super().setUp()
        self.lineup.status = Lineup.Status.CONFIRMED
        self.lineup.save()

    def test_save_to_spotify_saves_on_the_pressing_persons_account(self):
        make_spotify_connection(self.leader)
        with playlist_web() as web:
            page = self.save_to_spotify(self.leader)
        self.assertEqual(len(spotify_calls(web)), 2)
        self.assertEqual(self.fresh().spotify_playlist_id, "pl1")
        self.assertContains(page, "Saved to your Spotify")

    def test_saving_again_after_a_change_updates_the_same_playlist(self):
        make_spotify_connection(self.leader)
        with playlist_web():
            self.save_to_spotify(self.leader)
        third = make_song(title="Third Song", spotify_id="trackCCCCCCCCCCCCCCCCC")
        lineups.add_from_pool(self.fresh(), third, None, self.leader)
        page = self.client.get(self.lineup_url)
        self.assertContains(page, "the songs have changed since")
        self.assertContains(page, ">Save to Spotify</button>")
        with playlist_web() as web:
            self.save_to_spotify(self.leader)
        put = spotify_calls(web)
        self.assertEqual([call["method"] for call in put], ["PUT"])
        self.assertEqual(len(json.loads(put[0]["body"])["uris"]), 3)

    def test_someone_else_saving_gets_their_own_playlist(self):
        make_spotify_connection(self.leader)
        make_spotify_connection(self.pastor)
        with playlist_web("pl-leader"):
            self.save_to_spotify(self.leader)
        page = self.client.get(self.lineup_url)
        self.client.force_login(self.pastor)
        page = self.client.get(self.lineup_url)
        self.assertContains(page, "Saved to the Spotify account of")
        self.assertNotContains(page, "pl-leader")  # a private playlist: no link

    def test_without_a_connection_save_to_spotify_leads_to_connecting(self):
        response = self.save_to_spotify(self.leader)
        self.assertContains(response, "Connect Spotify")

    def test_a_team_member_may_not_save_or_see_the_button(self):
        make_spotify_connection(self.member)
        self.client.force_login(self.member)
        self.assertNotContains(self.client.get(self.lineup_url), "Save to Spotify")
        with FakeHttp() as web:
            response = self.client.post(
                reverse(
                    "worship:lineup_save_playlist",
                    kwargs={"public_id": self.service.public_id},
                )
            )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(web.calls, [])

    def test_a_draft_isnt_saved(self):
        self.lineup.status = Lineup.Status.DRAFT
        self.lineup.save()
        make_spotify_connection(self.leader)
        with FakeHttp() as web:
            page = self.save_to_spotify(self.leader)
        self.assertEqual(web.calls, [])
        self.assertContains(page, "before saving it to Spotify")

    def test_save_never_raises_for_spotify(self):
        make_spotify_connection(self.leader)
        with FakeHttp() as web:
            web.reply(
                "POST", CREATE, {"error": {"message": "Server error"}}, status=500
            )
            outcome = playlists.save(self.fresh(), self.leader)
        self.assertFalse(outcome.saved)
        self.assertIn("Spotify answered 500", outcome.message)


@override_settings(**SPOTIFY_TEST_SETTINGS)
class PlaybackTests(TestCase):
    """The page chooses the Web Playback SDK only for a connected account;
    otherwise Spotify's embedded player shows at once. With the SDK, the
    embedded player is on the page, hidden, for player.js to fall back to."""

    def setUp(self):
        complete_setup()
        self.member = make_user(roles=["team_member"])
        self.song = make_song(title="Made Up Song", spotify_id="trackDDDDDDDDDDDDDDDDD")
        self.lineup = make_lineup(make_service(), [self.song])
        self.item = self.lineup.items.get()
        self.url = reverse(
            "worship:lineup_song",
            kwargs={"public_id": self.lineup.service.public_id, "pk": self.item.pk},
        )
        self.client.force_login(self.member)

    def test_without_a_connection_the_embedded_player_shows_and_no_sdk_loads(self):
        page = self.client.get(self.url)
        self.assertContains(
            page, 'src="https://open.spotify.com/embed/track/trackDDDDDDDDDDDDDDDDD"'
        )
        self.assertContains(page, "Open in Spotify")
        self.assertContains(page, "Connect your Spotify account")
        self.assertNotContains(page, "data-spotify-player")
        self.assertNotContains(page, "songs/player.js")

    def test_a_connected_account_gets_the_sdk_with_the_embedded_player_to_fall_back_to(
        self,
    ):
        make_spotify_connection(self.member, access="never-on-the-page")
        page = self.client.get(self.url)
        self.assertContains(page, 'data-track="spotify:track:trackDDDDDDDDDDDDDDDDD"')
        self.assertContains(page, "songs/player.js")
        self.assertContains(page, "data-player-fallback hidden")
        self.assertContains(page, 'data-src="https://open.spotify.com/embed/track/')
        self.assertContains(page, "Open in Spotify")
        self.assertNotContains(page, "never-on-the-page")

    @override_settings(SPOTIFY_TOKEN_KEY="")
    def test_when_spotify_connections_are_unavailable_the_embedded_player_shows(self):
        page = self.client.get(self.url)
        self.assertContains(page, 'src="https://open.spotify.com/embed/track/')
        self.assertNotContains(page, "data-spotify-player")
        self.assertNotContains(page, "Connect your Spotify account")

    def test_a_song_not_on_spotify_says_so_in_the_card(self):
        # Since Phase 9A, A7 the card stays and says there is no playback.
        self.song.spotify_id = ""
        self.song.save()
        page = self.client.get(self.url)
        self.assertContains(page, 'id="listen"')
        self.assertContains(page, "No playback for this song")
        self.assertNotContains(page, "open.spotify.com/embed")

    def test_the_player_script_falls_back_without_retrying(self):
        # The SDK runs in the browser, which the test suite doesn't run; this
        # checks player.js keeps the agreed fallbacks.
        from django.contrib.staticfiles import finders

        with open(finders.find("songs/player.js"), encoding="utf-8") as script:
            source = script.read()
        for event in (
            "initialization_error",
            "authentication_error",
            "account_error",
            "playback_error",
            "not_ready",
        ):
            self.assertIn(f'"{event}"', source)
        self.assertIn("reply.status === 429", source)
        self.assertIn("READY_TIMEOUT_MS", source)
        self.assertNotIn("console.", source)
        self.assertNotIn("localStorage", source)
