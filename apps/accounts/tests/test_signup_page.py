"""Signing up for CHORD is registering a church (owner, 27 Nov 2026;
Design-System.md, "Registering a church"): the old personal sign-up address
goes to the registration wizard, whose first step makes the person's account
with ``SignUpForm`` and the same server-side validation as before."""

from django.contrib.auth import get_user_model
from django.contrib.staticfiles import finders
from django.test import Client, TestCase
from django.urls import reverse

from apps.core.testing import complete_setup, make_user

SIGNUP = reverse("accounts:signup")
REGISTER = reverse("churches:register")
ACCOUNT = {
    "first_name": "Ruth",
    "last_name": "Ann",
    "email": "ruth@example.com",
    "password1": "a-Long-pass-8472",
    "password2": "a-Long-pass-8472",
}


class OldSignUpAddressTests(TestCase):
    def test_it_goes_to_registering_a_church(self):
        self.assertRedirects(self.client.get(SIGNUP), REGISTER)

    def test_it_keeps_the_query_string(self):
        response = self.client.get(f"{SIGNUP}?next=/churches/")
        self.assertRedirects(response, f"{REGISTER}?next=/churches/")

    def test_a_form_sent_to_it_makes_nothing(self):
        response = self.client.post(SIGNUP, ACCOUNT)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], REGISTER)
        self.assertFalse(get_user_model().objects.filter(username="ruth.ann").exists())

    def test_signed_in_people_go_there_too(self):
        complete_setup()
        self.client.force_login(make_user())
        self.assertRedirects(self.client.get(SIGNUP), REGISTER)

    def test_there_is_no_personal_sign_up_page_left(self):
        for url in (reverse("home"), reverse("accounts:login"), REGISTER):
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertNotContains(response, "Create a personal account")
                self.assertNotContains(response, f'href="{SIGNUP}"')


class AccountStepTests(TestCase):
    """The wizard's first step: the account fields, the checklist, Show /
    Hide and the approved wording, from the old sign-up page."""

    def test_the_fields_the_checklist_and_the_show_buttons(self):
        response = self.client.get(REGISTER)
        for name in (*ACCOUNT, "middle_name", "suffix"):
            with self.subTest(field=name):
                self.assertContains(response, f'name="{name}"', count=1)
        # No username: the person signs in with their email.
        self.assertNotContains(response, 'name="username"')
        # The checklist stands in for Django's help list and keeps its id.
        self.assertContains(response, 'aria-describedby="id_password1_helptext"')
        self.assertContains(response, 'id="id_password1_helptext"')
        for rule in (
            "8 or more characters",
            "Not only numbers",
            "Unlike your name or email",
            "Not a common password",
        ):
            self.assertContains(response, rule)
        self.assertContains(response, "(checked when you create the account)")
        self.assertContains(response, 'data-au-reveal="id_password1"')
        self.assertContains(response, 'data-au-reveal="id_password2"')
        self.assertContains(
            response,
            'aria-pressed="false" hidden><span data-au-reveal-word>Show</span>'
            '<span class="visually-hidden"> password</span></button>',
        )

    def test_the_approved_wording(self):
        response = self.client.get(REGISTER)
        self.assertContains(response, ">Email address</label>")
        self.assertContains(response, "You sign in with it, and reset your password.")
        self.assertContains(response, ">Confirm password</label>")
        self.assertContains(response, "Enter the same password again.")
        self.assertContains(response, "Jr., Sr., III")

    def test_its_styles_stay_on_these_pages(self):
        css = open(finders.find("css/auth.css"), encoding="utf-8").read()
        for line in css.splitlines():
            selector = line.split("{")[0].strip()
            # Page transitions only act between two pages that both load auth.css.
            skip = ("@", "}", "::view-transition")
            if "{" in line and selector and not selector.startswith(skip):
                with self.subTest(selector=selector):
                    self.assertTrue(
                        all(
                            part.strip().startswith((".au", "[data-bs-theme"))
                            for part in selector.split(",")
                        ),
                        selector,
                    )
        for url in (reverse("home"), reverse("accounts:password_reset")):
            with self.subTest(url=url):
                self.assertNotContains(self.client.get(url), "css/auth.css")


class AccountValidationTests(TestCase):
    """The server checks the account, and its messages show on step 1."""

    def post(self, **changes):
        return self.client.post(
            REGISTER, {**ACCOUNT, "church-name": "Grace Chapel", **changes}
        )

    def assertNothingMade(self):
        self.assertFalse(
            get_user_model().objects.filter(email="ruth@example.com").exists()
        )

    def test_mismatched_passwords(self):
        response = self.post(password2="something-else-9")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "The two password fields didn’t match.")
        self.assertContains(response, 'id="id_password2_error"')
        self.assertContains(response, 'aria-invalid="true"')
        self.assertContains(response, 'data-au-start="3"')
        self.assertNothingMade()

    def test_every_password_rule(self):
        for password, message in (
            ("Ab1-x", "This password is too short."),
            ("48261937", "This password is entirely numeric."),
            ("password123", "This password is too common."),
            ("ruth@example", "The password is too similar to the"),
        ):
            with self.subTest(password=password):
                response = self.post(password1=password, password2=password)
                self.assertContains(response, message)
        self.assertNothingMade()

    def test_a_used_email_and_a_missing_first_name(self):
        make_user(email="RUTH@example.com")
        response = self.post(first_name="")
        self.assertContains(response, "An account already uses this email.")
        self.assertContains(response, "This field is required.")
        # What the person typed comes back, except the passwords.
        self.assertContains(response, 'value="Ann"')
        self.assertNotContains(response, ACCOUNT["password1"])

    def test_the_username_is_made_from_the_email_and_never_shared(self):
        from apps.accounts.forms import username_from_email

        make_user(username="ruth@example.com", email="other@example.com")
        self.assertEqual(
            username_from_email(" Ruth@Example.com "), "ruth@example.com-2"
        )
        self.assertEqual(username_from_email("o'neil@example.com"), "oneil@example.com")

    def test_the_form_needs_its_csrf_token(self):
        client = Client(enforce_csrf_checks=True)
        response = client.post(REGISTER, {**ACCOUNT, "church-name": "Grace Chapel"})
        self.assertEqual(response.status_code, 403)
        self.assertNothingMade()
