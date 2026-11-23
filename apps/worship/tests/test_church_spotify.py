"""The Church Spotify Account (Design-Decisions, Phase 7; decision 0011):
an optional church setting. When connected, every Lineup Playlist is made
and updated on it as a public playlist, and everyone who sees the
confirmed lineup gets the link. It is never used for playback. Spotify is
faked; tokens are made up."""

import datetime
import json
import urllib.parse
from unittest import mock

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.audit.models import AuditEvent
from apps.core.testing import (
    SPOTIFY_TEST_SETTINGS,
    FakeHttp,
    complete_setup,
    make_administrator,
    make_lineup,
    make_service,
    make_song,
    make_spotify_connection,
    make_user,
    quiet_logger,
)
from apps.songs import connections, spotify
from apps.songs.models import ChurchSpotifyAccount, SpotifyLimit
from apps.worship import lineups
from apps.worship.models import Lineup

CREATE = f"{spotify.API}/me/playlists"
ITEMS = f"{spotify.API}/playlists/"
PAGE = reverse("songs:church_spotify")
CONNECT = reverse("songs:church_spotify_connect")
DISCONNECT = reverse("songs:church_spotify_disconnect")
CALLBACK = reverse("songs:spotify_callback")


def make_church_account(access="church-access", refresh="church-refresh", **fields):
    return ChurchSpotifyAccount.objects.create(
        pk=ChurchSpotifyAccount.SINGLETON_PK,
        access_token_encrypted=connections.encrypt(access),
        refresh_token_encrypted=connections.encrypt(refresh),
        expires_at=timezone.now() + datetime.timedelta(hours=1),
        **fields,
    )


def spotify_calls(web):
    return [call for call in web.calls if call["path"].startswith(spotify.API)]


class PlaylistWeb(FakeHttp):
    """Fake Spotify that makes a new playlist ID for each create."""

    def __init__(self):
        super().__init__()
        self.made = 0

        def create(call):
            self.made += 1
            return 201, {"id": f"pl{self.made}"}

        self.reply("POST", CREATE, create)
        self.reply("PUT", ITEMS, {"snapshot_id": "s"})


@override_settings(**SPOTIFY_TEST_SETTINGS)
class ChurchAccountTestCase(TestCase):
    def setUp(self):
        complete_setup()
        quiet_logger(self)
        patcher = mock.patch(
            "apps.songs.spotify.time.sleep",
            side_effect=AssertionError("A web request waited on Spotify."),
        )
        patcher.start()
        self.addCleanup(patcher.stop)
        self.admin = make_administrator()
        self.leader = make_user(roles=["worship_leader"])
        self.member = make_user(roles=["team_member"])

    def new_lineup(self, *titles):
        service = make_service()
        songs = [
            make_song(title=title, spotify_id=f"track{title[:1]}{'X' * 16}")
            for title in titles
        ]
        return make_lineup(service, songs, confirmed=False)

    def confirm(self, lineup, user=None):
        self.client.force_login(user or self.leader)
        return self.client.post(
            reverse(
                "worship:lineup_confirm", kwargs={"public_id": lineup.service.public_id}
            ),
            follow=True,
        )

    def lineup_page(self, lineup, user):
        self.client.force_login(user)
        return self.client.get(
            reverse("worship:lineup", kwargs={"public_id": lineup.service.public_id})
        )


