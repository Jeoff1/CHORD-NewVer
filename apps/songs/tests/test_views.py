"""The song library screens and the song settings lists."""

from django.test import TestCase, override_settings
from django.urls import reverse

from apps.accounts.models import Role
from apps.audit.models import AuditEvent
from apps.core.music import Feel
from apps.core.testing import (
    FakeHttp,
    complete_setup,
    make_administrator,
    make_song,
    make_user,
)
from apps.songs import spotify
from apps.songs.models import Song, ThemeTag, TrustedArtist

LIST = reverse("songs:list")
SEARCH = reverse("songs:spotify_search")
ADD = reverse("songs:spotify_add")
VIEWER = ["songs.view_song"]
EDITOR = VIEWER + ["songs.change_song"]
FINDER = VIEWER + ["songs.add_song"]
SPOTIFY_ID = "4uLU6hMCjMI75M1A2tKUQC"
SPOTIFY_KEYS = {"SPOTIFY_CLIENT_ID": "id", "SPOTIFY_CLIENT_SECRET": "secret"}


def url(song, name="detail"):
    return reverse(f"songs:{name}", kwargs={"public_id": song.public_id})


def spotify_web():
    web = FakeHttp()
    web.reply("POST", spotify.TOKEN_URL, {"access_token": "t", "expires_in": 3600})
    return web


def api_track(spotify_id=SPOTIFY_ID, name="Morning Song"):
    return {
        "id": spotify_id,
        "name": name,
        "artists": [{"name": "Band"}],
        "album": {"name": "Album"},
        "duration_ms": 200_000,
    }


class SongsTestCase(TestCase):
    def setUp(self):
        complete_setup()


class SongListTests(SongsTestCase):
    def titles(self, **params):
        response = self.client.get(LIST, params)
        return [song.title for song in response.context["object_list"]]

    def test_needs_permission(self):
        self.client.force_login(make_user())
        self.assertEqual(self.client.get(LIST).status_code, 403)

    def test_switched_off_module_is_404_and_keeps_its_data(self):
        song = make_song()
        complete_setup(disabled_modules=["worship"])
        self.client.force_login(make_administrator())
        self.assertEqual(self.client.get(LIST).status_code, 404)
        self.assertEqual(self.client.get(url(song)).status_code, 404)
        self.assertEqual(
            self.client.get(reverse("songs:theme_tags_list")).status_code, 404
        )
        self.assertTrue(Song.objects.filter(pk=song.pk).exists())

    def test_search_and_filters(self):
        grace = ThemeTag.objects.get(name="Grace")
        make_song(
            title="Morning",
            artist="Choir",
            worship_check=Song.WorshipCheck.ACCEPTED,
            feel=Feel.UPBEAT,
            team_knows=True,
            tags=[grace],
        )
        make_song(
            title="Evening",
            worship_check=Song.WorshipCheck.REJECTED,
            lyrics_status=Song.LyricsStatus.FOUND,
        )
        self.client.force_login(make_user(perms=VIEWER))
        self.assertEqual(self.titles(), ["Evening", "Morning"])
        self.assertEqual(self.titles(q="choir"), ["Morning"])
        self.assertEqual(self.titles(check="rejected"), ["Evening"])
        self.assertEqual(self.titles(feel="upbeat"), ["Morning"])
        self.assertEqual(self.titles(known="yes"), ["Morning"])
        self.assertEqual(self.titles(known="no"), ["Evening"])
        self.assertEqual(self.titles(tag=grace.pk), ["Morning"])
        self.assertEqual(self.titles(lyrics="found"), ["Evening"])
        self.assertEqual(self.titles(check="bogus", tag="x"), ["Evening", "Morning"])

    def test_empty_pool(self):
        self.client.force_login(make_user(perms=FINDER))
        response = self.client.get(LIST)
        self.assertContains(response, "The song pool is empty")
        self.assertContains(response, "Find on Spotify")

    def test_songs_link_from_the_worship_pages(self):
        self.client.force_login(
            make_user(perms=VIEWER + ["worship.view_worshipservice"])
        )
        self.assertContains(self.client.get(reverse("worship:home")), f'href="{LIST}"')


