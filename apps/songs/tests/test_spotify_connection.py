"""Each user's own Spotify account (Design-Decisions, Phase 7): connecting
with the Authorization Code flow, tokens stored encrypted and refreshed,
disconnecting, and the access token the browser's player asks for. Spotify
is faked; every token is made up."""

import datetime
import json
import logging
import urllib.parse

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.audit.models import AuditEvent
from apps.core.testing import (
    SPOTIFY_TEST_SETTINGS,
    FakeHttp,
    complete_setup,
    make_spotify_connection,
    make_user,
    quiet_logger,
)
from apps.songs import connections, spotify
from apps.songs.models import SpotifyConnection, SpotifyLimit

ACCOUNT = reverse("songs:spotify_account")
CONNECT = reverse("songs:spotify_connect")
CALLBACK = reverse("songs:spotify_callback")
DISCONNECT = reverse("songs:spotify_disconnect")
PLAYER_TOKEN = reverse("songs:spotify_player_token")
TOKENS = {
    "access_token": "made-up-access-1",
    "refresh_token": "made-up-refresh-1",
    "expires_in": 3600,
    "scope": "streaming playlist-modify-private",
}


def grant(call):
    return urllib.parse.parse_qs(call["body"])["grant_type"][0]


@override_settings(**SPOTIFY_TEST_SETTINGS)
class SpotifyTestCase(TestCase):
    def setUp(self):
        complete_setup()
        self.user = make_user(roles=["team_member"])
        self.client.force_login(self.user)

    def start_connecting(self, **data):
        response = self.client.post(CONNECT, data)
        query = urllib.parse.parse_qs(urllib.parse.urlsplit(response["Location"]).query)
        return response, query

    def come_back(self, state, code="made-up-code", tokens=TOKENS, status=200):
        with FakeHttp() as web:
            web.reply("POST", spotify.TOKEN_URL, tokens, status=status)
            response = self.client.get(CALLBACK, {"code": code, "state": state})
        return response, web


class EncryptionTests(SpotifyTestCase):
    def test_a_stored_token_is_not_the_plain_token_and_decrypts_back(self):
        connection = make_spotify_connection(
            self.user, access="plain-access", refresh="plain-refresh"
        )
        stored = SpotifyConnection.objects.values().get(pk=connection.pk)
        for column, plain in (
            ("access_token_encrypted", "plain-access"),
            ("refresh_token_encrypted", "plain-refresh"),
        ):
            self.assertNotIn(plain, stored[column])
            self.assertEqual(connections.decrypt(stored[column]), plain)

    def test_tokens_given_by_spotify_never_show_in_their_repr(self):
        tokens = spotify.UserTokens.from_api(TOKENS)
        self.assertNotIn("made-up", repr(tokens))


