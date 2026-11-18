from django.contrib.auth import SESSION_KEY
from django.test import TestCase
from django.urls import reverse

from apps.core.testing import TEST_PASSWORD, make_user


class SignInTests(TestCase):
    def test_sign_in_page_renders_styled_form(self):
        response = self.client.get(reverse("accounts:login"))
        self.assertContains(response, 'class="form-control"')

    def test_valid_credentials_sign_in(self):
        user = make_user()
        response = self.client.post(
            reverse("accounts:login"),
            {"username": user.username, "password": TEST_PASSWORD},
        )
        self.assertRedirects(response, reverse("home"))
        self.assertEqual(int(self.client.session[SESSION_KEY]), user.pk)

    def test_wrong_password_shows_error(self):
        user = make_user()
        response = self.client.post(
            reverse("accounts:login"),
            {"username": user.username, "password": "wrong"},
        )
        self.assertContains(response, 'class="alert alert-danger"')
        self.assertNotIn(SESSION_KEY, self.client.session)

    def test_signed_in_user_skips_sign_in_page(self):
        self.client.force_login(make_user())
        response = self.client.get(reverse("accounts:login"))
        self.assertRedirects(response, reverse("home"))

    def test_sign_out_requires_post(self):
        self.client.force_login(make_user())
        self.assertEqual(self.client.get(reverse("accounts:logout")).status_code, 405)
        response = self.client.post(reverse("accounts:logout"))
        self.assertRedirects(response, reverse("accounts:login"))
        self.assertNotIn(SESSION_KEY, self.client.session)
