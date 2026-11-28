"""The owner's design system and the Spotify player card (Phase 9A, A7,
part 2; Design-Decisions, "Adviser comments, 24 Nov", A7)."""

from django.contrib.staticfiles import finders
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.core.testing import (
    SPOTIFY_TEST_SETTINGS,
    complete_setup,
    make_lineup,
    make_service,
    make_song,
    make_spotify_connection,
    make_user,
)


@override_settings(**SPOTIFY_TEST_SETTINGS)
class PlayerCardTests(TestCase):
    """The lineup song page's "Listen" card, in each of its three states."""

    def setUp(self):
        complete_setup()
        self.member = make_user(roles=["team_member"])
        self.song = make_song(
            title="Made Up Song",
            artist="Invented Artist",
            spotify_id="trackEEEEEEEEEEEEEEEEE",
            length_seconds=272,
        )
        self.lineup = make_lineup(make_service(), [self.song])
        item = self.lineup.items.get()
        self.url = reverse(
            "worship:lineup_song",
            kwargs={"public_id": self.lineup.service.public_id, "pk": item.pk},
        )

    def test_a_connected_user_gets_the_full_player_card(self):
        make_spotify_connection(self.member, access="never-on-the-page")
        self.client.force_login(self.member)
        page = self.client.get(self.url)
        self.assertContains(page, 'class="chord-player"')
        self.assertContains(page, "data-spotify-player")
        # Title and artist come from CHORD's own Song record.
        self.assertContains(
            page, '<p class="chord-player__song-title">Made Up Song</p>'
        )
        self.assertContains(page, '<p class="chord-player__artist">Invented Artist</p>')
        # The stored length until the SDK reports one.
        self.assertContains(page, 'data-length-ms="272000"')
        self.assertContains(page, "<span data-player-total>4:32</span>")
        self.assertContains(page, 'role="progressbar"')
        self.assertContains(page, 'aria-label="Back 10 seconds"')
        self.assertContains(page, 'aria-label="Play"')
        self.assertContains(page, 'aria-label="Forward 10 seconds"')
        self.assertContains(page, 'role="status"')
        # The embedded player waits, hidden, inside the same card.
        self.assertContains(page, "data-player-fallback hidden")
        self.assertNotContains(page, "never-on-the-page")
        self.assertNotContains(page, "No playback for this song")

    def test_without_a_connection_the_embedded_player_sits_in_the_card(self):
        self.client.force_login(self.member)
        page = self.client.get(self.url)
        content = page.content.decode()
        card = content[content.index('class="chord-player"') :]
        card = card[: card.index("</section>")]
        self.assertIn('src="https://open.spotify.com/embed/track/trackEEEE', card)
        self.assertIn("Open in Spotify", card)
        self.assertIn("Connect your Spotify account", card)
        self.assertNotContains(page, "data-spotify-player")

    def test_a_song_without_a_track_still_gets_the_card(self):
        self.song.spotify_id = ""
        self.song.save()
        pastor = make_user(roles=["pastoral_staff"])
        for person in (self.member, pastor):
            self.client.force_login(person)
            with self.subTest(person=person.username):
                page = self.client.get(self.url)
                self.assertContains(page, 'class="chord-player"')
                self.assertContains(page, "No playback for this song")
                self.assertContains(page, "The chord sheet still works without it.")
                # CHORD has no page that links an existing song to a track,
                # so nobody gets a link to fix it.
                self.assertNotContains(page, "Link a Spotify track")
                self.assertNotContains(page, "open.spotify.com/embed")

    def test_the_player_keeps_the_phase_7_safeguards(self):
        with open(finders.find("songs/player.js"), encoding="utf-8") as script:
            source = script.read()
        self.assertIn("reply.status === 429", source)
        self.assertIn("READY_TIMEOUT_MS = 15000", source)
        self.assertIn("player.seek(", source)
        self.assertIn('"player_state_changed"', source)
        self.assertIn("document.hidden", source)
        # The cover stays in the browser: nothing is sent back to CHORD
        # except the token request.
        self.assertEqual(source.count("fetch("), 2)
        self.assertNotIn("localStorage", source)
        self.assertNotIn("console.", source)


class ThemeTests(TestCase):
    def setUp(self):
        complete_setup()

    def test_every_page_loads_the_theme_and_follows_the_device(self):
        self.client.force_login(make_user(roles=["church_member"]))
        page = self.client.get(reverse("home"))
        self.assertContains(page, "css/chord.css")
        self.assertContains(page, "prefers-color-scheme: dark")
        self.assertContains(page, "data-bs-theme")
        self.assertNotContains(page, "bg-body-tertiary")
        self.assertTrue(finders.find("css/chord.css"))
        for name in ("raleway-latin.woff2", "fira-sans-condensed-400-latin.woff2"):
            self.assertTrue(finders.find(f"vendor/fonts/{name}"), name)
        self.assertTrue(finders.find("vendor/fonts/OFL-Raleway.txt"))

    def test_the_avatar_shows_the_initials_of_the_name(self):
        # UI/UX Phase 2: first and last initials, else the username's first letter.
        self.client.force_login(
            make_user(roles=["church_member"], first_name="rosa", last_name="Lim")
        )
        page = self.client.get(reverse("home"))
        self.assertContains(page, "data-account-initials>RL</span>")
        self.assertContains(page, "data-account-name>rosa Lim</span>")
        self.client.force_login(make_user(username="zed", roles=["church_member"]))
        page = self.client.get(reverse("home"))
        self.assertContains(page, "data-account-initials>Z</span>")
        self.assertContains(page, "data-account-name>zed</span>")

    def test_back_links_are_the_shared_pill(self):
        self.client.force_login(make_user(roles=["pastoral_staff"]))
        service = make_service()
        page = self.client.get(
            reverse("worship:service", kwargs={"public_id": service.public_id})
        )
        self.assertContains(
            page, f'<a href="{reverse("worship:home")}" class="chord-back-link">'
        )
        self.assertNotContains(page, "←")
