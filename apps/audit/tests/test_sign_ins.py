"""User history (Phase 9A, A3; Design-Decisions, "Adviser comments, 24
Nov"): sign-ins, sign-outs and failed sign-ins in the Audit Trail, and a
History page for each user."""

from django.test import TestCase
from django.urls import reverse

from apps.audit.models import AuditEvent, SignInEvent
from apps.core.testing import (
    TEST_PASSWORD,
    complete_setup,
    make_administrator,
    make_user,
)

LOGIN = reverse("accounts:login")
WRONG_PASSWORD = "not-the-password-9"


class SignInEventTests(TestCase):
    def setUp(self):
        complete_setup()
        self.user = make_user(username="rosa")

    def sign_in(self, username, password):
        return self.client.post(LOGIN, {"username": username, "password": password})

    def test_signing_in_is_recorded(self):
        self.sign_in("rosa", TEST_PASSWORD)
        event = SignInEvent.objects.get()
        self.assertEqual(event.kind, SignInEvent.Kind.SIGNED_IN)
        self.assertEqual(event.user, self.user)
        self.assertEqual(event.username, "rosa")

    def test_signing_out_is_recorded(self):
        self.sign_in("rosa", TEST_PASSWORD)
        self.client.post(reverse("accounts:logout"))
        self.assertEqual(
            list(SignInEvent.objects.values_list("kind", flat=True)),
            [SignInEvent.Kind.SIGNED_OUT, SignInEvent.Kind.SIGNED_IN],
        )

    def test_failed_sign_in_keeps_the_username_never_the_password(self):
        self.sign_in("rosa", WRONG_PASSWORD)
        event = SignInEvent.objects.get()
        self.assertEqual(event.kind, SignInEvent.Kind.FAILED)
        self.assertEqual(event.user, self.user)
        self.assertEqual(event.username, "rosa")
        stored = [str(v) for v in SignInEvent.objects.values().get().values()]
        self.assertNotIn(WRONG_PASSWORD, " ".join(stored))

    def test_failed_sign_in_with_an_unknown_username(self):
        self.sign_in("nobody", WRONG_PASSWORD)
        event = SignInEvent.objects.get()
        self.assertIsNone(event.user)
        self.assertEqual(event.username, "nobody")

    def test_sign_ins_stay_out_of_the_change_log(self):
        self.sign_in("rosa", TEST_PASSWORD)
        self.sign_in("rosa", WRONG_PASSWORD)
        self.assertFalse(AuditEvent.objects.exists())


class UserHistoryPageTests(TestCase):
    def setUp(self):
        complete_setup()
        self.admin = make_administrator()
        self.person = make_user(username="ben", first_name="Ben")
        self.other = make_user(username="cara")
        for user in (self.person, self.other):
            SignInEvent.objects.create(
                kind=SignInEvent.Kind.SIGNED_IN, user=user, username=user.username
            )
        SignInEvent.objects.create(
            kind=SignInEvent.Kind.FAILED, user=self.person, username="ben"
        )
        self.url = reverse("accounts:user_history", kwargs={"pk": self.person.pk})

    def test_shows_only_that_persons_sign_ins_and_changes(self):
        # A change Ben made, and one Cara made.
        self.client.force_login(self.person)
        self.client.post(
            reverse("accounts:profile"),
            {"first_name": "Benjamin", "last_name": "", "email": "ben@example.com"},
        )
        self.client.force_login(self.other)
        self.client.post(
            reverse("accounts:profile"),
            {"first_name": "Cara", "last_name": "", "email": "cara@example.com"},
        )
        self.client.force_login(self.admin)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        sign_ins = list(response.context["sign_ins"])
        self.assertTrue(sign_ins)
        self.assertTrue(all(event.user == self.person for event in sign_ins))
        self.assertIn(SignInEvent.Kind.FAILED, [e.kind for e in sign_ins])
        changes = list(response.context["changes"])
        self.assertEqual(len(changes), 1)
        self.assertEqual(changes[0].changes["First name"], ["Ben", "Benjamin"])
        self.assertContains(response, "Failed sign-in")

    def test_needs_the_audit_permission(self):
        self.client.force_login(make_user(perms=["accounts.change_user"]))
        self.assertEqual(self.client.get(self.url).status_code, 403)
        self.client.force_login(make_user(perms=["audit.view_auditevent"]))
        self.assertEqual(self.client.get(self.url).status_code, 200)

    def test_edit_page_links_history_only_with_the_permission(self):
        edit = reverse("accounts:user_update", kwargs={"pk": self.person.pk})
        self.client.force_login(self.admin)
        self.assertContains(self.client.get(edit), f'href="{self.url}"')
        self.client.force_login(make_user(perms=["accounts.change_user"]))
        self.assertNotContains(self.client.get(edit), f'href="{self.url}"')
