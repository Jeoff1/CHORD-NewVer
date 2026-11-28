"""A visitor without an account requests a service (28 Nov 2026): they fill
in the request, make their account in a pop-up with a code emailed to them,
and the request is sent. Their account joins that church as a Church
Member; they can still request from other churches."""

import datetime
import re

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts import verification
from apps.accounts.models import EmailCode, Membership
from apps.audit.models import AuditEvent
from apps.church.middleware import SESSION_KEY
from apps.core.testing import (
    TEST_PASSWORD,
    complete_setup,
    first_church,
    make_church,
    make_occasion,
    make_user,
)
from apps.occasions.models import OccasionRequest, OccasionType

User = get_user_model()
MY_REQUESTS = reverse("public_requests:my_requests")
PASSWORD = "river-stone-42"


def soon(days=20, hour=10):
    day = timezone.localdate() + datetime.timedelta(days=days)
    return timezone.make_aware(datetime.datetime.combine(day, datetime.time(hour)))


def offer_wedding(church):
    wedding = OccasionType.objects.for_church(church).get(name="Wedding")
    wedding.is_active = True
    wedding.offered_publicly = True
    wedding.save()
    return wedding


def emailed_code():
    return re.search(r"\b(\d{6})\b", mail.outbox[-1].body).group(1)


class VisitorSignUpTestCase(TestCase):
    def setUp(self):
        self.church = complete_setup(
            first_church(), name="Riverside Church", show_in_directory=True
        )
        self.wedding = offer_wedding(self.church)
        self.approver = make_user(church=self.church, roles=["pastoral_staff"])
        self.url = reverse(
            "public_requests:request",
            kwargs={"slug": self.church.slug, "type_pk": self.wedding.pk},
        )
        self.when = soon()

    def ask(self):
        return self.client.post(
            self.url,
            {
                "starts_at_0": f"{self.when:%Y-%m-%d}",
                "starts_at_1": f"{self.when:%H:%M}",
                "occasion_for": "Ana and Ben",
                "note": "Garden, please.",
            },
        )

    def account(self, email="ana@example.com", password=PASSWORD):
        return self.client.post(
            self.url,
            {
                "step": "account",
                "first_name": "Ana",
                "last_name": "Reyes",
                "email": email,
                "password": password,
            },
        )

    def code(self, code):
        return self.client.post(self.url, {"step": "code", "code": code})


class SignUpFlowTests(VisitorSignUpTestCase):
    def test_send_opens_the_pop_up_and_keeps_the_request(self):
        page = self.ask()
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, 'id="signup-modal"')
        self.assertContains(page, "Create your account to send it")
        self.assertContains(page, 'value="Ana and Ben"')
        self.assertFalse(OccasionRequest.objects.exists())
        self.assertFalse(User.objects.filter(email="ana@example.com").exists())

    def test_the_right_code_makes_the_account_and_sends_the_request(self):
        self.ask()
        page = self.account()
        self.assertContains(page, "Check your email")
        self.assertContains(page, "ana@example.com")
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["ana@example.com"])
        code = emailed_code()
        self.assertIn(code, mail.outbox[0].subject)
        # Nothing is made before the code.
        self.assertFalse(User.objects.filter(email="ana@example.com").exists())

        response = self.code(code)
        self.assertRedirects(response, MY_REQUESTS)
        user = User.objects.get(email="ana@example.com")
        self.assertEqual((user.first_name, user.last_name), ("Ana", "Reyes"))
        self.assertTrue(user.check_password(PASSWORD))
        request = OccasionRequest.objects.get()
        self.assertEqual(request.requester, user)
        self.assertEqual(request.church, self.church)
        self.assertEqual(request.occasion_for, "Ana and Ben")
        self.assertEqual(request.starts_at, self.when)
        # Signed in, working in the church they joined, as a Church Member.
        self.assertEqual(int(self.client.session["_auth_user_id"]), user.pk)
        self.assertEqual(self.client.session[SESSION_KEY], self.church.pk)
        membership = Membership.objects.get(user=user)
        self.assertEqual(membership.church, self.church)
        self.assertEqual(
            [role.key for role in membership.roles.all()], ["church_member"]
        )
        event = AuditEvent.objects.get(
            church=self.church, changes__Account__1="Made when requesting a service"
        )
        self.assertEqual(event.actor, user)

    def test_the_password_is_never_stored_as_typed(self):
        self.ask()
        self.account()
        stored = EmailCode.objects.get()
        self.assertNotIn(PASSWORD, str(stored.pending))
        self.assertNotIn(emailed_code(), stored.code_hash)

    def test_a_wrong_code_counts_down_then_stops(self):
        self.ask()
        self.account()
        right = emailed_code()
        wrong = "000000" if right != "000000" else "111111"
        page = self.code(wrong)
        self.assertContains(page, "That code isn&#x27;t right. 4 tries left.")
        for _ in range(4):
            page = self.code(wrong)
        self.assertContains(page, "Too many wrong tries. Ask for a new code.")
        # Even the right code is refused now.
        self.assertContains(self.code(right), "Too many wrong tries")
        self.assertFalse(User.objects.filter(email="ana@example.com").exists())

    def test_an_old_code_has_expired(self):
        self.ask()
        self.account()
        EmailCode.objects.update(
            expires_at=timezone.now() - datetime.timedelta(seconds=1)
        )
        self.assertContains(self.code(emailed_code()), "That code has expired.")

    def test_a_new_code_waits_a_minute_and_replaces_the_old(self):
        self.ask()
        self.account()
        first = emailed_code()
        page = self.client.post(self.url, {"step": "resend"})
        self.assertContains(page, "A code was just sent.")
        self.assertEqual(len(mail.outbox), 1)
        EmailCode.objects.update(
            created_at=timezone.now() - datetime.timedelta(seconds=61)
        )
        page = self.client.post(self.url, {"step": "resend"})
        self.assertContains(page, "A new code is on its way.")
        self.assertEqual(len(mail.outbox), 2)
        second = emailed_code()
        if first != second:
            self.assertContains(self.code(first), "isn&#x27;t right")
        self.assertRedirects(self.code(second), MY_REQUESTS)

    def test_at_most_five_codes_an_hour(self):
        for _ in range(verification.MAX_SENDS_PER_HOUR):
            EmailCode.objects.create(
                email="ana@example.com",
                code_hash="x",
                expires_at=timezone.now(),
                created_at=timezone.now(),
            )
        EmailCode.objects.update(
            created_at=timezone.now() - datetime.timedelta(minutes=5)
        )
        self.ask()
        page = self.account()
        self.assertContains(page, "Too many codes were sent to this address.")
        self.assertEqual(len(mail.outbox), 0)

    def test_the_account_form_checks_name_email_and_password(self):
        self.ask()
        page = self.account(email="not-an-email", password="123")
        self.assertContains(page, "Create your account to send it")
        self.assertContains(page, "Enter a valid email address.")
        self.assertEqual(len(mail.outbox), 0)
        page = self.account(password="12345678")
        self.assertContains(page, "This password is entirely numeric.")

    def test_a_steps_post_without_a_waiting_request_starts_again(self):
        response = self.account()
        self.assertRedirects(response, self.url, fetch_redirect_response=False)
        self.assertEqual(len(mail.outbox), 0)

    def test_a_past_time_is_refused_before_any_account(self):
        self.when = timezone.now() - datetime.timedelta(days=1)
        page = self.ask()
        self.assertContains(page, "Choose a date and time that hasn")
        self.assertNotContains(page, 'id="signup-modal"')


