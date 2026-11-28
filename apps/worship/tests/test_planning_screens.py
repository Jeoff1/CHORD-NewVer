"""UI/UX Phase 5 (28 Nov 2026): worship planning, suggestions and the lineup builder. UI-UX-Master-Plan.md
§11. Layout only: every action, permission and rule is tested where it lives."""

from django.contrib.staticfiles import finders
from django.test import TestCase
from django.urls import reverse

from apps.core.testing import (
    complete_setup,
    make_lineup,
    make_service,
    make_song,
    make_user,
)


def url(service, name):
    return reverse(f"worship:{name}", kwargs={"public_id": service.public_id})


class PlanningScreenTests(TestCase):
    def setUp(self):
        complete_setup()
        self.service = make_service(name="Sunday gathering")
        self.lineup = make_lineup(
            self.service,
            [make_song(title="First song"), make_song(title="Second song")],
            confirmed=False,
        )
        self.leader = make_user(roles=["worship_leader"])
        self.client.force_login(self.leader)

    def test_the_planning_stylesheet_is_loaded(self):
        page = self.client.get(reverse("worship:home"))
        self.assertContains(page, "css/planning.css")
        self.assertTrue(finders.find("css/planning.css"))

    def test_the_service_list_has_date_tiles_and_whole_row_links(self):
        page = self.client.get(reverse("worship:home"))
        self.assertContains(page, 'class="chord-seg"')
        self.assertContains(page, f'data-href="{url(self.service, "service")}"')
        self.assertContains(page, "chord-date__day")

    def test_an_empty_search_says_so(self):
        page = self.client.get(reverse("worship:home"), {"q": "zzzz"})
        self.assertContains(page, "chord-empty")
        self.assertContains(page, "Nothing matches your search.")

    def test_the_lineup_shows_its_count_and_row_anchors(self):
        page = self.client.get(url(self.service, "lineup"))
        self.assertContains(page, 'class="chord-lineup-count"')
        self.assertContains(page, ">2</span>")
        item = self.lineup.items.order_by("position").first()
        self.assertContains(page, f'id="item-{item.pk}"')

    def test_the_rundown_numbers_the_songs(self):
        page = self.client.get(url(self.service, "lineup_confirm"))
        self.assertContains(page, 'class="chord-rundown"')
        self.assertContains(page, "First song")
