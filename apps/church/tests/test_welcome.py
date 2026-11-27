"""Registering a church goes straight to the dashboard (owner, 27 Nov 2026):
the church is set up when its values pass the model's checks, starts in the
person's time zone, and the dashboard welcomes them once with a toast."""

from unittest import mock

from django.contrib.auth import SESSION_KEY as USER_KEY
from django.contrib.staticfiles import finders
from django.test import TestCase
from django.urls import reverse

from apps.church.middleware import SESSION_KEY
from apps.church.models import ChurchProfile
from apps.church.views import WELCOME_MESSAGE, showcase_churches
from apps.core.testing import TEST_PASSWORD, complete_setup, make_user

REGISTER = reverse("churches:register")
HOME = reverse("home")
ACCOUNT = {
    "first_name": "Ruth",
    "last_name": "Ann",
    "email": "ruth@example.com",
    "password1": "a-Long-pass-8472",
    "password2": "a-Long-pass-8472",
}
TITLE = "Welcome to CHORD!"


class RegistrationToDashboardTests(TestCase):
    def setUp(self):
        complete_setup()

    def register(self, **church):
        data = {**ACCOUNT, "church-name": "Grace Chapel", **church}
        return self.client.post(REGISTER, data)

    def test_the_new_administrator_is_signed_in_and_sent_to_the_dashboard(self):
        response = self.register()
        self.assertRedirects(response, HOME, fetch_redirect_response=False)
        church = ChurchProfile.objects.get(name="Grace Chapel")
        self.assertTrue(church.setup_completed)
        self.assertEqual(self.client.session[SESSION_KEY], church.pk)
        self.assertIn(USER_KEY, self.client.session)
        dashboard = self.client.get(HOME)
        self.assertTemplateUsed(dashboard, "church/dashboard.html")
        self.assertTemplateNotUsed(dashboard, "church/profile_section.html")

    def test_the_welcome_shows_once_under_the_navigation_bar(self):
        self.register()
        dashboard = self.client.get(HOME)
        self.assertTemplateUsed(dashboard, "includes/welcome_toast.html")
        self.assertContains(dashboard, TITLE, count=1)
        self.assertContains(dashboard, WELCOME_MESSAGE, count=1)
        self.assertContains(dashboard, 'role="status" aria-live="polite"')
        self.assertContains(dashboard, 'data-chord-toast-ms="5000"')
        self.assertContains(dashboard, 'aria-label="Dismiss the welcome message"')
        self.assertContains(dashboard, "js/welcome-toast.js")
        content = dashboard.content.decode()
        # Right after the navigation bar, before the page; never also as an alert.
        self.assertLess(content.index("</nav>"), content.index("chord-toast-region"))
        self.assertLess(content.index("chord-toast-region"), content.index("<main"))
        self.assertNotIn("alert alert-success", content)
        # Refreshing the page doesn't show it again.
        again = self.client.get(HOME)
        self.assertNotContains(again, TITLE)
        self.assertTemplateNotUsed(again, "includes/welcome_toast.html")

    def test_signing_in_normally_never_shows_it(self):
        self.register()
        self.client.get(HOME)
        self.client.logout()
        self.client.post(
            reverse("accounts:login"),
            {"username": ACCOUNT["email"], "password": ACCOUNT["password1"]},
        )
        self.assertNotContains(self.client.get(HOME), TITLE)
        other = make_user()
        self.client.logout()
        self.client.post(
            reverse("accounts:login"),
            {"username": other.username, "password": TEST_PASSWORD},
        )
        self.assertNotContains(self.client.get(HOME), TITLE)

    def test_the_church_starts_in_the_devices_time_zone(self):
        self.register(**{"church-time_zone": "Europe/Berlin"})
        self.assertEqual(
            ChurchProfile.objects.get(name="Grace Chapel").time_zone, "Europe/Berlin"
        )

    def test_an_unknown_or_missing_time_zone_keeps_the_default(self):
        default = ChurchProfile._meta.get_field("time_zone").default
        self.register(**{"church-time_zone": "Mars/Olympus"})
        self.assertEqual(
            ChurchProfile.objects.get(name="Grace Chapel").time_zone, default
        )
        self.client.logout()
        self.client.post(
            REGISTER,
            {**ACCOUNT, "email": "two@example.com", "church-name": "Hope Hall"},
        )
        self.assertEqual(ChurchProfile.objects.get(name="Hope Hall").time_zone, default)

    def test_the_registration_page_sends_the_time_zone(self):
        response = self.client.get(REGISTER)
        self.assertContains(response, 'name="church-time_zone"')
        self.assertContains(response, "data-au-time-zone")

    def test_a_church_missing_something_still_goes_to_the_dashboard(self):
        # No setup wizard any more (owner, 27 Nov 2026): the dashboard says
        # what to check, with the welcome.
        with mock.patch(
            "apps.church.registration.setup_requirements_met", return_value=False
        ):
            response = self.register()
            self.assertRedirects(response, HOME, fetch_redirect_response=False)
            page = self.client.get(HOME)
        church = ChurchProfile.objects.get(name="Grace Chapel")
        self.assertFalse(church.setup_completed)
        self.assertContains(page, TITLE)
        self.assertContains(page, "need checking before it can be listed")

    def test_sending_the_same_form_again_goes_to_the_dashboard_without_a_second_church(
        self,
    ):
        self.client.get(REGISTER)
        token = self.client.session["church_registration_token"]
        data = {**ACCOUNT, "church-name": "Grace Chapel", "registration": token}
        self.client.post(REGISTER, data)
        again = self.client.post(REGISTER, data)
        self.assertRedirects(again, HOME, fetch_redirect_response=False)
        self.assertEqual(ChurchProfile.objects.filter(name="Grace Chapel").count(), 1)

    def test_a_public_registered_church_can_be_showcased(self):
        self.register()
        church = ChurchProfile.objects.get(name="Grace Chapel")
        self.assertTrue(church.show_in_directory)
        self.assertIn(church, list(showcase_churches()))

    def test_its_script_and_styles_exist(self):
        self.assertTrue(finders.find("js/welcome-toast.js"))
        css = open(finders.find("css/chord.css"), encoding="utf-8").read()
        for rule in (
            ".chord-toast-region",
            "@keyframes chord-toast-in",
            "chord-toast-count",
            "prefers-reduced-motion",
        ):
            self.assertIn(rule, css)
