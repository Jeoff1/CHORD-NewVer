"""The lineup page (Phase 9A, A7, part 3): Confirm on top, the rest under
More, and song rows with move, lock and a menu. Every moved action keeps
its permission."""

from django.test import TestCase
from django.urls import reverse

from apps.core.testing import (
    complete_setup,
    make_lineup,
    make_service,
    make_song,
    make_user,
)


def url(service, name, **kwargs):
    return reverse(f"worship:{name}", kwargs={"public_id": service.public_id, **kwargs})


class LineupScreenTests(TestCase):
    def setUp(self):
        complete_setup()
        self.service = make_service(name="Sunday gathering")
        self.lineup = make_lineup(
            self.service,
            [make_song(title="First song"), make_song(title="Second song")],
            confirmed=False,
        )
        self.items = list(self.lineup.items.order_by("position"))
        self.leader = make_user(roles=["worship_leader"])
        self.pastor = make_user(roles=["pastoral_staff"])
        self.member = make_user(roles=["team_member"])

    def test_the_leader_gets_confirm_more_and_song_rows(self):
        self.client.force_login(self.leader)
        page = self.client.get(url(self.service, "lineup"))
        self.assertContains(page, ">Confirm lineup</button>")
        self.assertContains(page, ">More</button>")
        self.assertContains(page, "Regenerate around locked songs")
        self.assertNotContains(page, "Send back to the worship leader")
        self.assertContains(page, 'aria-label="Move Second song up"')
        self.assertContains(page, 'aria-label="Move First song down"')
        self.assertContains(page, 'aria-label="Lock First song"')
        self.assertContains(page, 'aria-pressed="false"')
        self.assertContains(page, 'aria-label="More for First song"')
        self.assertContains(page, ">Swap with a suggestion</a>")
        self.assertContains(page, ">Key and notes</a>")
        self.assertContains(page, ">Open the song page</a>")
        self.assertContains(page, ">Remove from the lineup</button>")
        self.assertContains(page, ">Add a song from the pool</a>")
        self.assertContains(page, "Saved when the lineup is confirmed.")

    def test_the_pastor_also_gets_send_back(self):
        self.client.force_login(self.pastor)
        page = self.client.get(url(self.service, "lineup"))
        self.assertContains(page, ">Send back to the worship leader</a>")

    def test_a_locked_song_has_no_swap_or_remove(self):
        item = self.items[0]
        item.locked = True
        item.save()
        self.client.force_login(self.leader)
        page = self.client.get(url(self.service, "lineup"))
        self.assertContains(page, 'aria-pressed="true"')
        content = page.content.decode()
        menu = content[content.index('aria-label="More for First song"') :]
        menu = menu[: menu.index("</ul>")]
        self.assertNotIn("Swap with a suggestion", menu)
        self.assertNotIn("Remove from", menu)

    def test_the_team_sees_a_confirmed_lineup_without_any_controls(self):
        self.lineup.status = "confirmed"
        self.lineup.save()
        self.client.force_login(self.member)
        page = self.client.get(url(self.service, "lineup"))
        self.assertContains(page, "First song")
        for text in (
            "Confirm lineup",
            ">More</button>",
            "Send back",
            "Regenerate",
            "More for First song",
            "Lock First song",
            "Add a song from the pool",
        ):
            with self.subTest(text):
                self.assertNotContains(page, text)

    def test_moved_actions_still_refuse_people_without_the_permission(self):
        self.client.force_login(self.member)
        item = self.items[0]
        posts = [
            url(self.service, "lineup_confirm"),
            url(self.service, "lineup_regenerate"),
            url(self.service, "lineup_reopen"),
            url(self.service, "lineup_item_action", pk=item.pk, action="lock"),
            url(self.service, "lineup_item_action", pk=item.pk, action="remove"),
            url(self.service, "lineup_item_action", pk=item.pk, action="up"),
        ]
        for address in posts:
            with self.subTest(address):
                self.assertEqual(self.client.post(address).status_code, 403)
        for address in (
            url(self.service, "lineup_send_back"),
            url(self.service, "lineup_swap", pk=item.pk),
            url(self.service, "lineup_item", pk=item.pk),
            url(self.service, "lineup_add"),
        ):
            with self.subTest(address):
                self.assertEqual(self.client.get(address).status_code, 403)
        self.client.force_login(self.leader)
        self.assertEqual(
            self.client.get(url(self.service, "lineup_send_back")).status_code, 403
        )