class ConnectTests(SpotifyTestCase):
    def test_connect_sends_the_person_to_spotify_with_a_state_and_the_scopes(self):
        response, query = self.start_connecting()
        self.assertTrue(response["Location"].startswith(spotify.AUTHORIZE_URL))
        self.assertEqual(query["response_type"], ["code"])
        self.assertEqual(query["client_id"], ["test-client"])
        self.assertIn("streaming", query["scope"][0].split())
        self.assertIn("playlist-modify-private", query["scope"][0].split())
        self.assertEqual(query["redirect_uri"], [f"http://testserver{CALLBACK}"])
        self.assertEqual(
            self.client.session[connections.SESSION_KEY]["state"], query["state"][0]
        )

    @override_settings(SPOTIFY_REDIRECT_URI="http://127.0.0.1:8000/callback/")
    def test_the_redirect_uri_setting_wins(self):
        _, query = self.start_connecting()
        self.assertEqual(query["redirect_uri"], ["http://127.0.0.1:8000/callback/"])

    def test_coming_back_stores_the_tokens_encrypted(self):
        _, query = self.start_connecting(next="/worship/")
        response, web = self.come_back(query["state"][0])
        self.assertRedirects(response, "/worship/", fetch_redirect_response=False)
        self.assertEqual(grant(web.calls[0]), "authorization_code")
        self.assertEqual(len(web.calls), 1)
        connection = SpotifyConnection.objects.get(user=self.user)
        self.assertNotIn("made-up", connection.access_token_encrypted)
        self.assertEqual(
            connections.decrypt(connection.access_token_encrypted), "made-up-access-1"
        )
        self.assertEqual(
            connections.decrypt(connection.refresh_token_encrypted), "made-up-refresh-1"
        )

    def test_the_audit_trail_records_the_connection_without_tokens(self):
        _, query = self.start_connecting()
        self.come_back(query["state"][0])
        event = AuditEvent.objects.get(object_id=str(self.user.pk))
        self.assertEqual(
            event.changes, {"Spotify account": ["Not connected", "Connected"]}
        )
        self.assertNotIn("made-up", json.dumps(event.changes))

    def test_a_state_this_session_never_sent_is_refused(self):
        self.start_connecting()
        response, web = self.come_back("someone-elses-state")
        self.assertRedirects(response, ACCOUNT, fetch_redirect_response=False)
        self.assertEqual(web.calls, [])
        self.assertFalse(SpotifyConnection.objects.exists())

    def test_a_state_works_only_once(self):
        _, query = self.start_connecting()
        self.come_back(query["state"][0])
        SpotifyConnection.objects.all().delete()
        _, web = self.come_back(query["state"][0])
        self.assertEqual(web.calls, [])
        self.assertFalse(SpotifyConnection.objects.exists())

    def test_declining_on_spotify_connects_nothing(self):
        _, query = self.start_connecting()
        with FakeHttp() as web:
            self.client.get(
                CALLBACK, {"error": "access_denied", "state": query["state"][0]}
            )
        self.assertEqual(web.calls, [])
        self.assertFalse(SpotifyConnection.objects.exists())

    def test_a_refused_code_says_so(self):
        _, query = self.start_connecting()
        response, _ = self.come_back(
            query["state"][0], tokens={"error": "invalid_grant"}, status=400
        )
        self.assertFalse(SpotifyConnection.objects.exists())
        page = self.client.get(response["Location"])
        self.assertContains(page, "Spotify wasn&#x27;t connected")

    def test_a_429_while_connecting_fails_fast_and_records_the_block(self):
        quiet_logger(self)
        _, query = self.start_connecting()
        with FakeHttp() as web:
            web.reply(
                "POST", spotify.TOKEN_URL, {}, status=429, headers={"retry-after": "30"}
            )
            self.client.get(CALLBACK, {"code": "c", "state": query["state"][0]})
        self.assertEqual(len(web.calls), 1)
        self.assertEqual(SpotifyLimit.objects.count(), 1)
        self.assertFalse(SpotifyConnection.objects.exists())

    def test_disconnecting_forgets_the_tokens(self):
        make_spotify_connection(self.user)
        self.client.post(DISCONNECT)
        self.assertFalse(SpotifyConnection.objects.exists())
        event = AuditEvent.objects.get(object_id=str(self.user.pk))
        self.assertEqual(
            event.changes, {"Spotify account": ["Connected", "Not connected"]}
        )

    def test_the_account_page_offers_connect_or_disconnect(self):
        self.assertContains(self.client.get(ACCOUNT), "Connect Spotify")
        make_spotify_connection(self.user)
        page = self.client.get(ACCOUNT)
        self.assertContains(page, "Disconnect Spotify")
        self.assertNotContains(page, "test-access-token")

    @override_settings(SPOTIFY_TOKEN_KEY="")
    def test_without_the_token_key_connecting_is_unavailable(self):
        self.assertContains(self.client.get(ACCOUNT), "Spotify isn't set up")
        response = self.client.post(CONNECT)
        self.assertRedirects(response, ACCOUNT, fetch_redirect_response=False)


class AccessTests(SpotifyTestCase):
    def test_signed_out_people_are_sent_to_sign_in(self):
        self.client.logout()
        for url in (ACCOUNT, CALLBACK):
            self.assertEqual(self.client.get(url).status_code, 302)
        for url in (CONNECT, DISCONNECT, PLAYER_TOKEN):
            self.assertEqual(self.client.post(url).status_code, 302)

    def test_switched_off_module_is_404(self):
        complete_setup(disabled_modules=["worship"])
        self.assertEqual(self.client.get(ACCOUNT).status_code, 404)
        self.assertEqual(self.client.post(PLAYER_TOKEN).status_code, 404)