class MailServerTests(VisitorSignUpTestCase):
    def test_a_mail_server_failure_says_so_and_keeps_the_details(self):
        from unittest import mock

        with mock.patch(
            "apps.accounts.verification.send_mail",
            side_effect=OSError("connection refused"),
        ):
            self.ask()
            with self.assertLogs("apps.accounts.verification", "ERROR"):
                page = self.account()
        self.assertContains(page, "We couldn&#x27;t send the email just now.")
        self.assertContains(page, "Create your account to send it")
        self.assertContains(page, 'value="ana@example.com"')
        # No code is left over, so trying again isn't held back.
        self.assertFalse(EmailCode.objects.exists())
        self.assertEqual(verification.seconds_until_resend("ana@example.com"), 0)


class ExistingAccountTests(VisitorSignUpTestCase):
    def test_an_email_with_an_account_signs_in_and_sends(self):
        other = complete_setup(make_church("Hilltop Chapel"))
        ben = make_user(church=other, email="ben@example.com", roles=["administrator"])
        self.ask()
        page = self.account(email="BEN@example.com")
        self.assertContains(page, "Sign in to send your request")
        self.assertContains(page, "You already have a CHORD account with this email.")
        self.assertEqual(len(mail.outbox), 0)
        page = self.client.post(self.url, {"step": "signin", "password": "wrong"})
        self.assertContains(page, "That password isn&#x27;t right.")
        response = self.client.post(
            self.url, {"step": "signin", "password": TEST_PASSWORD}
        )
        self.assertRedirects(response, MY_REQUESTS)
        self.assertEqual(OccasionRequest.objects.get().requester, ben)
        # An existing account isn't made a member of the church it asks.
        self.assertFalse(
            Membership.objects.filter(user=ben, church=self.church).exists()
        )


class ChurchRulesTests(VisitorSignUpTestCase):
    def test_a_church_for_its_own_people_asks_visitors_to_sign_in(self):
        self.church.accept_outside_requests = False
        self.church.save()
        response = self.client.get(self.url)
        self.assertRedirects(
            response,
            f"{reverse('accounts:login')}?next={self.url}",
            fetch_redirect_response=False,
        )
        self.assertEqual(self.ask().status_code, 302)
        self.assertFalse(OccasionRequest.objects.exists())

    def test_the_new_member_can_still_ask_another_church(self):
        self.ask()
        self.account()
        self.code(emailed_code())
        other = complete_setup(make_church("Hilltop Chapel"), show_in_directory=True)
        wedding = offer_wedding(other)
        url = reverse(
            "public_requests:request",
            kwargs={"slug": other.slug, "type_pk": wedding.pk},
        )
        when = soon(days=30)
        response = self.client.post(
            url,
            {
                "starts_at_0": f"{when:%Y-%m-%d}",
                "starts_at_1": f"{when:%H:%M}",
                "occasion_for": "Our son",
                "note": "",
            },
        )
        self.assertRedirects(response, MY_REQUESTS)
        self.assertEqual(
            sorted(OccasionRequest.objects.values_list("church__name", flat=True)),
            ["Hilltop Chapel", "Riverside Church"],
        )
        # Linked only to the first church.
        user = User.objects.get(email="ana@example.com")
        self.assertEqual(
            list(Membership.objects.filter(user=user).values_list("church", flat=True)),
            [self.church.pk],
        )

    def test_a_time_taken_meanwhile_keeps_the_account_and_says_so(self):
        self.ask()
        self.account()
        code = emailed_code()
        make_occasion(self.wedding, starts_at=self.when)
        page = self.code(code)
        # The account is made and signed in; the form says the time is taken.
        self.assertTrue(User.objects.filter(email="ana@example.com").exists())
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, "That time is already booked.")
        self.assertContains(page, 'value="Ana and Ben"')
        self.assertNotContains(page, 'id="signup-modal"')
        self.assertFalse(OccasionRequest.objects.exists())
