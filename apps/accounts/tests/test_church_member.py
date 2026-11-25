"""The Church Member default role (Phase 9A, A1; Design-Decisions,
"Adviser comments, 24 Nov").

A Church Member sees the dashboard, the schedule with theme titles,
announcements to everyone and their own member record; never lineups, song
pages, chord sheets, lyrics, suggestions, theme notes, the roster or other
members' records.
"""

from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse

from apps.accounts import roles
from apps.accounts.models import Role
from apps.announcements.models import Announcement
from apps.core.testing import (
    complete_setup,
    first_church,
    make_chord_sheet,
    make_lineup,
    make_member,
    make_service,
    make_song,
    make_theme,
    make_user,
)

REFUSED = (403, 404)


class ChurchMemberRoleTests(TestCase):
    def test_role_is_seeded_with_the_schedule_and_occasion_requests(self):
        role = Role.objects.get(key="church_member")
        self.assertEqual(role.title, "Church Member")
        self.assertEqual(
            {
                f"{p.content_type.app_label}.{p.codename}"
                for p in role.permissions.all()
            },
            {"worship.view_worshipservice", "occasions.request_occasion"},
        )
        self.assertEqual(
            roles.DEFAULT_ROLE_PERMISSIONS["church_member"],
            ["worship.view_worshipservice", "occasions.request_occasion"],
        )

    def test_role_is_editable_like_any_role(self):
        """Code checks permissions, never the role: a permission the church
        removes is gone, and the schedule is refused."""
        role = Role.objects.get(key="church_member")
        role.permissions.remove(
            Permission.objects.get(
                content_type__app_label="worship", codename="view_worshipservice"
            )
        )
        complete_setup()
        self.client.force_login(make_user(roles=["church_member"]))
        self.assertEqual(self.client.get(reverse("worship:home")).status_code, 403)


class ChurchMemberPagesTests(TestCase):
    def setUp(self):
        complete_setup()
        self.user = make_user(roles=["church_member"], first_name="Rosa")
        self.client.force_login(self.user)
        self.service = make_service()
        make_theme(
            service=self.service,
            title="Hope that holds",
            notes="Planning notes for the team only.",
        )
        self.song = make_song(title="Morning Hymn")
        make_chord_sheet(self.song)
        self.lineup = make_lineup(self.service, [self.song], confirmed=True)
        self.item = self.lineup.items.get()

    # --- Allowed ----------------------------------------------------------------

    def test_dashboard_lists_only_modules_it_can_open(self):
        response = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 200)
        codes = [entry.code for entry in response.context["module_entries"]]
        # Occasions opens for them to ask for one (Phase 9A, A5).
        self.assertEqual(codes, ["worship", "occasions", "announcements"])
        self.assertNotContains(response, f'href="{reverse("members:list")}"')
        self.assertNotContains(response, f'href="{reverse("teams:my_schedule")}"')

    def test_schedule_and_calendar(self):
        for name in ("worship:home", "worship:calendar"):
            with self.subTest(name):
                response = self.client.get(reverse(name))
                self.assertEqual(response.status_code, 200)
        self.assertContains(self.client.get(reverse("worship:home")), "Hope that holds")

    def test_service_page_shows_theme_title_but_no_lineup_or_notes(self):
        response = self.client.get(
            reverse("worship:service", kwargs={"public_id": self.service.public_id})
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Hope that holds")
        self.assertNotContains(response, "Planning notes for the team only.")
        self.assertNotContains(response, "Morning Hymn")
        self.assertNotIn("lineup", response.context)
        self.assertFalse(response.context["can_suggest"])
        self.assertNotIn("show_team", response.context)

    def test_announcements_to_everyone(self):
        Announcement.objects.create(
            church=first_church(),
            title="Picnic on Saturday",
            body="Bring a dish.",
            author=make_user(roles=["pastoral_staff"]),
        )
        response = self.client.get(reverse("announcements:list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Picnic on Saturday")

    def test_own_member_record(self):
        make_member(first_name="Rosa", last_name="Lim", user=self.user)
        response = self.client.get(reverse("members:me"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Lim")

    # --- Refused ----------------------------------------------------------------

    def test_refused_on_lineups_songs_and_chord_sheets(self):
        service = {"public_id": self.service.public_id}
        urls = {
            "lineup": reverse("worship:lineup", kwargs=service),
            "lineup song": reverse(
                "worship:lineup_song", kwargs={**service, "pk": self.item.pk}
            ),
            "suggestions": reverse("worship:suggestions", kwargs=service),
            "song library": reverse("songs:list"),
            "song page": reverse(
                "songs:detail", kwargs={"public_id": self.song.public_id}
            ),
            "chord sheet": reverse(
                "songs:chordsheet", kwargs={"public_id": self.song.public_id}
            ),
            "reports": reverse("worship:reports"),
        }
        for name, url in urls.items():
            with self.subTest(name):
                self.assertIn(self.client.get(url).status_code, REFUSED)

    def test_refused_on_the_roster_and_other_members(self):
        other = make_member(last_name="Santos")
        urls = {
            "roster": reverse("teams:roster"),
            "member list": reverse("members:list"),
            "another member": reverse(
                "members:detail", kwargs={"public_id": other.public_id}
            ),
        }
        for name, url in urls.items():
            with self.subTest(name):
                self.assertIn(self.client.get(url).status_code, REFUSED)

    def test_my_schedule_sends_it_to_notifications(self):
        response = self.client.get(reverse("teams:my_schedule"))
        self.assertRedirects(response, reverse("notifications:list"))


class ModuleNavigationTests(TestCase):
    """The navigation and dashboard list a Module only for people who can
    open its page (Phase 9A, A1)."""

    def setUp(self):
        complete_setup()

    def codes(self, user):
        self.client.force_login(user)
        response = self.client.get(reverse("home"))
        return [entry.code for entry in response.context["module_entries"]]

    def test_each_role_sees_the_modules_it_can_open(self):
        expected = {
            "office_staff": ["members", "worship", "occasions", "announcements"],
            "team_member": ["worship", "teams", "announcements"],
            "worship_leader": [
                "members",
                "worship",
                "teams",
                "occasions",
                "announcements",
            ],
            "administrator": [
                "members",
                "worship",
                "teams",
                "occasions",
                "announcements",
            ],
        }
        for role, codes in expected.items():
            with self.subTest(role):
                self.assertEqual(self.codes(make_user(roles=[role])), codes)

    def test_a_permission_given_to_one_user_shows_the_module(self):
        user = make_user(roles=["church_member"], perms=["members.view_member"])
        self.assertIn("members", self.codes(user))

    def test_spotify_account_link_only_for_people_who_see_lineups(self):
        link = f'href="{reverse("songs:spotify_account")}"'
        for role, shown in (
            ("church_member", False),
            ("office_staff", False),
            ("team_member", True),
            ("worship_leader", True),
        ):
            with self.subTest(role):
                self.client.force_login(make_user(roles=[role]))
                response = self.client.get(reverse("home"))
                if shown:
                    self.assertContains(response, link)
                else:
                    self.assertNotContains(response, link)

    def test_no_role_gets_a_message_instead_of_cards(self):
        """Announcements need no permission, so switch them off to leave a
        user without a role nothing to open."""
        complete_setup(disabled_modules=["announcements"])
        self.client.force_login(make_user())
        response = self.client.get(reverse("home"))
        self.assertContains(response, "Your role doesn't open any module yet.")
