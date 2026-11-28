"""Phase 2 of the UI/UX implementation (UI/UX owner, 28 Nov 2026): the account popover and Edit
Profile. Initials only, and only the name fields the account already has: no profile picture, bio or
banner (the lead developer's decision, 28 Nov 2026). Design-Decisions.md, "Personal profile"."""

from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.audit.models import AuditEvent
from apps.core.testing import complete_setup, first_church, make_user

EDIT = reverse("accounts:profile_edit")
JSON = {"HTTP_ACCEPT": "application/json"}


def names(**overrides):
    data = {
        "first_name": "Maria",
        "middle_name": "Luz",
        "last_name": "Santos",
        "suffix": "Jr.",
    }
    data.update(overrides)
    return data


class PopoverTests(TestCase):
    def setUp(self):
        complete_setup(show_in_directory=True)

    def test_the_popover_shows_initials_name_role_and_church(self):
        self.client.force_login(
            make_user(
                roles=["administrator"],
                first_name="Maria",
                middle_name="Luz",
                last_name="Santos",
                suffix="Jr.",
            )
        )
        page = self.client.get(reverse("home"))
        self.assertContains(page, "data-account-initials>MS</span>", count=2)
        self.assertContains(
            page, "data-account-name>Maria Luz Santos Jr.</span>", count=2
        )
        self.assertContains(
            page, '<span class="acct__role">Church Administration</span>'
        )
        self.assertContains(
            page, f'<span class="acct__church-name">{first_church().name}</span>'
        )
        self.assertContains(page, "data-profile-open>")
        self.assertContains(page, f'href="{reverse("accounts:profile")}"')
        self.assertContains(page, ">Account Settings</a>")
        self.assertContains(page, f'action="{reverse("accounts:logout")}"')
        self.assertContains(page, f'action="{EDIT}"')

    def test_no_picture_bio_or_banner_anywhere(self):
        self.client.force_login(make_user(roles=["church_member"]))
        page = self.client.get(reverse("home")).content.decode()
        modal = page[page.index("data-profile-modal") : page.index("</dialog>")]
        self.assertNotIn('type="file"', modal)
        self.assertNotIn("textarea", modal)
        self.assertNotIn("camera", modal.lower())
        fields = {field.name for field in User._meta.get_fields()}
        for name in ("avatar", "photo", "picture", "profile_picture", "bio", "about"):
            self.assertNotIn(name, fields)

    def test_the_public_pages_use_the_same_popover(self):
        self.client.force_login(make_user(roles=["church_member"]))
        page = self.client.get(reverse("landing"))
        self.assertContains(page, "acct--public")
        self.assertContains(page, "data-profile-open>")
        self.assertContains(page, "css/account.css")
        self.assertContains(page, ">Account Settings</a>")


class EditProfileTests(TestCase):
    def setUp(self):
        complete_setup()
        self.user = make_user(
            roles=["church_member"], first_name="Ana", last_name="Cruz"
        )
        self.client.force_login(self.user)

    def test_saving_in_the_background_returns_the_new_name(self):
        response = self.client.post(EDIT, names(), **JSON)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(), {"name": "Maria Luz Santos Jr.", "initials": "MS"}
        )
        self.user.refresh_from_db()
        self.assertEqual(
            (self.user.first_name, self.user.middle_name, self.user.suffix),
            ("Maria", "Luz", "Jr."),
        )
        changes = AuditEvent.objects.get().changes
        self.assertEqual(changes["First name"], ["Ana", "Maria"])
        self.assertEqual(changes["Middle name"], ["", "Luz"])
        self.assertEqual(changes["Suffix"], ["", "Jr."])

    def test_first_and_last_name_are_required(self):
        response = self.client.post(EDIT, names(first_name=" ", last_name=""), **JSON)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(set(response.json()["errors"]), {"first_name", "last_name"})
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, "Ana")
        self.assertFalse(AuditEvent.objects.exists())

    def test_only_the_name_fields_change(self):
        email, username = self.user.email, self.user.username
        self.client.post(
            EDIT, names(email="x@example.com", username="taken", is_staff="on"), **JSON
        )
        self.user.refresh_from_db()
        self.assertEqual((self.user.email, self.user.username), (email, username))
        self.assertFalse(self.user.is_staff)

    def test_extra_spaces_are_tidied(self):
        self.client.post(EDIT, names(first_name="  Maria   Clara "), **JSON)
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, "Maria Clara")

    def test_without_javascript_it_goes_back_to_the_page(self):
        response = self.client.post(EDIT, names(next="/worship/"))
        self.assertRedirects(response, "/worship/", fetch_redirect_response=False)

    def test_an_outside_next_address_is_ignored(self):
        response = self.client.post(EDIT, names(next="https://evil.example/"))
        self.assertRedirects(response, reverse("accounts:profile"))

    def test_without_javascript_errors_show_on_a_page(self):
        response = self.client.post(EDIT, names(first_name=""))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Edit profile")
        self.assertContains(response, "This field is required.")

    def test_requires_sign_in(self):
        self.client.logout()
        self.assertEqual(self.client.post(EDIT, names(), **JSON).status_code, 302)


