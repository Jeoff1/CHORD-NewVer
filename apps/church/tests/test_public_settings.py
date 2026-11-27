"""Phase 9B, slice d (decision 0014): what a church shows publicly, its
logo, the setup wizard of a new church, and sign-in history of accounts
other churches share."""

from io import BytesIO
from unittest import mock

from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.template.loader import render_to_string
from django.test import TestCase
from django.urls import reverse
from PIL import Image

from apps.accounts.models import Membership, Role
from apps.audit.models import AuditEvent, SignInEvent
from apps.audit.services import record_change
from apps.church.forms import ABOUT_MAX_LENGTH
from apps.church.middleware import SESSION_KEY
from apps.church.models import ChurchProfile
from apps.core.testing import (
    complete_setup,
    first_church,
    make_administrator,
    make_church,
    make_user,
)
from apps.occasions.models import OccasionType

HOMEPAGE = reverse("church:settings", kwargs={"section": "homepage"})
DETAILS = reverse("church:settings", kwargs={"section": "details"})


def upload(name, content=None, image_format="PNG"):
    if content is None:
        buffer = BytesIO()
        Image.new("RGB", (10, 10), "white").save(buffer, image_format)
        content = buffer.getvalue()
    return SimpleUploadedFile(name, content)


def details(**overrides):
    church = first_church()
    data = {
        "name": church.name,
        "address": "",
        "phone": "",
        "email": "",
        "website": "",
        "currency": "PHP",
        "time_zone": "Asia/Manila",
    }
    data.update(overrides)
    return data


class DefaultsTests(TestCase):
    """Nothing about the church from before Phase 9B becomes public until
    its Administrator chooses."""

    def test_the_existing_church_starts_private(self):
        church = first_church()
        self.assertFalse(church.show_in_directory)
        self.assertFalse(church.show_upcoming_services)
        self.assertTrue(church.accept_outside_requests)
        self.assertFalse(
            OccasionType.objects.for_church(church)
            .filter(offered_publicly=True)
            .exists()
        )

    def test_a_new_church_offers_no_occasion_publicly(self):
        church = make_church("Grace Chapel")
        self.assertTrue(church.show_in_directory)
        self.assertFalse(church.show_upcoming_services)
        self.assertTrue(church.accept_outside_requests)
        types = OccasionType.objects.for_church(church)
        self.assertEqual(types.count(), 3)
        self.assertFalse(types.filter(offered_publicly=True).exists())


class HomepageSettingsTests(TestCase):
    def setUp(self):
        complete_setup()
        self.client.force_login(make_administrator())

    def test_the_settings_hub_links_it_under_general_after_modules(self):
        # The old settings tabs are gone; the hub is the only way in.
        menu = self.client.get(DETAILS).context["settings_menu"]
        general = next(c for c in menu.categories if c.key == "general")
        self.assertEqual(
            [(page.label, page.url) for page in general.pages][-2:],
            [
                ("Modules", reverse("church:settings", kwargs={"section": "modules"})),
                ("Public homepage", HOMEPAGE),
            ],
        )
        self.assertContains(self.client.get(DETAILS), f'href="{HOMEPAGE}"')
        self.assertEqual(
            self.client.get(HOMEPAGE).context["settings_menu"].current.label,
            "Public homepage",
        )

    def test_the_church_chooses_what_is_public(self):
        response = self.client.post(
            HOMEPAGE,
            {
                "show_in_directory": "on",
                "about": "  We meet on Sundays.\nAll are welcome.  ",
                "show_upcoming_services": "on",
                "accept_outside_requests": "",
            },
        )
        self.assertRedirects(response, HOMEPAGE)
        church = first_church()
        self.assertTrue(church.show_in_directory)
        self.assertTrue(church.show_upcoming_services)
        self.assertFalse(church.accept_outside_requests)
        self.assertEqual(church.about, "We meet on Sundays.\nAll are welcome.")

    def test_about_has_a_length_limit(self):
        response = self.client.post(HOMEPAGE, {"about": "x" * (ABOUT_MAX_LENGTH + 1)})
        self.assertContains(response, "is-invalid")
        self.assertEqual(first_church().about, "")

    def test_about_is_plain_text_with_its_line_breaks(self):
        church = ChurchProfile(about='<script>alert("x")</script>\nLine <b>two</b>')
        html = render_to_string("church/includes/about.html", {"church": church})
        self.assertNotIn("<script>", html)
        self.assertNotIn("<b>", html)
        self.assertIn("&lt;script&gt;", html)
        self.assertIn("<br>", html)

    def test_an_occasion_type_is_offered_publicly_only_when_chosen(self):
        wedding = OccasionType.objects.for_church(first_church()).get(name="Wedding")
        url = reverse("occasions:types_update", kwargs={"pk": wedding.pk})
        self.client.post(
            url,
            {
                "name": "Wedding",
                "description": "",
                "length_minutes": 120,
                "offered_publicly": "on",
                "sort_order": 10,
                "is_active": "on",
            },
        )
        wedding.refresh_from_db()
        self.assertTrue(wedding.offered_publicly)
        listing = self.client.get(reverse("occasions:types_list"))
        self.assertContains(listing, "Offered publicly")


