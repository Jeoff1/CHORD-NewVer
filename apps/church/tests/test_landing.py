"""The landing page: what a visitor who isn't signed in sees at the home
address. Since Phase 9B it is the platform's page, not one church's
(decision 0014): it offers every Module and uses the neutral wording."""

from django.test import TestCase
from django.urls import reverse

from apps.core.testing import complete_setup, make_user

HOME = reverse("home")


class LandingPageTests(TestCase):
    def test_a_visitor_sees_the_landing_page_with_a_way_to_sign_in(self):
        complete_setup(name="Grace Fellowship")
        response = self.client.get(HOME)
        self.assertTemplateUsed(response, "church/landing.html")
        self.assertContains(response, f'href="{reverse("accounts:login")}"')
        # The platform's page names no church.
        self.assertNotContains(response, "Grace Fellowship")
        self.assertContains(response, "Worship planning · CHORD")

    def test_a_signed_in_person_sees_the_dashboard(self):
        complete_setup()
        self.client.force_login(make_user())
        response = self.client.get(HOME)
        self.assertTemplateUsed(response, "church/dashboard.html")
        self.assertTemplateNotUsed(response, "church/landing.html")

    def test_the_wording_is_neutral_whatever_a_church_calls_things(self):
        complete_setup(
            labels={
                "pastor": {"singular": "Elder", "plural": "Elders"},
                "lineup": {"singular": "Set List", "plural": "Set Lists"},
            }
        )
        response = self.client.get(HOME)
        self.assertContains(response, "Your pastor reviews and confirms it")
        self.assertNotContains(response, "set list")

    def test_one_churchs_switched_off_modules_are_still_offered(self):
        complete_setup(disabled_modules=["teams", "occasions", "announcements"])
        response = self.client.get(HOME)
        self.assertContains(response, "Team roster")
        self.assertContains(response, "Calendar and occasions")
        self.assertContains(response, "Chord sheets in any key")

    def test_switched_on_modules_are_offered(self):
        complete_setup()
        response = self.client.get(HOME)
        self.assertContains(response, "Team roster")
        self.assertContains(response, "Calendar and occasions")
        self.assertContains(response, "<h3>Announcements</h3>", html=False)
