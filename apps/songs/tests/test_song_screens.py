"""UI/UX Phase 6 (28 Nov 2026): songs, chord sheets and rehearsal screens. UI-UX-Master-Plan.md §12.
Layout only; no album art (only the allowed Spotify fields are stored)."""

from django.test import TestCase
from django.urls import reverse

from apps.core.testing import complete_setup, make_administrator, make_song


class SongScreenTests(TestCase):
    def setUp(self):
        complete_setup()
        self.client.force_login(make_administrator())

    def test_the_pool_has_tiles_whole_row_links_and_folded_filters(self):
        song = make_song(title="Amazing grace")
        page = self.client.get(reverse("songs:list"))
        self.assertContains(page, '<details class="chord-filters">')
        self.assertContains(page, '<span class="chord-art" aria-hidden="true">A</span>')
        self.assertContains(
            page,
            f'data-href="{reverse("songs:detail", kwargs={"public_id": song.public_id})}"',
        )
        self.assertNotContains(page, "badge text-bg")

    def test_a_chosen_filter_opens_the_panel(self):
        page = self.client.get(reverse("songs:list"), {"feel": "upbeat"})
        self.assertContains(page, '<details class="chord-filters" open>')

    def test_an_empty_pool_offers_find_on_spotify(self):
        page = self.client.get(reverse("songs:list"))
        self.assertContains(page, "chord-empty")
        self.assertContains(page, "The song pool is empty")

    def test_the_song_page_has_a_large_tile(self):
        song = make_song(title="Be thou my vision")
        page = self.client.get(
            reverse("songs:detail", kwargs={"public_id": song.public_id})
        )
        self.assertContains(page, "chord-art chord-art--lg")
        self.assertContains(page, "chord-pill")

    def test_find_on_spotify_has_the_big_search(self):
        page = self.client.get(reverse("songs:spotify_search"))
        self.assertContains(page, "chord-big-search")
