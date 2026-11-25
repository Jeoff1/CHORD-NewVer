from django.contrib.staticfiles import finders
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from apps.core.testing import make_user


class HomePageTests(TestCase):
    def test_a_visitor_sees_the_landing_page_and_signs_in_for_the_rest(self):
        response = self.client.get(reverse("home"))
        self.assertTemplateUsed(response, "church/landing.html")
        url = reverse("worship:home")
        response = self.client.get(url)
        self.assertRedirects(response, f"{reverse('accounts:login')}?next={url}")

    def test_signed_in_user_sees_base_page(self):
        self.client.force_login(make_user(first_name="Ana"))
        response = self.client.get(reverse("home"))
        self.assertContains(response, "Welcome, Ana.")
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
