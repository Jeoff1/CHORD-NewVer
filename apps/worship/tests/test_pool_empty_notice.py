"""The empty-pool pop-up on the Song Lineup page: a church whose song pool
has nothing to suggest is told that Find songs (Spotify) fills it. It is a
modal over the page, never part of it."""

from django.test import TestCase, override_settings
from django.urls import reverse

from apps.core.testing import (
    complete_setup,
    make_search_run,
    make_service,
    make_song,
    make_theme,
    make_user,
)
from apps.songs.models import Song
from apps.worship import suggesting
from apps.worship.models import SearchRun

SPOTIFY_KEYS = {"SPOTIFY_CLIENT_ID": "id", "SPOTIFY_CLIENT_SECRET": "secret"}
MODAL = 'id="pool-empty-modal"'


class PoolIsEmptyTests(TestCase):
    def setUp(self):
        self.church = complete_setup()

    def test_a_church_without_songs_has_an_empty_pool(self):
        self.assertTrue(suggesting.pool_is_empty(self.church))

    def test_a_song_that_passed_the_worship_check_fills_it(self):
        make_song(worship_check=Song.WorshipCheck.ACCEPTED)
        self.assertFalse(suggesting.pool_is_empty(self.church))

    def test_songs_still_being_checked_count_as_coming(self):
        make_song(lyrics_status=Song.LyricsStatus.PENDING)
        self.assertFalse(suggesting.pool_is_empty(self.church))

    def test_songs_found_but_not_analysed_count_as_coming(self):
        make_song(lyrics_status=Song.LyricsStatus.FOUND)
        self.assertFalse(suggesting.pool_is_empty(self.church))

    def test_only_rejected_or_lyricless_songs_leave_it_empty(self):
        make_song(
            lyrics_status=Song.LyricsStatus.MISSING,
            worship_check=Song.WorshipCheck.REJECTED,
        )
        self.assertTrue(suggesting.pool_is_empty(self.church))


@override_settings(**SPOTIFY_KEYS)
class PoolEmptyModalTests(TestCase):
    def setUp(self):
        complete_setup()
        self.service = make_service()
        self.pastor = make_user(roles=["pastoral_staff"])
        self.url = reverse(
            "worship:lineup", kwargs={"public_id": self.service.public_id}
        )

    def page(self, user=None):
        self.client.force_login(user or self.pastor)
        return self.client.get(self.url)

    def test_the_pastor_sees_it_with_find_songs_once_the_theme_is_posted(self):
        make_theme(self.service, notes="The message in a few sentences.")
        response = self.page()
        self.assertContains(response, MODAL)
        self.assertContains(response, "Your song pool is empty")
        self.assertContains(response, 'class="modal fade"')
        self.assertContains(
            response,
            f'action="{reverse("worship:suggest", kwargs={"public_id": self.service.public_id})}"',
        )
        self.assertContains(
            response, 'value="spotify" class="btn btn-primary">Find songs'
        )

    def test_without_a_theme_it_says_to_post_the_theme_first(self):
        response = self.page()
        self.assertContains(response, MODAL)
        self.assertContains(response, "post the theme first")
        self.assertContains(response, "Post the theme</a>")

    def test_without_spotify_it_says_spotify_isnt_available(self):
        make_theme(self.service, notes="The message.")
        with self.settings(SPOTIFY_CLIENT_ID="", SPOTIFY_CLIENT_SECRET=""):
            response = self.page()
        self.assertContains(response, MODAL)
        self.assertContains(response, "Spotify isn't available right now")
        self.assertNotContains(response, 'value="spotify" class="btn btn-primary"')

    def test_not_shown_when_the_pool_has_songs(self):
        make_song(worship_check=Song.WorshipCheck.ACCEPTED)
        self.assertNotContains(self.page(), MODAL)

    def test_not_shown_while_a_search_is_running(self):
        make_theme(self.service, notes="The message.")
        run = make_search_run(self.service, [])
        run.status = SearchRun.Status.RUNNING
        run.save(update_fields=["status"])
        self.assertNotContains(self.page(), MODAL)

    def test_not_shown_for_a_cancelled_service(self):
        self.service.is_cancelled = True
        self.service.save(update_fields=["is_cancelled"])
        self.assertNotContains(self.page(), MODAL)

    def test_not_shown_to_people_who_cant_suggest_songs(self):
        leader = make_user(roles=["team_member"])
        self.client.force_login(leader)
        response = self.client.get(self.url)
        self.assertNotContains(response, MODAL, status_code=response.status_code)