class SongDetailTests(SongsTestCase):
    def test_shows_the_song_and_its_analysis(self):
        song = make_song(
            title="Morning",
            length_seconds=245,
            lyrics="Invented words of praise",
            lyrics_status=Song.LyricsStatus.FOUND,
            worship_check=Song.WorshipCheck.ACCEPTED,
            worship_score=0.8125,
            tags=[ThemeTag.objects.get(name="Joy")],
        )
        song.tag_scores = {str(ThemeTag.objects.get(name="Joy").pk): 0.72}
        song.save()
        self.client.force_login(make_user(perms=VIEWER))
        response = self.client.get(url(song))
        self.assertContains(response, "4:05")
        self.assertContains(response, "Lyrics score 81%")
        self.assertContains(response, "Joy")
        self.assertContains(response, "72%")
        self.assertContains(response, "Invented words of praise")
        self.assertContains(
            response, f"https://open.spotify.com/track/{song.spotify_id}"
        )
        self.assertNotContains(response, url(song, "update"))

    def test_needs_permission(self):
        self.client.force_login(make_user())
        self.assertEqual(self.client.get(url(make_song())).status_code, 403)


class SongEditTests(SongsTestCase):
    def test_corrections_are_saved_reviewed_and_audited(self):
        joy = ThemeTag.objects.get(name="Joy")
        song = make_song(worship_check=Song.WorshipCheck.REJECTED)
        editor = make_user(perms=EDITOR)
        self.client.force_login(editor)
        response = self.client.post(
            url(song, "update"),
            {
                "worship_check": "accepted",
                "tags": [joy.pk],
                "feel": "slow",
                "team_knows": "on",
            },
        )
        self.assertRedirects(response, url(song))
        song.refresh_from_db()
        self.assertEqual(song.worship_check, Song.WorshipCheck.ACCEPTED)
        self.assertEqual(list(song.tags.all()), [joy])
        self.assertTrue(song.team_knows)
        self.assertEqual(song.reviewed_by, editor)
        event = AuditEvent.objects.get(action=AuditEvent.Action.CHANGED)
        self.assertEqual(
            event.changes["Worship check"], ["Not a worship song", "Worship song"]
        )
        self.assertEqual(event.changes["Theme tags"], ["", "Joy"])
        self.assertEqual(event.changes["Feel"], ["", "Slow"])

    def test_switched_off_tag_stays_on_a_song_that_has_it(self):
        old = ThemeTag.objects.create(name="Old theme", is_active=False)
        song = make_song(tags=[old])
        self.client.force_login(make_user(perms=EDITOR))
        response = self.client.get(url(song, "update"))
        choices = [tag.name for tag in response.context["form"].fields["tags"].queryset]
        self.assertIn("Old theme", choices)
        other = make_song()
        response = self.client.get(url(other, "update"))
        choices = [tag.name for tag in response.context["form"].fields["tags"].queryset]
        self.assertNotIn("Old theme", choices)

    def test_needs_permission(self):
        song = make_song()
        self.client.force_login(make_user(perms=VIEWER))
        self.assertEqual(self.client.get(url(song, "update")).status_code, 403)
        self.assertEqual(self.client.post(url(song, "check_again")).status_code, 403)

    def test_check_again_queues_the_song(self):
        song = make_song(lyrics_status=Song.LyricsStatus.MISSING)
        self.client.force_login(make_user(perms=EDITOR))
        response = self.client.post(url(song, "check_again"))
        self.assertRedirects(response, url(song))
        song.refresh_from_db()
        self.assertEqual(song.lyrics_status, Song.LyricsStatus.PENDING)
        event = AuditEvent.objects.get()
        self.assertEqual(event.changes["Lyrics"], ["Not found", "Not looked up yet"])
        self.assertEqual(self.client.get(url(song, "check_again")).status_code, 405)


