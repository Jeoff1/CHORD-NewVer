"""The lineup song page (Phase 9A, A7, part 3): Previous and Next through
the lineup, the sheet's one toolbar, and the side column."""

from django.test import TestCase
from django.urls import reverse

from apps.core.testing import (
    complete_setup,
    make_chord_sheet,
    make_lineup,
    make_service,
    make_song,
    make_user,
)


class LineupSongScreenTests(TestCase):
    def setUp(self):
        complete_setup()
        self.service = make_service(name="Sunday gathering")
        songs = [make_song(title=title) for title in ("Alpha", "Beta", "Gamma")]
        self.lineup = make_lineup(self.service, songs, keys=("D", "G", "C"))
        self.items = list(self.lineup.items.order_by("position", "pk"))
        self.client.force_login(make_user(roles=["team_member"]))

    def page(self, item):
        return self.client.get(
            reverse(
                "worship:lineup_song",
                kwargs={"public_id": self.service.public_id, "pk": item.pk},
            )
        )

    def song_url(self, item):
        return reverse(
            "worship:lineup_song",
            kwargs={"public_id": self.service.public_id, "pk": item.pk},
        )

    def test_previous_and_next_follow_the_lineup_order(self):
        page = self.page(self.items[1])
        self.assertContains(page, "song 2 of 3")
        content = page.content.decode()
        self.assertIn(f'href="{self.song_url(self.items[0])}" class="btn', content)
        self.assertIn(f'href="{self.song_url(self.items[2])}" class="btn', content)

    def test_the_first_and_last_songs_disable_their_ends(self):
        first = self.page(self.items[0]).content.decode()
        self.assertIn("disabled>", first[: first.index("Previous song") + 300])
        self.assertIn(f'href="{self.song_url(self.items[1])}" class="btn', first)
        last = self.page(self.items[2]).content.decode()
        nxt = last.index("Next song")
        self.assertIn("disabled", last[nxt - 200 : nxt])

    def test_the_side_column(self):
        item = self.items[0]
        item.notes = "Piano alone first"
        item.save()
        page = self.page(item)
        self.assertContains(page, 'id="listen"')
        self.assertContains(page, "Notes for the team")
        self.assertContains(page, "Piano alone first")
        self.assertContains(
            page, '<li aria-current="true"><strong>Alpha</strong> · D</li>'
        )
        self.assertContains(page, ">Beta</a> · G")
        self.assertContains(page, "Back to Lineup")

    def test_the_sheet_toolbar(self):
        make_chord_sheet(self.items[1].song)
        page = self.page(self.items[1])
        self.assertContains(page, 'aria-label="Sheet options"')
        self.assertContains(page, "Service key")
        self.assertContains(page, ">My key</label>")
        self.assertContains(page, 'aria-label="Down a semitone">−</a>')
        self.assertContains(page, 'aria-label="Up a semitone">+</a>')
        self.assertContains(page, "Capo")