class LogoTests(TestCase):
    def setUp(self):
        complete_setup()
        self.client.force_login(make_administrator())

    def test_the_address_names_neither_the_file_nor_a_private_folder(self):
        self.client.post(
            DETAILS, details(logo=upload("../../protected_media/ana passport.PNG"))
        )
        logo = first_church().logo
        self.assertRegex(logo.name, r"^church/[0-9a-f]{32}\.png$")
        self.assertTrue(logo.url.startswith(settings.MEDIA_URL + "church/"))
        for private in ("passport", "ana", "protected", ".."):
            self.assertNotIn(private, logo.url)

    def test_only_an_image_is_taken(self):
        for name, content in (
            ("notes.png", b"not an image at all"),
            ("logo.svg", b'<svg xmlns="http://www.w3.org/2000/svg"></svg>'),
            ("logo.pdf", b"%PDF-1.4"),
        ):
            with self.subTest(name=name):
                response = self.client.post(
                    DETAILS, details(logo=upload(name, content))
                )
                self.assertContains(response, "is-invalid")
                self.assertFalse(first_church().logo)

    def test_an_image_with_an_unlisted_extension_is_refused(self):
        response = self.client.post(
            DETAILS, details(logo=upload("logo.bmp", image_format="BMP"))
        )
        self.assertContains(response, "is-invalid")
        self.assertFalse(first_church().logo)


class SetupWizardForANewChurchTests(TestCase):
    def setUp(self):
        complete_setup()
        self.church = make_church("Grace Chapel")  # setup not finished
        self.setup = reverse("church:setup", kwargs={"section": "details"})

    def home_as(self, user):
        self.client.force_login(user)
        session = self.client.session
        session[SESSION_KEY] = self.church.pk
        session.save()
        return self.client.get(reverse("home"))

    def test_registering_goes_straight_to_the_dashboard(self):
        # Registration asks what the wizard needs; the rest has defaults
        # (owner, 27 Nov 2026). The wizard stays for a church not set up.
        self.client.force_login(make_user())
        response = self.client.post(
            reverse("churches:register"), {"church-name": "Hope Hall"}
        )
        self.assertRedirects(response, reverse("home"), fetch_redirect_response=False)
        self.assertTrue(ChurchProfile.objects.get(name="Hope Hall").setup_completed)
        self.assertEqual(self.client.get(reverse("home")).status_code, 200)

    def test_its_administrator_goes_to_the_dashboard(self):
        # No setup wizard any more (owner, 27 Nov 2026).
        admin = make_user(church=self.church, roles=["administrator"])
        self.assertEqual(self.home_as(admin).status_code, 200)
        self.church.refresh_from_db()
        self.assertTrue(self.church.setup_completed)

    def test_its_fourth_step_is_the_public_homepage(self):
        # The wizard's pages stay at their addresses, though nothing sends
        # anyone there now.
        admin = make_user(church=self.church, roles=["administrator"])
        self.client.force_login(admin)
        session = self.client.session
        session[SESSION_KEY] = self.church.pk
        session.save()
        step = reverse("church:setup", kwargs={"section": "homepage"})
        self.assertContains(self.client.get(step), "Step 4 of 4: Public homepage")
        self.assertContains(
            self.client.get(reverse("church:setup", kwargs={"section": "modules"})),
            "Step 3 of 4: Modules",
        )
        # Once set up, the step opens the settings page the hub links.
        complete_setup(self.church)
        self.assertRedirects(
            self.client.get(step),
            reverse("church:settings", kwargs={"section": "homepage"}),
        )

    def test_a_superuser_looking_in_is_not(self):
        boss = make_user(is_superuser=True, church=False)
        self.assertEqual(self.home_as(boss).status_code, 200)

    def test_someone_else_with_the_permission_is_not(self):
        helper = make_user(church=self.church, perms=["church.change_churchprofile"])
        self.assertEqual(self.home_as(helper).status_code, 200)

    def test_once_set_up_nobody_is(self):
        complete_setup(self.church)
        admin = make_user(church=self.church, roles=["administrator"])
        self.assertEqual(self.home_as(admin).status_code, 200)


class SignInHistoryTests(TestCase):
    """Owner's decision (option a): a church sees an account's sign-ins only
    when the account is that church's alone."""

    def setUp(self):
        complete_setup()
        self.church = first_church()
        self.client.force_login(make_administrator())
        self.other = make_church("Grace Chapel")

    def history(self, person):
        return self.client.get(
            reverse("accounts:user_history", kwargs={"pk": person.pk})
        )

    def signed_in(self, person):
        SignInEvent.objects.create(
            kind=SignInEvent.Kind.SIGNED_IN, user=person, username=person.username
        )

    def test_an_account_of_this_church_only_shows_its_sign_ins(self):
        person = make_user(roles=["team_member"])
        self.signed_in(person)
        response = self.history(person)
        self.assertContains(response, "Signed in")
        self.assertNotContains(response, "Shared account")

    def test_a_shared_account_shows_changes_here_but_no_sign_ins(self):
        person = make_user(roles=["team_member"])
        Membership.objects.create(user=person, church=self.other).roles.add(
            Role.objects.get(church=self.other, key="team_member")
        )
        self.signed_in(person)
        here = make_church("Ignored")  # a record to change in each church
        record_change(
            person,
            here,
            AuditEvent.Action.CHANGED,
            {"Note": ["", "x"]},
            church=self.church,
        )
        record_change(
            person,
            here,
            AuditEvent.Action.CHANGED,
            {"Note": ["", "y"]},
            church=self.other,
        )
        with mock.patch.object(
            SignInEvent.objects,
            "filter",
            side_effect=AssertionError("Sign-ins of a shared account were read."),
        ):
            response = self.history(person)
        self.assertContains(response, "Shared account: sign-ins not shown")
        self.assertEqual(response.context["sign_ins"], [])
        self.assertEqual(
            [event.church for event in response.context["changes"]], [self.church]
        )

    def test_a_superusers_account_shows_no_sign_ins(self):
        boss = make_user(is_superuser=True)
        self.signed_in(boss)
        response = self.history(boss)
        self.assertContains(response, "Shared account: sign-ins not shown")
        self.assertEqual(response.context["sign_ins"], [])