class ChurchPlaylistTests(ChurchAccountTestCase):
    def setUp(self):
        super().setUp()
        make_church_account()
        self.lineup = self.new_lineup("Alpha", "Beta")

    def test_confirming_makes_a_public_playlist_on_the_church_account(self):
        with PlaylistWeb() as web:
            page = self.confirm(self.lineup)
        create, items = spotify_calls(web)
        self.assertEqual(create["headers"]["Authorization"], "Bearer church-access")
        self.assertTrue(json.loads(create["body"])["public"])
        self.assertEqual(len(json.loads(items["body"])["uris"]), 2)
        lineup = Lineup.objects.get(pk=self.lineup.pk)
        self.assertTrue(lineup.is_confirmed)
        self.assertEqual(lineup.spotify_playlist_id, "pl1")
        self.assertTrue(lineup.spotify_playlist_on_church_account)
        self.assertIsNone(lineup.spotify_playlist_owner)
        self.assertContains(page, "Saved to the church&#x27;s Spotify account")

    def test_the_confirmer_needs_no_connection_of_their_own(self):
        with PlaylistWeb() as web:
            self.confirm(self.lineup)
        self.assertEqual(len(spotify_calls(web)), 2)

    def test_a_team_member_sees_the_link_but_no_save_button(self):
        with PlaylistWeb():
            self.confirm(self.lineup)
        page = self.lineup_page(self.lineup, self.member)
        self.assertContains(page, "https://open.spotify.com/playlist/pl1")
        self.assertContains(page, "Open the playlist")
        self.assertNotContains(page, "Save to Spotify")

    def test_the_name_is_the_service_name_and_date(self):
        with PlaylistWeb() as web:
            self.confirm(self.lineup)
        name = json.loads(spotify_calls(web)[0]["body"])["name"]
        self.assertTrue(name.startswith(f"{self.lineup.service.name} – "))

    def test_saving_again_updates_the_same_playlist(self):
        with PlaylistWeb():
            self.confirm(self.lineup)
        lineup = Lineup.objects.get(pk=self.lineup.pk)
        lineups.add_from_pool(
            lineup,
            make_song(title="Gamma", spotify_id="trackG" + "X" * 16),
            None,
            self.leader,
        )
        self.assertContains(
            self.lineup_page(lineup, self.leader), ">Save to Spotify</button>"
        )
        with PlaylistWeb() as web:
            self.client.post(
                reverse(
                    "worship:lineup_save_playlist",
                    kwargs={"public_id": lineup.service.public_id},
                )
            )
        calls = spotify_calls(web)
        self.assertEqual([call["method"] for call in calls], ["PUT"])
        self.assertEqual(calls[0]["path"], f"{spotify.API}/playlists/pl1/items")
        self.assertEqual(len(json.loads(calls[0]["body"])["uris"]), 3)

    def test_reopening_and_confirming_again_updates_the_same_playlist(self):
        with PlaylistWeb():
            self.confirm(self.lineup)
        lineups.reopen(Lineup.objects.get(pk=self.lineup.pk), self.admin)
        with PlaylistWeb() as web:
            self.confirm(self.lineup)
        self.assertEqual([call["method"] for call in spotify_calls(web)], ["PUT"])
        self.assertEqual(
            Lineup.objects.get(pk=self.lineup.pk).spotify_playlist_id, "pl1"
        )

    def test_two_services_get_two_playlists_and_editing_one_leaves_the_other(self):
        other = self.new_lineup("Delta", "Echo")
        with PlaylistWeb() as web:
            self.confirm(self.lineup)
            self.confirm(other)
        self.assertEqual(web.made, 2)
        first = Lineup.objects.get(pk=self.lineup.pk)
        second = Lineup.objects.get(pk=other.pk)
        self.assertNotEqual(first.spotify_playlist_id, second.spotify_playlist_id)
        second_tracks = list(second.spotify_playlist_tracks)
        lineups.remove(first, first.items.first(), self.leader)
        with PlaylistWeb() as web:
            self.client.post(
                reverse(
                    "worship:lineup_save_playlist",
                    kwargs={"public_id": first.service.public_id},
                )
            )
        paths = [call["path"] for call in spotify_calls(web)]
        self.assertEqual(
            paths, [f"{spotify.API}/playlists/{first.spotify_playlist_id}/items"]
        )
        second.refresh_from_db()
        self.assertEqual(second.spotify_playlist_tracks, second_tracks)

    def test_a_playlist_spotify_no_longer_has_is_made_again(self):
        with PlaylistWeb():
            self.confirm(self.lineup)
        lineups.reopen(Lineup.objects.get(pk=self.lineup.pk), self.admin)
        with FakeHttp() as web:
            web.reply("PUT", f"{spotify.API}/playlists/pl1/", {}, status=404)
            web.reply("POST", CREATE, {"id": "pl-new"}, status=201)
            web.reply("PUT", f"{spotify.API}/playlists/pl-new/", {})
            self.confirm(self.lineup)
        self.assertEqual(
            Lineup.objects.get(pk=self.lineup.pk).spotify_playlist_id, "pl-new"
        )

    # Updating a stored playlist (Design-Decisions, Phase 8): a new one only
    # on a 404, or a 403 from a playlist the connected account doesn't own.

    def with_stored_playlist(self):
        Lineup.objects.filter(pk=self.lineup.pk).update(
            spotify_playlist_id="pl1",
            spotify_playlist_on_church_account=True,
            spotify_playlist_tracks=["trackOLD"],
        )

    def refused_update(self, web, *, owner, me="church-user"):
        web.reply("PUT", f"{spotify.API}/playlists/pl1/", {}, status=403)
        web.reply("GET", f"{spotify.API}/playlists/pl1", {"owner": {"id": owner}})
        web.reply("GET", f"{spotify.API}/me", {"id": me})
        web.reply("POST", CREATE, {"id": "pl-new"}, status=201)
        web.reply("PUT", f"{spotify.API}/playlists/pl-new/", {})

    def test_a_403_from_a_playlist_another_account_owns_makes_a_new_one(self):
        self.with_stored_playlist()
        with FakeHttp() as web:
            self.refused_update(web, owner="someone-else")
            self.confirm(self.lineup)
        lineup = Lineup.objects.get(pk=self.lineup.pk)
        self.assertEqual(lineup.spotify_playlist_id, "pl-new")
        self.assertEqual(len(lineup.spotify_playlist_tracks), 2)
        # Both account IDs were only compared, never stored.
        stored = str(list(Lineup.objects.values())) + str(
            list(ChurchSpotifyAccount.objects.values())
        )
        self.assertNotIn("someone-else", stored)
        self.assertNotIn("church-user", stored)

    def test_a_403_on_the_accounts_own_playlist_is_a_refusal(self):
        self.with_stored_playlist()
        with FakeHttp() as web:
            self.refused_update(web, owner="church-user")
            page = self.confirm(self.lineup)
        self.assertNotIn(CREATE, [call["path"] for call in web.calls])
        lineup = Lineup.objects.get(pk=self.lineup.pk)
        self.assertTrue(lineup.is_confirmed)
        self.assertEqual(lineup.spotify_playlist_id, "pl1")
        self.assertContains(page, "The Spotify playlist wasn&#x27;t saved")
        self.assertContains(page, ">Save to Spotify</button>")

    def test_a_403_whose_playlist_is_gone_on_lookup_makes_a_new_one(self):
        self.with_stored_playlist()
        with FakeHttp() as web:
            self.refused_update(web, owner="x")
            web.reply("GET", f"{spotify.API}/playlists/pl1", {}, status=404)
            self.confirm(self.lineup)
        self.assertEqual(
            Lineup.objects.get(pk=self.lineup.pk).spotify_playlist_id, "pl-new"
        )

    def test_a_429_on_the_owner_lookup_fails_fast_with_save_to_spotify(self):
        self.with_stored_playlist()
        with FakeHttp() as web:
            self.refused_update(web, owner="someone-else")
            web.reply(
                "GET",
                f"{spotify.API}/me",
                {},
                status=429,
                headers={"retry-after": "9"},
            )
            page = self.confirm(self.lineup)
        self.assertNotIn(CREATE, [call["path"] for call in web.calls])
        self.assertEqual(SpotifyLimit.objects.count(), 1)
        lineup = Lineup.objects.get(pk=self.lineup.pk)
        self.assertTrue(lineup.is_confirmed)
        self.assertEqual(lineup.spotify_playlist_id, "pl1")
        self.assertContains(page, ">Save to Spotify</button>")

    def test_a_429_leaves_the_lineup_confirmed_with_save_to_spotify(self):
        with FakeHttp() as web:
            web.reply("POST", CREATE, {}, status=429, headers={"retry-after": "9"})
            page = self.confirm(self.lineup)
        self.assertTrue(Lineup.objects.get(pk=self.lineup.pk).is_confirmed)
        self.assertEqual(len(spotify_calls(web)), 1)
        self.assertEqual(SpotifyLimit.objects.count(), 1)
        self.assertContains(page, ">Save to Spotify</button>")

    def test_a_refusal_leaves_the_lineup_confirmed_with_save_to_spotify(self):
        with FakeHttp() as web:
            web.reply("POST", CREATE, {"error": {"message": "Forbidden"}}, status=403)
            page = self.confirm(self.lineup)
        self.assertTrue(Lineup.objects.get(pk=self.lineup.pk).is_confirmed)
        self.assertContains(page, "The Spotify playlist wasn&#x27;t saved")
        self.assertContains(page, ">Save to Spotify</button>")
        self.assertTrue(ChurchSpotifyAccount.objects.exists())

    def test_a_revoked_church_account_leaves_the_lineup_confirmed(self):
        account = ChurchSpotifyAccount.objects.get()
        account.expires_at = timezone.now()
        account.save()
        with FakeHttp() as web:
            web.reply("POST", spotify.TOKEN_URL, {"error": "invalid_grant"}, status=400)
            page = self.confirm(self.lineup)
        self.assertTrue(Lineup.objects.get(pk=self.lineup.pk).is_confirmed)
        self.assertContains(page, "needs connecting again in church settings")
        self.assertContains(page, "Save to Spotify")

    def test_a_personal_playlist_moves_to_the_church_account_once_it_is_connected(self):
        ChurchSpotifyAccount.objects.all().delete()
        make_spotify_connection(self.leader)
        with PlaylistWeb():
            self.confirm(self.lineup)
        self.assertFalse(
            Lineup.objects.get(pk=self.lineup.pk).spotify_playlist_on_church_account
        )
        make_church_account()
        self.assertContains(
            self.lineup_page(self.lineup, self.leader), ">Save to Spotify</button>"
        )


