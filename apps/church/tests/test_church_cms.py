"""Phase 1 of the UI/UX implementation (UI/UX owner, 28 Nov 2026): the landing page for signed-in
people, the sidebar's links to the landing page and the church page, and the Church CMS (editing a
church's page from the page itself). Design-Decisions.md, "Signed-in website access and the Church
CMS"."""

from django.test import TestCase
from django.urls import reverse

from apps.audit.models import AuditEvent
from apps.church.models import ChurchProfile
from apps.church.tests.test_banner import MediaMixin, picture
from apps.core.testing import complete_setup, first_church, make_church, make_user

LANDING = reverse("landing")
EDIT = reverse("church:profile_edit")


def page_url(church):
    return reverse("churches:home", kwargs={"slug": church.slug})


def editor_data(**overrides):
    data = {
        "part": "all",
        "details-name": "Grace Fellowship",
        "details-address": "12 Example Street",
        "details-phone": "+63 900 000 0000",
        "details-email": "office@example.org",
        "homepage-about": "Everyone is welcome.",
        "homepage-show_in_directory": "on",
        "homepage-accept_outside_requests": "on",
    }
    data.update(overrides)
    return data


class SignedInLandingTests(TestCase):
    def setUp(self):
        complete_setup(show_in_directory=True)

    def test_a_guest_sees_the_landing_page_as_before(self):
        page = self.client.get(reverse("home"))
        self.assertContains(page, ">Sign in</a>")
        self.assertContains(page, ">Sign up</a>")
        self.assertContains(page, ">Explore churches</a>")
        self.assertNotContains(page, "data-account-menu")
        self.assertEqual(self.client.get(LANDING).status_code, 200)
        # Churches no longer edit their wording (28 Nov 2026); they switch Modules.
        self.assertContains(page, "<strong>Your modules</strong>")
        self.assertNotContains(page, "Your wording")

    def test_a_signed_in_person_gets_the_account_menu_instead(self):
        self.client.force_login(
            make_user(roles=["administrator"], first_name="Maria", last_name="Santos")
        )
        page = self.client.get(LANDING)
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, "data-account-menu")
        self.assertContains(page, ">MS<")
        self.assertContains(page, "Church Administration")
        self.assertContains(page, f'href="{reverse("home")}"')
        self.assertContains(page, f'href="{page_url(first_church())}"')
        self.assertContains(page, f'action="{reverse("accounts:logout")}"')
        self.assertNotContains(
            page, 'class="lp-btn lp-btn--ghost lp-btn--small lp-nav__signin"'
        )
        self.assertNotContains(page, ">Explore churches</a>")
        # Signed in, "/" is still the dashboard, with the app's own popover.
        dashboard = self.client.get(reverse("home"))
        self.assertNotContains(dashboard, "acct--public")
        self.assertContains(dashboard, "acct--app")

    def test_my_church_only_when_its_page_can_be_opened(self):
        church = first_church()
        church.show_in_directory = False
        church.save()
        self.client.force_login(make_user(roles=["team_member"]))
        self.assertNotContains(self.client.get(LANDING), f'href="{page_url(church)}"')
        self.client.force_login(make_user(roles=["administrator"]))
        self.assertContains(self.client.get(LANDING), f'href="{page_url(church)}"')


class SidebarLinkTests(TestCase):
    def setUp(self):
        complete_setup(show_in_directory=True)

    def test_the_logo_opens_the_landing_page_with_a_tooltip(self):
        self.client.force_login(make_user(roles=["administrator"]))
        page = self.client.get(reverse("home"))
        self.assertContains(page, f'class="chord-sb__logo" href="{LANDING}"')
        self.assertContains(page, 'data-tip="Go to Homepage"')
        self.assertNotContains(page, "View Website")

    def test_the_church_panel_opens_the_church_page(self):
        self.client.force_login(make_user(roles=["team_member"]))
        page = self.client.get(reverse("home"))
        self.assertContains(
            page,
            f'class="chord-sb__church chord-sb__church--link" href="{page_url(first_church())}"',
        )
        self.assertContains(page, "View page")


class ChurchPageTests(TestCase):
    def setUp(self):
        complete_setup(show_in_directory=True)
        self.church = first_church()

    def test_the_back_arrow_replaces_the_centred_button(self):
        page = self.client.get(page_url(self.church))
        self.assertContains(page, 'class="pf-back"')
        self.assertContains(page, 'aria-label="Back to Churches"')
        self.assertContains(page, 'data-tip="Back to Churches"')
        self.assertNotContains(page, "pf-back__long")
        self.assertContains(page, 'class="pf-head"')

    def test_visitors_and_members_get_no_editing_tools(self):
        for user in (
            None,
            make_user(roles=["team_member"]),
            make_user(roles=["church_member"]),
        ):
            with self.subTest(user=user):
                self.client.logout()
                if user:
                    self.client.force_login(user)
                page = self.client.get(page_url(self.church))
                self.assertEqual(page.status_code, 200)
                self.assertNotContains(page, "pf-editor")
                self.assertNotContains(page, "Edit cover photo")
                self.assertNotContains(page, "profile_edit.js")

    def test_its_administrator_gets_the_editing_tools(self):
        self.client.force_login(make_user(roles=["administrator"]))
        page = self.client.get(page_url(self.church))
        self.assertContains(page, 'id="pf-editor"')
        self.assertContains(page, "Edit cover photo")
        self.assertContains(page, "Change the church logo")
        self.assertContains(page, "View as visitor")
        self.assertContains(page, "1920 × 640 px")
        self.assertContains(page, "512 × 512 px")
        self.assertContains(page, "data-location-picker")
        self.assertNotContains(page, 'name="details-website"')
        self.assertNotContains(page, "data-open-on-load")

    def test_another_churchs_administrator_gets_none(self):
        other = complete_setup(make_church("Hope Hall", show_in_directory=True))
        self.client.force_login(make_user(roles=["administrator"], church=other))
        page = self.client.get(page_url(self.church))
        self.assertEqual(page.status_code, 200)
        self.assertNotContains(page, "pf-editor")


