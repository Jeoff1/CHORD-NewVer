"""The sign-up page redesign (27 Nov 2026; Design-System.md, "The sign-in
and sign-up pages"): a split screen with its own look, the same form, fields,
CSRF protection and server-side validation as before."""

from django.contrib.auth import get_user_model
from django.contrib.staticfiles import finders
from django.test import Client, TestCase
from django.urls import reverse

from apps.accounts.forms import SignUpForm
from apps.core.testing import complete_setup, make_user

SIGNUP = reverse("accounts:signup")
ACCOUNT = {
    "username": "ruth.ann",
    "first_name": "Ruth",
    "last_name": "Ann",
    "email": "ruth@example.com",
    "password1": "a-Long-pass-8472",
    "password2": "a-Long-pass-8472",
}


class SignUpPageTests(TestCase):
    def test_it_has_its_own_page_with_every_field_of_the_form(self):
        response = self.client.get(SIGNUP)
        self.assertTemplateUsed(response, "accounts/signup.html")
        self.assertTemplateUsed(response, "accounts/auth_base.html")
        self.assertTemplateNotUsed(response, "form_page.html")
        self.assertTemplateNotUsed(response, "base.html")
        for name in SignUpForm().fields:
            with self.subTest(field=name):
                self.assertContains(response, f'name="{name}"', count=1)
        self.assertContains(response, 'name="csrfmiddlewaretoken"')
        self.assertContains(response, 'method="post"')
        self.assertContains(response, "<h1", count=1)
        self.assertContains(response, "Create an account")
        self.assertContains(
            response, "<span data-au-label>Create Account</span></button>"
        )
        self.assertContains(response, 'data-au-busy="Creating account…"')

    def test_the_photo_panel_brand_and_words(self):
        response = self.client.get(SIGNUP)
        self.assertContains(response, "Bringing Worship Together")
        self.assertContains(
            response,
            "A space for churches to connect, organize, and plan meaningful "
            "worship experiences.",
        )
        self.assertContains(response, "images/landing/chord-logo-gold.webp")
        self.assertContains(response, 'aria-label="CHORD, home"')
        # Every image is decorative.
        self.assertNotRegex(response.content.decode(), r'<img (?![^>]*alt="")')

    def test_links_to_sign_in_and_home(self):
        response = self.client.get(SIGNUP)
        login, home = reverse("accounts:login"), reverse("home")
        self.assertContains(
            response,
            f'<a class="au-tab au-tab--on" href="{SIGNUP}" aria-current="page">',
        )
        self.assertContains(response, f'<a class="au-tab" href="{login}">Sign In</a>')
        self.assertContains(response, f'Already have an account? <a href="{login}">')
        self.assertContains(response, f'href="{home}"', count=3)  # logo, two Back links
        # One Back to Home for phones, one for wider screens.
        self.assertContains(response, "Back to Home", count=2)
        self.assertTemplateUsed(response, "includes/icons/arrow-left.html")

    def test_no_sign_in_with_other_services(self):
        content = self.client.get(SIGNUP).content.decode().lower()
        for word in ("google", "facebook", "apple"):
            self.assertNotIn(word, content)

    def test_the_password_checklist_and_show_buttons(self):
        response = self.client.get(SIGNUP)
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
        # One show button per password, hidden until the script runs.
        self.assertContains(response, 'data-au-reveal="id_password1"')
        self.assertContains(response, 'data-au-reveal="id_password2"')
        self.assertContains(
            response, 'aria-label="Show password" aria-pressed="false" hidden'
        )

    def test_the_approved_wording(self):
        response = self.client.get(SIGNUP)
        self.assertContains(response, "Up to 150 letters, digits and @ . + - _")
        self.assertContains(response, ">Confirm password</label>")
        self.assertContains(response, "Enter the same password again.")
        self.assertContains(response, "For resetting your password.")

    def test_it_loads_its_own_stylesheet_script_and_photo(self):
        response = self.client.get(SIGNUP)
        for path in (
            "css/auth.css",
            "accounts/auth.js",
            "images/landing/signup-worship.webp",
            "images/landing/signup-worship-800.webp",
            "images/landing/signup-worship.jpg",
        ):
            self.assertContains(response, path)
            self.assertTrue(finders.find(path), path)
        sources = open(
            finders.find("images/landing/SOURCES.md"), encoding="utf-8"
        ).read()
        self.assertIn("signup-worship", sources)
        self.assertIn("CC0", sources)

    def test_its_styles_stay_on_this_page(self):
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


class SignUpValidationTests(TestCase):
    """The server checks everything, and its messages show on the page."""

    def post(self, **changes):
        return self.client.post(SIGNUP, {**ACCOUNT, **changes})

    def test_mismatched_passwords(self):
        response = self.post(password2="something-else-9")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "The two password fields didn’t match.")
        self.assertContains(response, 'id="id_password2_error"')
        self.assertContains(response, 'aria-invalid="true"')
        self.assertFalse(get_user_model().objects.filter(username="ruth.ann").exists())

    def test_every_password_rule(self):
        for password, message in (
            ("Ab1-x", "This password is too short."),
            ("48261937", "This password is entirely numeric."),
            ("password123", "This password is too common."),
            ("ruth.ann.1", "The password is too similar to the username."),
        ):
            with self.subTest(password=password):
                response = self.post(password1=password, password2=password)
                self.assertContains(response, message)
        self.assertFalse(get_user_model().objects.filter(username="ruth.ann").exists())

    def test_a_taken_username_and_a_missing_email(self):
        make_user(username="ruth.ann")
        response = self.post(email="")
        self.assertContains(response, "A user with that username already exists.")
        self.assertContains(response, "This field is required.")
        # What the person typed comes back, except the passwords.
        self.assertContains(response, 'value="Ruth"')
        self.assertNotContains(response, ACCOUNT["password1"])

    def test_a_good_account_is_created_as_before(self):
        response = self.post()
        self.assertRedirects(response, reverse("home"), fetch_redirect_response=False)
        self.assertTrue(get_user_model().objects.filter(username="ruth.ann").exists())

    def test_the_form_needs_its_csrf_token(self):
        client = Client(enforce_csrf_checks=True)
        response = client.post(SIGNUP, ACCOUNT)
        self.assertEqual(response.status_code, 403)
        self.assertFalse(get_user_model().objects.filter(username="ruth.ann").exists())

    def test_signed_in_people_still_go_home(self):
        complete_setup()
        self.client.force_login(make_user())
        self.assertRedirects(self.client.get(SIGNUP), reverse("home"))
