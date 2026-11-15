from django.contrib.staticfiles import finders
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from apps.core.testing import make_user


class HomePageTests(TestCase):
    def test_anonymous_user_is_sent_to_sign_in(self):
        response = self.client.get(reverse("core:home"))
        self.assertRedirects(response, reverse("accounts:login") + "?next=/")

    def test_signed_in_user_sees_base_page(self):
        self.client.force_login(make_user(first_name="Ana"))
        response = self.client.get(reverse("core:home"))
        self.assertContains(response, "Welcome, Ana")
        self.assertContains(response, "Sign out")
        self.assertContains(response, "vendor/htmx-2.0.4/htmx.min.js")
        self.assertContains(response, "vendor/bootstrap-5.3.3/bootstrap.min.css")


class VendorFilesTests(SimpleTestCase):
    def test_vendor_files_are_found(self):
        for path in (
            "vendor/bootstrap-5.3.3/bootstrap.min.css",
            "vendor/bootstrap-5.3.3/bootstrap.bundle.min.js",
            "vendor/htmx-2.0.4/htmx.min.js",
        ):
            with self.subTest(path=path):
                self.assertIsNotNone(finders.find(path))