class ProfileEditTests(MediaMixin, TestCase):
    def setUp(self):
        super().setUp()
        complete_setup(show_in_directory=True)
        self.church = first_church()
        self.admin = make_user(roles=["administrator"])

    def test_saving_the_editor_updates_the_church_and_the_audit_trail(self):
        self.client.force_login(self.admin)
        response = self.client.post(
            EDIT, editor_data(**{"details-name": "Grace Chapel"})
        )
        self.assertRedirects(
            response, page_url(self.church), fetch_redirect_response=False
        )
        self.church.refresh_from_db()
        self.assertEqual(self.church.name, "Grace Chapel")
        self.assertEqual(self.church.about, "Everyone is welcome.")
        self.assertEqual(self.church.address, "12 Example Street")
        self.assertTrue(
            AuditEvent.objects.filter(action=AuditEvent.Action.CHANGED).exists()
        )
        self.assertContains(
            self.client.get(page_url(self.church)), "Church profile saved."
        )

    def test_errors_reopen_the_editor_and_save_nothing(self):
        self.client.force_login(self.admin)
        response = self.client.post(
            EDIT, editor_data(**{"details-name": "", "details-email": "not-an-email"})
        )
        self.assertEqual(response.status_code, 400)
        self.assertContains(response, "data-open-on-load", status_code=400)
        self.assertContains(response, "Nothing was saved yet.", status_code=400)
        self.church.refresh_from_db()
        self.assertNotEqual(self.church.name, "")

    def test_only_the_people_who_manage_the_church_may_save(self):
        self.client.force_login(make_user(roles=["team_member"]))
        self.assertEqual(self.client.post(EDIT, editor_data()).status_code, 403)
        self.client.logout()
        self.assertEqual(self.client.post(EDIT, editor_data()).status_code, 302)
        self.church.refresh_from_db()
        self.assertNotEqual(self.church.about, "Everyone is welcome.")

    def test_it_only_edits_the_current_church(self):
        other = complete_setup(make_church("Hope Hall", show_in_directory=True))
        self.client.force_login(make_user(roles=["administrator"], church=other))
        self.client.post(EDIT, editor_data(**{"details-name": "Renamed"}))
        self.church.refresh_from_db()
        other.refresh_from_db()
        self.assertNotEqual(self.church.name, "Renamed")
        self.assertEqual(other.name, "Renamed")

    def test_the_camera_buttons_change_and_remove_pictures(self):
        self.client.force_login(self.admin)
        response = self.client.post(
            EDIT,
            {"part": "logo", "details-logo": picture("logo.png", (512, 512), "PNG")},
        )
        self.assertRedirects(
            response, page_url(self.church), fetch_redirect_response=False
        )
        self.church.refresh_from_db()
        self.assertTrue(self.church.logo)
        self.client.post(EDIT, {"part": "banner", "homepage-banner": picture()})
        self.church.refresh_from_db()
        self.assertTrue(self.church.banner)
        self.assertTrue(
            self.church.show_in_directory, "The other settings stay as they were."
        )
        self.client.post(EDIT, {"part": "logo-remove"})
        self.client.post(EDIT, {"part": "banner-remove"})
        self.church.refresh_from_db()
        self.assertFalse(self.church.logo)
        self.assertFalse(self.church.banner)

    def test_a_wrong_picture_is_refused_with_a_message(self):
        self.client.force_login(self.admin)
        bad = picture("cover.gif", fmt="GIF")
        response = self.client.post(
            EDIT, {"part": "banner", "homepage-banner": bad}, follow=True
        )
        self.assertContains(response, "Choose a JPG, PNG or WebP image.")
        self.church.refresh_from_db()
        self.assertFalse(self.church.banner)

    def test_unknown_parts_are_404(self):
        self.client.force_login(self.admin)
        self.assertEqual(self.client.post(EDIT, {"part": "website"}).status_code, 404)
        self.assertEqual(self.client.get(EDIT).status_code, 405)

    def test_a_private_church_is_still_editable_by_its_administrator(self):
        ChurchProfile.objects.filter(pk=self.church.pk).update(show_in_directory=False)
        self.client.force_login(self.admin)
        self.assertContains(
            self.client.get(page_url(self.church)), "it isn't public yet"
        )