class AccountSettingsTests(TestCase):
    def test_account_settings_is_in_the_settings_hub(self):
        complete_setup()
        self.client.force_login(make_user(roles=["church_member"]))
        page = self.client.get(reverse("accounts:profile"))
        self.assertContains(page, "Account settings")
        self.assertContains(page, '<p class="chord-eyebrow">Personal</p>', html=True)
        self.assertContains(page, f'href="{reverse("accounts:appearance")}"')


class RevisionTests(TestCase):
    """The UI/UX owner's review of Phase 2 (28 Nov 2026)."""

    def setUp(self):
        complete_setup(show_in_directory=True)
        self.user = make_user(
            roles=["church_member"], first_name="Ana", last_name="Cruz"
        )
        self.client.force_login(self.user)

    def test_edit_profile_is_text_only(self):
        page = self.client.get(reverse("home"))
        self.assertContains(page, "data-profile-open>Edit Profile</button>")

    def test_appearance_is_in_the_popover(self):
        page = self.client.get(reverse("home"))
        self.assertContains(page, f'action="{reverse("accounts:appearance")}"')
        self.assertContains(page, 'data-theme-form data-current="device"')
        for value in ("light", "dark", "device"):
            self.assertContains(
                page, f'name="theme" value="{value}" role="menuitemradio"'
            )
        self.assertContains(page, "window.chordSetTheme")

    def test_the_switch_saves_in_the_background(self):
        appearance = reverse("accounts:appearance")
        response = self.client.post(appearance, {"theme": "dark"}, **JSON)
        self.assertEqual(response.json(), {"theme": "dark"})
        self.user.refresh_from_db()
        self.assertEqual(self.user.theme, "dark")
        bad = self.client.post(appearance, {"theme": "purple"}, **JSON)
        self.assertEqual(bad.status_code, 400)

    def test_without_javascript_the_switch_returns_to_the_page(self):
        response = self.client.post(
            reverse("accounts:appearance"), {"theme": "light", "next": "/worship/"}
        )
        self.assertRedirects(response, "/worship/", fetch_redirect_response=False)
        response = self.client.post(
            reverse("accounts:appearance"),
            {"theme": "light", "next": "https://evil.example/"},
        )
        self.assertRedirects(response, reverse("accounts:appearance"))

    def test_the_landing_page_follows_a_signed_in_persons_choice(self):
        self.user.theme = "dark"
        self.user.save()
        self.assertContains(self.client.get(reverse("landing")), 'var choice = "dark"')


class HomepageLogoTests(TestCase):
    """The official CHORD logo goes to /welcome/ when signed in, to the landing page at "/" for a
    guest, with "Go to Homepage" (UI/UX owner, 28 Nov 2026)."""

    def setUp(self):
        complete_setup(show_in_directory=True)
        self.church = first_church()

    def logo_link(self, page, url):
        self.assertContains(
            page, f'href="{url}" aria-label="CHORD, go to the homepage"'
        )
        self.assertContains(page, "Go to Homepage")

    def test_signed_in_every_logo_goes_to_welcome(self):
        self.client.force_login(make_user(roles=["administrator"]))
        welcome = reverse("landing")
        for url in (
            reverse("home"),
            reverse("landing"),
            reverse("churches:directory"),
            reverse("churches:home", kwargs={"slug": self.church.slug}),
            reverse("accounts:profile"),
        ):
            with self.subTest(url=url):
                self.logo_link(self.client.get(url), welcome)

    def test_guests_go_to_the_landing_page(self):
        home = reverse("home")
        for url in (
            reverse("landing"),
            reverse("churches:directory"),
            reverse("churches:home", kwargs={"slug": self.church.slug}),
            reverse("accounts:login"),
        ):
            with self.subTest(url=url):
                self.logo_link(self.client.get(url), home)

    def test_church_logos_keep_their_own_link(self):
        self.client.force_login(make_user(roles=["administrator"]))
        page = self.client.get(reverse("home"))
        self.assertContains(
            page,
            f'href="{reverse("churches:home", kwargs={"slug": self.church.slug})}"',
        )
