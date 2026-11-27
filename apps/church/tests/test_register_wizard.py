"""Registering a church as a four-step wizard (owner, 27 Nov 2026;
Design-System.md, "Registering a church"): one form, sent once and checked on
the server; only the name is needed; the same form sent twice never makes a
second church."""

import shutil
import tempfile
from io import BytesIO

from django.contrib.auth import get_user_model
from django.contrib.staticfiles import finders
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

from apps.accounts.models import Membership
from apps.church.middleware import SESSION_KEY
from apps.church.models import ChurchProfile
from apps.core.testing import complete_setup, make_user

REGISTER = reverse("churches:register")
SETUP = reverse("church:setup", kwargs={"section": "details"})
ACCOUNT = {
    "username": "ruth.ann",
    "first_name": "Ruth",
    "last_name": "Ann",
    "email": "ruth@example.com",
    "password1": "a-Long-pass-8472",
    "password2": "a-Long-pass-8472",
}


def image(name="logo.png", size=(10, 10)):
    buffer = BytesIO()
    Image.new("RGB", size, "white").save(buffer, "PNG")
    return SimpleUploadedFile(name, buffer.getvalue(), content_type="image/png")


class WizardPageTests(TestCase):
    def setUp(self):
        complete_setup()

    def test_a_visitor_sees_the_four_steps_and_every_field_once(self):
        response = self.client.get(REGISTER)
        self.assertTemplateUsed(response, "church/register.html")
        self.assertTemplateNotUsed(response, "base.html")
        self.assertContains(response, "<h1", count=1)
        self.assertContains(response, ">Register your church</h1>")
        for number, title in enumerate(
            (
                "Account information",
                "Church information",
                "Church profile",
                "Review and confirm",
            ),
            start=1,
        ):
            with self.subTest(step=number):
                self.assertContains(response, f'data-au-pane="{number}"')
                self.assertContains(response, f'aria-label="Step {number}, {title}"')
        for name in (
            *ACCOUNT,
            "church-name",
            "church-address",
            "church-phone",
            "church-email",
            "church-logo",
            "church-about",
        ):
            with self.subTest(field=name):
                self.assertContains(response, f'name="{name}"', count=1)
        self.assertContains(response, 'name="church-show_in_directory"', count=2)
        self.assertContains(response, 'value="public" checked')
        self.assertContains(response, 'enctype="multipart/form-data"')
        self.assertContains(response, 'name="csrfmiddlewaretoken"')
        self.assertContains(response, 'name="registration" value="')
        self.assertContains(response, 'data-au-start="1"')
        self.assertContains(response, 'role="progressbar"')
        self.assertContains(
            response, "<span data-au-label>Complete registration</span>"
        )
        self.assertContains(response, 'data-au-busy="Registering…"')

    def test_the_name_starts_empty(self):
        response = self.client.get(REGISTER)
        self.assertNotContains(response, 'value="My Church"')
        self.assertContains(response, 'name="church-name" maxlength="200" required')

    def test_only_the_name_is_marked_needed(self):
        response = self.client.get(REGISTER)
        self.assertContains(
            response, '<span class="au-optional">Optional</span>', count=7
        )
        self.assertContains(response, "Only the name is needed now.")

    def test_the_ways_out(self):
        response = self.client.get(REGISTER)
        login = reverse("accounts:login")
        self.assertContains(
            response, f'Already have an account? <a href="{login}?next={REGISTER}">'
        )
        self.assertContains(
            response,
            f'<a href="{reverse("accounts:signup")}">Create a personal account</a>',
        )
        self.assertContains(response, "Back to Home")
        self.assertContains(response, ">Cancel</a>")

    def test_a_signed_in_person_sees_their_account_not_a_new_one(self):
        person = make_user(
            first_name="Maria", last_name="Santos", email="m@example.com"
        )
        self.client.force_login(person)
        response = self.client.get(REGISTER)
        self.assertNotContains(response, 'name="password1"')
        self.assertNotContains(response, "Create a personal account")
        self.assertContains(response, ">MS</div>")
        self.assertContains(response, "<b>Maria Santos</b>")
        self.assertContains(response, f'action="{reverse("accounts:logout")}"')
        self.assertContains(response, "<dd>Your existing account</dd>")

    def test_its_own_stylesheets_and_scripts(self):
        response = self.client.get(REGISTER)
        content = response.content.decode()
        for path in (
            "css/auth.css",
            "css/register.css",
            "church/register.js",
            "accounts/auth.js",
        ):
            self.assertContains(response, path)
            self.assertTrue(finders.find(path), path)
        # The wizard's script runs first, so a step forward never looks like sending.
        self.assertLess(
            content.index("church/register.js"), content.index("accounts/auth.js")
        )

    def test_its_styles_stay_on_this_page(self):
        css = open(finders.find("css/register.css"), encoding="utf-8").read()
        for line in css.splitlines():
            selector = line.split("{")[0].strip()
            if "{" in line and selector and not selector.startswith(("@", "}")):
                with self.subTest(selector=selector):
                    self.assertTrue(
                        all(
                            part.strip().startswith((".au", "[data-bs-theme"))
                            for part in selector.split(",")
                        ),
                        selector,
                    )
        self.assertNotContains(self.client.get(reverse("home")), "css/register.css")


