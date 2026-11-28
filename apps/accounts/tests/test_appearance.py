"""Each person's own light or dark mode (Phase 9A, A7): Settings ›
Personal › Appearance."""

from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.core.testing import complete_setup, make_user

APPEARANCE = reverse("accounts:appearance")


class AppearanceTests(TestCase):
    def setUp(self):
        complete_setup()
        self.person = make_user(roles=["church_member"])

    def test_by_default_the_page_follows_the_device(self):
        self.assertEqual(self.person.theme, User.Theme.DEVICE)
        self.client.force_login(self.person)
        page = self.client.get(reverse("home"))
        self.assertContains(page, 'var choice = "device"')
        self.assertContains(page, "prefers-color-scheme: dark")

    def test_choosing_dark_or_light_is_kept_and_applied(self):
        self.client.force_login(self.person)
        page = self.client.get(APPEARANCE)
        self.assertContains(page, "Match my device")
        self.assertContains(page, "chord-settings-menu")
        self.assertContains(page, "Personal")
        for choice in ("dark", "light", "device"):
            with self.subTest(choice):
                response = self.client.post(APPEARANCE, {"theme": choice})
                self.assertRedirects(response, APPEARANCE)
                self.person.refresh_from_db()
                self.assertEqual(self.person.theme, choice)
                self.assertContains(
                    self.client.get(reverse("home")), f'var choice = "{choice}"'
                )

    def test_a_choice_is_only_for_that_person(self):
        other = make_user()
        self.client.force_login(self.person)
        self.client.post(APPEARANCE, {"theme": "dark"})
        other.refresh_from_db()
        self.assertEqual(other.theme, User.Theme.DEVICE)

    def test_an_unknown_choice_is_refused(self):
        self.client.force_login(self.person)
        response = self.client.post(APPEARANCE, {"theme": "purple"})
        self.assertEqual(response.status_code, 200)
        self.person.refresh_from_db()
        self.assertEqual(self.person.theme, User.Theme.DEVICE)

    def test_signed_out_pages_follow_the_device(self):
        page = self.client.get(reverse("accounts:login"))
        self.assertContains(page, 'var choice = "device"')

    def test_signing_in_is_needed(self):
        response = self.client.get(APPEARANCE)
        self.assertEqual(response.status_code, 302)

    def test_account_settings_links_it(self):
        # UI/UX Phase 2: the popover's Account Settings, then Appearance.
        self.client.force_login(self.person)
        self.assertContains(self.client.get(reverse("home")), ">Account Settings</a>")
        self.assertContains(
            self.client.get(reverse("accounts:profile")), f'href="{APPEARANCE}"'
        )