class RefreshTests(SpotifyTestCase):
    def client_(self):
        return spotify.SpotifyClient.from_settings()

    def test_a_fresh_token_is_used_without_calling_spotify(self):
        connection = make_spotify_connection(self.user, access="still-good")
        with FakeHttp() as web:
            token = connections.access_token(connection, self.client_())
        self.assertEqual(token, "still-good")
        self.assertEqual(web.calls, [])

    def test_an_expiring_token_is_refreshed_and_stored_encrypted(self):
        connection = make_spotify_connection(self.user, refresh="r-1", expires_in=30)
        with FakeHttp() as web:
            web.reply(
                "POST",
                spotify.TOKEN_URL,
                {"access_token": "new-access", "expires_in": 3600},
            )
            token = connections.access_token(connection, self.client_())
        self.assertEqual(token, "new-access")
        self.assertEqual(grant(web.calls[0]), "refresh_token")
        connection.refresh_from_db()
        self.assertEqual(
            connections.decrypt(connection.access_token_encrypted), "new-access"
        )
        # Spotify sent no new refresh token, so the old one is kept.
        self.assertEqual(connections.decrypt(connection.refresh_token_encrypted), "r-1")
        self.assertGreater(
            connection.expires_at, timezone.now() + datetime.timedelta(minutes=50)
        )

    def test_a_revoked_connection_is_removed(self):
        connection = make_spotify_connection(self.user, expires_in=0)
        with FakeHttp() as web:
            web.reply("POST", spotify.TOKEN_URL, {"error": "invalid_grant"}, status=400)
            with self.assertRaises(connections.SpotifyNotConnected):
                connections.access_token(connection, self.client_())
        self.assertFalse(SpotifyConnection.objects.exists())

    def test_tokens_the_key_cant_read_remove_the_connection(self):
        connection = make_spotify_connection(self.user)
        connection.access_token_encrypted = "not-a-fernet-token"
        connection.save()
        with self.assertRaises(connections.SpotifyNotConnected):
            connections.access_token(connection, self.client_())
        self.assertFalse(SpotifyConnection.objects.exists())

    def test_a_refused_token_is_refreshed_once_and_the_call_tried_again(self):
        connection = make_spotify_connection(self.user, access="old")
        seen = []

        def call(token):
            seen.append(token)
            if token == "old":
                raise spotify.SpotifyUnauthorized("refused")
            return "done"

        with FakeHttp() as web:
            web.reply(
                "POST", spotify.TOKEN_URL, {"access_token": "new", "expires_in": 3600}
            )
            result = connections.call_with_token(connection, self.client_(), call)
        self.assertEqual((result, seen), ("done", ["old", "new"]))


class PlayerTokenTests(SpotifyTestCase):
    def test_the_player_gets_the_persons_own_access_token_uncached(self):
        make_spotify_connection(self.user, access="for-the-player")
        with FakeHttp() as web:
            response = self.client.post(PLAYER_TOKEN)
        self.assertEqual(response.json()["access_token"], "for-the-player")
        self.assertNotIn("refresh", json.dumps(response.json()))
        self.assertIn("no-store", response["Cache-Control"])
        self.assertEqual(web.calls, [])

    def test_without_a_connection_there_is_no_token(self):
        response = self.client.post(PLAYER_TOKEN)
        self.assertEqual(response.status_code, 404)
        self.assertNotIn("access_token", response.json())

    def test_a_get_never_hands_out_a_token(self):
        make_spotify_connection(self.user)
        self.assertEqual(self.client.get(PLAYER_TOKEN).status_code, 405)

    def test_during_a_spotify_block_the_player_is_told_at_once(self):
        make_spotify_connection(self.user, expires_in=0)
        now = timezone.now()
        SpotifyLimit.objects.create(
            occurred_at=now,
            reason=SpotifyLimit.Reason.RATE_LIMIT,
            retry_after=60,
            blocked_until=now + datetime.timedelta(seconds=60),
        )
        with FakeHttp() as web:
            response = self.client.post(PLAYER_TOKEN)
        self.assertEqual(response.status_code, 429)
        self.assertIn("Spotify asked CHORD to wait", response.json()["error"])
        self.assertEqual(web.calls, [])


class NoTokensInLogsTests(SpotifyTestCase):
    def test_connecting_and_refreshing_log_no_token(self):
        with self.assertLogs(level=logging.DEBUG) as logs:
            logging.getLogger("apps").debug("start")
            _, query = self.start_connecting()
            self.come_back(query["state"][0])
            connection = SpotifyConnection.objects.get()
            connection.expires_at = timezone.now()
            connection.save()
            with FakeHttp() as web:
                web.reply(
                    "POST", spotify.TOKEN_URL, {"access_token": "made-up-access-2"}
                )
                connections.access_token(
                    connection, spotify.SpotifyClient.from_settings()
                )
        self.assertNotIn("made-up", "\n".join(logs.output))