class WizardRegistrationTests(TestCase):
    def setUp(self):
        complete_setup()
        self.media = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.media, ignore_errors=True)
        override = override_settings(MEDIA_ROOT=self.media)
        override.enable()
        self.addCleanup(override.disable)

    def token(self):
        self.client.get(REGISTER)
        return self.client.session["church_registration_token"]

    def post(self, church=None, account=ACCOUNT, **extra):
        data = {"registration": self.token(), **account, **(church or {})}
        data.update(extra)
        return self.client.post(REGISTER, data)

    def test_the_name_alone_registers_a_public_church(self):
        response = self.post({"church-name": "Grace Chapel"})
        self.assertRedirects(response, SETUP, fetch_redirect_response=False)
        church = ChurchProfile.objects.get(name="Grace Chapel")
        self.assertTrue(church.show_in_directory)
        self.assertEqual((church.address, church.phone, church.about), ("", "", ""))
        self.assertFalse(church.logo)

    def test_every_optional_detail_is_kept(self):
        response = self.post(
            {
                "church-name": "  Grace Chapel ",
                "church-address": "12 Example Street\nSample City",
                "church-phone": "+63 900 000 0000",
                "church-email": "office@example.org",
                "church-about": "  Everyone is welcome.  ",
                "church-show_in_directory": "private",
                "church-logo": image(),
            }
        )
        self.assertRedirects(response, SETUP, fetch_redirect_response=False)
        church = ChurchProfile.objects.get(name="Grace Chapel")
        self.assertEqual(church.address, "12 Example Street\nSample City")
        self.assertEqual(church.phone, "+63 900 000 0000")
        self.assertEqual(church.email, "office@example.org")
        self.assertEqual(church.about, "Everyone is welcome.")
        self.assertFalse(church.show_in_directory)
        self.assertRegex(church.logo.name, r"^church/[0-9a-f]{32}\.png$")
        user = church.memberships.get().user
        self.assertEqual(user.username, "ruth.ann")
        self.assertEqual([r.key for r in user.roles_in(church)], ["administrator"])
        self.assertEqual(self.client.session[SESSION_KEY], church.pk)

    def test_a_missing_name_opens_the_church_step(self):
        response = self.post({"church-name": "  "})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-au-start="2"')
        self.assertContains(response, "data-au-bound")
        self.assertContains(response, 'id="id_church-name_error"')
        self.assertFalse(get_user_model().objects.filter(username="ruth.ann").exists())

    def test_a_bad_church_email_opens_the_church_step(self):
        response = self.post({"church-name": "Grace", "church-email": "nope"})
        self.assertContains(response, 'data-au-start="2"')
        self.assertContains(response, 'id="id_church-email_error"')

    def test_an_account_problem_opens_the_account_step_first(self):
        make_user(username="ruth.ann")
        response = self.post({"church-name": ""})
        self.assertContains(response, 'data-au-start="1"')
        self.assertContains(response, "A user with that username already exists.")
        self.assertNotContains(response, ACCOUNT["password1"])

    def test_a_logo_that_isnt_an_image_opens_the_profile_step(self):
        bad = SimpleUploadedFile("logo.png", b"not an image", content_type="image/png")
        count = ChurchProfile.objects.count()
        response = self.post({"church-name": "Grace", "church-logo": bad})
        self.assertContains(response, 'data-au-start="3"')
        self.assertContains(response, 'id="id_church-logo_error"')
        self.assertEqual(ChurchProfile.objects.count(), count)

    def test_a_long_description_opens_the_profile_step(self):
        response = self.post({"church-name": "Grace", "church-about": "x" * 2001})
        self.assertContains(response, 'data-au-start="3"')

    def test_a_chosen_logo_must_be_chosen_again_after_a_correction(self):
        response = self.post({"church-name": "", "church-logo": image()})
        self.assertContains(response, "Please choose the logo again")
        self.assertContains(response, 'value="private" checked', count=0)

    def test_sending_the_same_form_twice_makes_one_church_and_one_account(self):
        data = {"registration": self.token(), **ACCOUNT, "church-name": "Grace Chapel"}
        first = self.client.post(REGISTER, data)
        again = self.client.post(REGISTER, data)
        self.assertRedirects(first, SETUP, fetch_redirect_response=False)
        self.assertRedirects(again, SETUP, fetch_redirect_response=False)
        self.assertEqual(ChurchProfile.objects.filter(name="Grace Chapel").count(), 1)
        self.assertEqual(
            get_user_model().objects.filter(username="ruth.ann").count(), 1
        )
        church = ChurchProfile.objects.get(name="Grace Chapel")
        self.assertEqual(self.client.session[SESSION_KEY], church.pk)
        self.assertEqual(Membership.objects.filter(church=church).count(), 1)

    def test_a_signed_in_person_sending_twice_also_makes_one_church(self):
        person = make_user()
        self.client.force_login(person)
        data = {"registration": self.token(), "church-name": "Hope Hall"}
        self.client.post(REGISTER, data)
        self.client.post(REGISTER, data)
        self.assertEqual(ChurchProfile.objects.filter(name="Hope Hall").count(), 1)

    def test_a_new_page_registers_another_church(self):
        person = make_user()
        self.client.force_login(person)
        self.client.post(
            REGISTER, {"registration": self.token(), "church-name": "Hope Hall"}
        )
        self.client.post(
            REGISTER, {"registration": self.token(), "church-name": "Hope Hall"}
        )
        self.assertEqual(ChurchProfile.objects.filter(name="Hope Hall").count(), 2)

    def test_someone_elses_token_never_opens_their_church(self):
        data = {"registration": self.token(), **ACCOUNT, "church-name": "Grace Chapel"}
        self.client.post(REGISTER, data)
        grace = ChurchProfile.objects.get(name="Grace Chapel")
        other = make_user()
        self.client.force_login(other)
        # Even with the used token in their session, it isn't their church.
        session = self.client.session
        session["church_registrations_done"] = {data["registration"]: grace.pk}
        session.save()
        response = self.client.post(REGISTER, {**data, "church-name": "Own Church"})
        self.assertRedirects(response, SETUP, fetch_redirect_response=False)
        self.assertTrue(ChurchProfile.objects.filter(name="Own Church").exists())
        self.assertFalse(
            Membership.objects.filter(user=other, church__name="Grace Chapel").exists()
        )
