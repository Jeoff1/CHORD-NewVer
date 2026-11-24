"""The service page (Phase 9A, A7, part 3): the step bar, the next step's
card first, and who sees what."""

from django.test import TestCase
from django.urls import reverse

from apps.core.testing import (
    complete_setup,
    make_assignment,
    make_lineup,
    make_service,
    make_song,
    make_team_part,
    make_theme,
    make_user,
)


class ServiceScreenTests(TestCase):
    def setUp(self):
        complete_setup()
        self.pastor = make_user(roles=["pastoral_staff"])
        self.service = make_service(name="Sunday gathering")
        self.url = reverse(
            "worship:service", kwargs={"public_id": self.service.public_id}
        )

    def test_no_theme_yet_puts_the_theme_first(self):
        self.client.force_login(self.pastor)
        page = self.client.get(self.url)
        self.assertContains(page, 'aria-label="Planning steps"')
        self.assertContains(page, 'aria-current="step"')
        content = page.content.decode()
        current = content[content.index('aria-current="step"') :]
        self.assertIn("Theme", current[:400])
        self.assertIn("Not posted", current[:400])

    def test_a_draft_lineup_is_the_next_step_and_comes_first(self):
        make_theme(self.service, title="Grace that forgives", notes="Outline here")
        make_lineup(self.service, [make_song(title="Opening song")], confirmed=False)
        self.client.force_login(self.pastor)
        page = self.client.get(self.url)
        content = page.content.decode()
        current = content[content.index('aria-current="step"') :][:400]
        self.assertIn("Lineup", current)
        self.assertIn("Draft, to review", current)
        self.assertEqual(content.count("is-done"), 2)  # Theme, Suggestions
        self.assertContains(page, "Next step: review and confirm.")
        self.assertContains(page, ">Review and confirm</a>")
        self.assertLess(content.index('id="lineup"'), content.index('id="theme-title"'))
        self.assertContains(page, "<details")
        self.assertContains(page, "Outline here")

    def test_the_team_sees_no_step_bar_no_draft_and_no_notes(self):
        make_theme(self.service, notes="Outline here")
        make_lineup(self.service, [make_song()], confirmed=False)
        member = make_user(roles=["team_member"])
        self.client.force_login(member)
        page = self.client.get(self.url)
        self.assertNotContains(page, "Planning steps")
        self.assertNotContains(page, "Review and confirm")
        self.assertNotContains(page, "Outline here")

    def test_edit_is_the_primary_button_for_people_who_may_edit(self):
        self.client.force_login(self.pastor)
        self.assertContains(self.client.get(self.url), ">Edit worship service</a>")
        self.client.force_login(make_user(roles=["team_member"]))
        page = self.client.get(self.url)
        self.assertNotContains(page, "Edit worship service")
        self.assertNotContains(page, ">More</button>")
        edit = reverse(
            "worship:service_update", kwargs={"public_id": self.service.public_id}
        )
        self.assertEqual(self.client.get(edit).status_code, 403)

    def test_the_team_card_counts_and_shows_pills(self):
        part = make_team_part()
        make_assignment(
            self.service,
            make_user(first_name="Jo", last_name="Tan"),
            part,
            reply="accepted",
        )
        make_assignment(self.service, make_user(first_name="Mia", last_name="Go"), part)
        self.client.force_login(self.pastor)
        page = self.client.get(self.url)
        self.assertContains(page, "1 of 2 accepted")
        self.assertContains(page, 'class="chord-pill chord-pill--success">Accepted')
        self.assertContains(page, 'class="chord-pill chord-pill--warning">Pending')

    def test_details_and_headcount(self):
        self.client.force_login(self.pastor)
        page = self.client.get(self.url)
        self.assertContains(page, "Recorded after the worship service.")
        self.assertContains(page, ">People</label>")
        self.assertContains(page, 'class="chord-back-link"')
        self.assertContains(page, "Back to Worship Services")