class SpotifySearchTests(SongsTestCase):
    def test_without_credentials_says_so(self):
        self.client.force_login(make_user(perms=FINDER))
        response = self.client.get(SEARCH, {"q": "grace"})
        self.assertContains(response, "SPOTIFY_CLIENT_ID")

    def test_empty_search_calls_nobody(self):
        self.client.force_login(make_user(perms=FINDER))
        response = self.client.get(SEARCH)
        self.assertIsNone(response.context["tracks"])

    @override_settings(**SPOTIFY_KEYS)
    def test_lists_tracks_and_marks_those_in_the_pool(self):
        known = make_song(spotify_id="0" * 22)
        self.client.force_login(make_user(perms=FINDER))
        with spotify_web() as web:
            web.reply(
                "GET",
                f"{spotify.API}/search",
                {"tracks": {"items": [api_track(), api_track("0" * 22, "Known")]}},
            )
            response = self.client.get(SEARCH, {"q": "morning"})
        self.assertContains(response, "Morning Song")
        self.assertContains(response, url(known))
        self.assertContains(response, f'value="{SPOTIFY_ID}"')

    @override_settings(**SPOTIFY_KEYS)
    def test_spotify_problem_is_shown(self):
        self.client.force_login(make_user(perms=FINDER))
        with spotify_web() as web:
            web.reply("GET", f"{spotify.API}/search", {}, status=503)
            response = self.client.get(SEARCH, {"q": "morning"})
        self.assertContains(response, "Spotify answered 503")

    @override_settings(**SPOTIFY_KEYS)
    def test_add_fetches_the_track_and_audits_it(self):
        user = make_user(perms=FINDER)
        self.client.force_login(user)
        with spotify_web() as web:
            web.reply("GET", f"{spotify.API}/tracks/{SPOTIFY_ID}", api_track())
            response = self.client.post(ADD, {"spotify_id": SPOTIFY_ID})
            again = self.client.post(ADD, {"spotify_id": SPOTIFY_ID}, follow=True)
        song = Song.objects.get(spotify_id=SPOTIFY_ID)
        self.assertRedirects(response, url(song))
        self.assertEqual(song.title, "Morning Song")
        event = AuditEvent.objects.get()
        self.assertEqual(event.action, AuditEvent.Action.CREATED)
        self.assertEqual(event.actor, user)
        self.assertContains(again, "already in the song pool")

    def test_add_rejects_anything_but_a_track_id(self):
        self.client.force_login(make_user(perms=FINDER))
        response = self.client.post(ADD, {"spotify_id": "../me/playlists"})
        self.assertRedirects(response, SEARCH)
        self.assertFalse(Song.objects.exists())

    def test_add_without_credentials(self):
        self.client.force_login(make_user(perms=FINDER))
        response = self.client.post(ADD, {"spotify_id": SPOTIFY_ID}, follow=True)
        self.assertContains(response, "SPOTIFY_CLIENT_ID")

    def test_needs_permission(self):
        self.client.force_login(make_user(perms=VIEWER))
        self.assertEqual(self.client.get(SEARCH).status_code, 403)
        self.assertEqual(
            self.client.post(ADD, {"spotify_id": SPOTIFY_ID}).status_code, 403
        )


class SongSettingsTests(SongsTestCase):
    def test_thirty_neutral_theme_tags_are_seeded(self):
        self.assertEqual(ThemeTag.objects.active().count(), 30)
        self.assertFalse(TrustedArtist.objects.exists())
        self.assertTrue(all(tag.keyword_set() for tag in ThemeTag.objects.all()))

    def test_tag_without_keywords_uses_its_name(self):
        self.assertEqual(ThemeTag(name="Lament").keyword_set(), {"lament"})

    def test_worship_leader_manages_tags_and_artists(self):
        leader = make_user(roles=["worship_leader"])
        self.client.force_login(leader)
        response = self.client.post(
            reverse("songs:trusted_artists_create"),
            {"name": "Grace Band", "description": "", "is_active": "on"},
        )
        self.assertRedirects(response, reverse("songs:trusted_artists_list"))
        self.assertTrue(TrustedArtist.objects.filter(name="Grace Band").exists())
        response = self.client.get(reverse("songs:theme_tags_list"))
        self.assertContains(response, "Adoration")
        self.assertContains(response, "Trusted artists")

    def test_team_member_cannot_open_the_song_settings(self):
        self.client.force_login(make_user(roles=["team_member"]))
        self.assertEqual(
            self.client.get(reverse("songs:theme_tags_list")).status_code, 403
        )


class DefaultRoleTests(SongsTestCase):
    def test_song_permissions_by_role(self):
        def has(role_key, perm):
            return (
                Role.objects.get(key=role_key)
                .permissions.filter(content_type__app_label="songs", codename=perm)
                .exists()
            )

        self.assertTrue(has("worship_leader", "change_song"))
        self.assertTrue(has("worship_leader", "add_trustedartist"))
        self.assertTrue(has("pastoral_staff", "view_song"))
        self.assertFalse(has("pastoral_staff", "change_song"))
        self.assertFalse(has("team_member", "view_song"))
        self.assertTrue(has("administrator", "change_themetag"))