class WithoutChurchAccountTests(ChurchAccountTestCase):
    def test_the_playlist_goes_privately_to_the_confirmers_account(self):
        make_spotify_connection(self.leader, access="leader-access")
        lineup = self.new_lineup("Alpha")
        with PlaylistWeb() as web:
            self.confirm(lineup)
        create = spotify_calls(web)[0]
        self.assertEqual(create["headers"]["Authorization"], "Bearer leader-access")
        self.assertFalse(json.loads(create["body"])["public"])
        lineup.refresh_from_db()
        self.assertEqual(lineup.spotify_playlist_owner, self.leader)
        self.assertFalse(lineup.spotify_playlist_on_church_account)
        # Private: a team member sees no link.
        page = self.lineup_page(lineup, self.member)
        self.assertNotContains(page, "open.spotify.com/playlist")


class ChurchAccountSettingTests(ChurchAccountTestCase):
    def test_only_holders_of_the_church_settings_permission_may_manage_it(self):
        make_church_account()
        for user in (self.leader, self.member):
            self.client.force_login(user)
            self.assertEqual(self.client.get(PAGE).status_code, 403)
            self.assertEqual(self.client.post(CONNECT).status_code, 403)
            self.assertEqual(self.client.post(DISCONNECT).status_code, 403)
        self.assertTrue(ChurchSpotifyAccount.objects.exists())
        self.client.force_login(make_user(perms=["church.change_churchprofile"]))
        self.assertEqual(self.client.get(PAGE).status_code, 200)

    def test_connecting_asks_only_for_the_playlist_scopes(self):
        self.client.force_login(self.admin)
        response = self.client.post(CONNECT)
        query = urllib.parse.parse_qs(urllib.parse.urlsplit(response["Location"]).query)
        self.assertEqual(
            set(query["scope"][0].split()),
            {"playlist-modify-public", "playlist-modify-private"},
        )
        self.assertEqual(query["redirect_uri"], [f"http://testserver{CALLBACK}"])

    def test_coming_back_stores_the_church_account_encrypted(self):
        self.client.force_login(self.admin)
        response = self.client.post(CONNECT)
        state = urllib.parse.parse_qs(
            urllib.parse.urlsplit(response["Location"]).query
        )["state"][0]
        with FakeHttp() as web:
            web.reply(
                "POST",
                spotify.TOKEN_URL,
                {"access_token": "made-up-church", "refresh_token": "made-up-church-r"},
            )
            response = self.client.get(CALLBACK, {"code": "c", "state": state})
        self.assertRedirects(response, PAGE, fetch_redirect_response=False)
        account = ChurchSpotifyAccount.objects.get()
        self.assertNotIn("made-up", account.access_token_encrypted)
        self.assertNotIn("made-up", account.refresh_token_encrypted)
        self.assertEqual(
            connections.decrypt(account.access_token_encrypted), "made-up-church"
        )
        self.assertEqual(account.connected_by, self.admin)
        event = AuditEvent.objects.get()
        self.assertEqual(
            event.changes, {"Church Spotify account": ["Not connected", "Connected"]}
        )
        self.assertNotIn("made-up", json.dumps(event.changes))

    def test_someone_who_lost_the_permission_cant_finish_connecting(self):
        holder = make_user(perms=["church.change_churchprofile"])
        self.client.force_login(holder)
        response = self.client.post(CONNECT)
        state = urllib.parse.parse_qs(
            urllib.parse.urlsplit(response["Location"]).query
        )["state"][0]
        holder.user_permissions.clear()
        with FakeHttp() as web:
            response = self.client.get(CALLBACK, {"code": "c", "state": state})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(web.calls, [])
        self.assertFalse(ChurchSpotifyAccount.objects.exists())

    def test_disconnecting_forgets_it(self):
        make_church_account()
        self.client.force_login(self.admin)
        self.client.post(DISCONNECT)
        self.assertFalse(ChurchSpotifyAccount.objects.exists())
        self.assertEqual(
            AuditEvent.objects.get().changes,
            {"Church Spotify account": ["Connected", "Not connected"]},
        )

    def test_the_church_settings_show_a_spotify_tab(self):
        self.client.force_login(self.admin)
        page = self.client.get(
            reverse("church:settings", kwargs={"section": "details"})
        )
        self.assertContains(page, PAGE)
        self.assertNotContains(self.client.get(PAGE), "church-access")

    def test_switched_off_worship_module_hides_it(self):
        complete_setup(disabled_modules=["worship"])
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(PAGE).status_code, 404)
        page = self.client.get(
            reverse("church:settings", kwargs={"section": "details"})
        )
        self.assertNotContains(page, PAGE)


class NeverUsedForPlaybackTests(ChurchAccountTestCase):
    def test_the_church_account_never_plays_music(self):
        make_church_account(access="church-only")
        lineup = make_lineup(
            make_service(), [make_song(spotify_id="trackZ" + "X" * 16)]
        )
        item = lineup.items.get()
        self.client.force_login(self.member)
        page = self.client.get(
            reverse(
                "worship:lineup_song",
                kwargs={"public_id": lineup.service.public_id, "pk": item.pk},
            )
        )
        self.assertNotContains(page, "data-spotify-player")
        self.assertContains(page, 'src="https://open.spotify.com/embed/track/')
        response = self.client.post(reverse("songs:spotify_player_token"))
        self.assertEqual(response.status_code, 404)
        self.assertNotIn("church-only", response.content.decode())
