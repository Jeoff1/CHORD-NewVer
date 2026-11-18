import re

from django.core import mail
from django.test import TestCase
from django.urls import reverse

from apps.audit.models import AuditEvent
from apps.core.testing import TEST_PASSWORD, make_user

NEW_PASSWORD = "Fresh-pass-5520"


class ProfileTests(TestCase):
    def test_edit_own_profile(self):
        user = make_user(first_name="Ana")
        self.client.force_login(user)
        response = self.client.post(
            reverse("accounts:profile"),
            {"first_name": "Anna", "last_name": "Reyes", "email": "anna@example.com"},
        )
        self.assertRedirects(response, reverse("accounts:profile"))
        user.refresh_from_db()
        self.assertEqual(user.get_full_name(), "Anna Reyes")
        self.assertEqual(
            AuditEvent.objects.get().changes["First name"], ["Ana", "Anna"]
        )

    def test_requires_sign_in(self):
        response = self.client.get(reverse("accounts:profile"))
        self.assertEqual(response.status_code, 302)


class PasswordChangeTests(TestCase):
    def test_change_password(self):
        user = make_user()
        self.client.force_login(user)
        response = self.client.post(
            reverse("accounts:password_change"),
            {
                "old_password": TEST_PASSWORD,
                "new_password1": NEW_PASSWORD,
                "new_password2": NEW_PASSWORD,
            },
        )
        self.assertRedirects(response, reverse("accounts:profile"))
        user.refresh_from_db()
        self.assertTrue(user.check_password(NEW_PASSWORD))
        self.assertNotIn(NEW_PASSWORD, str(AuditEvent.objects.get().changes))


class PasswordResetTests(TestCase):
    def test_full_reset_flow(self):
        user = make_user(email="ana@example.com")
        response = self.client.post(
            reverse("accounts:password_reset"), {"email": "ana@example.com"}
        )
        self.assertRedirects(response, reverse("accounts:password_reset_done"))
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].subject, "Set a new CHORD password")
        link = re.search(r"http://testserver(\S+)", mail.outbox[0].body).group(1)

        response = self.client.get(link, follow=True)
        self.assertContains(response, "Set a new password")
        response = self.client.post(
            response.redirect_chain[-1][0],
            {"new_password1": NEW_PASSWORD, "new_password2": NEW_PASSWORD},
        )
        self.assertRedirects(response, reverse("accounts:password_reset_complete"))
        user.refresh_from_db()
        self.assertTrue(user.check_password(NEW_PASSWORD))

    def test_unknown_email_sends_nothing_but_looks_the_same(self):
        response = self.client.post(
            reverse("accounts:password_reset"), {"email": "nobody@example.com"}
        )
        self.assertRedirects(response, reverse("accounts:password_reset_done"))
        self.assertEqual(len(mail.outbox), 0)

    def test_bad_link_explains_itself(self):
        url = reverse(
            "accounts:password_reset_confirm",
            kwargs={"uidb64": "MQ", "token": "bad-token"},
        )
        self.assertContains(self.client.get(url), "This link doesn't work")
