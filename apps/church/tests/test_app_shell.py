"""The signed-in sidebar and header, and the dashboard's figures (dashboard
redesign, 27 Nov 2026; Design-Decisions.md, "Dashboard and sidebar").

The menu, the figures and the quick actions show only what the person may
open, in Modules that are switched on, counted for the current church."""

import datetime

from django.test import RequestFactory, TestCase
from django.urls import resolve, reverse
from django.utils import timezone

from apps.church.dashboard import stat_window, window_label
from apps.church.navigation import build, role_line
from apps.core.testing import (
    complete_setup,
    first_church,
    make_assignment,
    make_church,
    make_lineup,
    make_member,
    make_occasion,
    make_occasion_type,
    make_service,
    make_song,
    make_team_part,
    make_user,
)
from apps.occasions.models import OccasionRequest

HOME = reverse("home")
GOLD_LOGO = "images/landing/chord-logo-gold"


class ShellTests(TestCase):
    def setUp(self):
        complete_setup()

    def page(self, user, url=HOME):
        self.client.force_login(user)
        return self.client.get(url)

    def test_signed_in_pages_have_the_sidebar_and_header(self):
        page = self.page(make_user(roles=["administrator"]))
        self.assertContains(page, 'id="chord-sidebar"')
        self.assertContains(page, 'class="chord-hd"')
        self.assertContains(page, "css/sidebar.css")
        # The official CHORD logo, the gold copy for the green sidebar.
        self.assertContains(page, GOLD_LOGO)
        self.assertNotContains(page, 'class="navbar ')

    def test_public_and_sign_in_pages_have_no_sidebar(self):
        church = complete_setup(make_church("Hope Hall"))
        for url in (
            HOME,
            reverse("accounts:login"),
            reverse("churches:register"),
            reverse("churches:directory"),
            reverse("churches:home", kwargs={"slug": church.slug}),
        ):
            with self.subTest(url=url):
                self.client.logout()
                page = self.client.get(url)
                self.assertNotContains(page, 'id="chord-sidebar"')
                self.assertNotContains(page, "css/sidebar.css")

    def test_the_church_panel_shows_its_logo_or_initials_and_name(self):
        church = first_church()
        church.name = "Grace Fellowship"
        church.save()
        admin = make_user(roles=["administrator"])
        page = self.page(admin).content.decode()
        panel = page[page.index('class="chord-sb__church') :][:900]
        self.assertIn("Grace Fellowship", panel)
        self.assertIn(">GF<", panel)
        church.logo.name = "church/example.png"
        church.save()
        page = self.page(admin).content.decode()
        panel = page[page.index('class="chord-sb__church') :][:900]
        self.assertIn(f'src="{church.logo.url}"', panel)
        self.assertNotIn(">GF<", panel)

    def test_the_line_under_the_name_follows_the_role(self):
        church = first_church()
        self.assertEqual(
            role_line(make_user(roles=["administrator"]), church),
            "Church Administration",
        )
        self.assertEqual(
            role_line(make_user(roles=["team_member"]), church), "Team Member"
        )
        self.assertEqual(role_line(make_user(), church), "")
        page = self.page(make_user(roles=["team_member"]))
        self.assertContains(
            page, '<span class="chord-sb__church-role">Team Member</span>'
        )
        self.assertNotContains(page, "Church Administration")

    def test_no_church_switcher_for_a_person_in_one_church(self):
        page = self.page(make_user(roles=["administrator"]))
        self.assertNotContains(page, "Working in")
        self.assertNotContains(page, "Switch church")

    def test_the_menu_follows_permissions(self):
        requests = f'href="{reverse("occasions:requests")}"'
        request_one = f'href="{reverse("occasions:request")}"'
        page = self.page(make_user(roles=["pastoral_staff"]))
        self.assertContains(page, requests)
        self.assertContains(page, ">Services<", html=False)
        self.assertContains(page, ">Bookings<", html=False)
        page = self.page(make_user(roles=["church_member"]))
        self.assertNotContains(page, requests)
        self.assertContains(page, request_one)
        self.assertNotContains(page, f'href="{reverse("accounts:role_list")}"')

    def test_people_who_approve_requests_do_not_get_the_request_links(self):
        # Administrators manage incoming requests (UI/UX owner, 28 Nov 2026):
        # the menu leaves out Request a Service and My Requests for anyone
        # who may approve, while the pages themselves stay open to them.
        request_one = f'href="{reverse("occasions:request")}"'
        mine = f'href="{reverse("occasions:my_requests")}"'
        for role in ("administrator", "pastoral_staff"):
            with self.subTest(role):
                page = self.page(make_user(roles=[role]))
                self.assertContains(page, f'href="{reverse("occasions:requests")}"')
                self.assertNotContains(page, request_one)
                self.assertNotContains(page, mine)
        admin = make_user(roles=["administrator"])
        self.client.force_login(admin)
        self.assertEqual(
            self.client.get(reverse("occasions:my_requests")).status_code, 200
        )
        page = self.page(make_user(roles=["church_member"]))
        self.assertContains(page, request_one)
        self.assertContains(page, mine)

    def test_a_switched_off_module_and_empty_categories_disappear(self):
        complete_setup(disabled_modules=["occasions"])
        page = self.page(make_user(roles=["administrator"]))
        self.assertNotContains(page, "Management")
        self.assertNotContains(page, f'href="{reverse("occasions:requests")}"')
        page = self.page(make_user())
        for category in ("Planning", "Songs", "Management"):
            self.assertNotContains(
                page, f'<span class="chord-sb__label">{category}</span>'
            )

    def test_settings_pages_stay_in_settings(self):
        page = self.page(make_user(roles=["administrator"]))
        self.assertNotContains(page, f'href="{reverse("songs:check_settings")}"')
        self.assertNotContains(page, "Occasion Types")

    def test_the_current_page_is_marked_and_its_category_open(self):
        page = self.page(
            make_user(roles=["administrator"]), reverse("worship:calendar")
        )
        self.assertContains(
            page,
            f'<a class="chord-sb__sublink is-active" href="{reverse("worship:calendar")}" aria-current="page">Calendar</a>',
            html=True,
        )
        self.assertContains(page, 'class="collapse show" id="chord-sb-planning"')
        self.assertContains(
            page, '<span class="chord-hd__page">Calendar</span>', html=True
        )

    def test_build_marks_one_page_only(self):
        admin = make_user(roles=["administrator"])
        request = RequestFactory().get(reverse("worship:calendar"))
        request.user = admin
        request.church = first_church()
        request.resolver_match = resolve(reverse("worship:calendar"))
        nav = build(request)
        active = [
            link
            for category in nav["categories"]
            for link in category.all_links
            if link.active
        ]
        self.assertEqual([link.label for link in active], ["Calendar"])
        self.assertEqual(nav["section"], "Planning")

    def test_members_holds_users_roles_and_the_audit_log(self):
        # They are pages of their own under Members, not Settings pages
        # (the owner, 28 Nov 2026).
        admin = make_user(roles=["administrator"])
        for url, label in (
            (reverse("accounts:user_list"), "Users"),
            (reverse("accounts:user_create"), "Users"),
            (reverse("accounts:user_history", kwargs={"pk": admin.pk}), "Users"),
            (reverse("accounts:role_list"), "Roles and Permissions"),
            (reverse("accounts:permission_matrix"), "Roles and Permissions"),
            (reverse("audit:log"), "Audit Log"),
        ):
            with self.subTest(url):
                page = self.page(admin, url)
                self.assertEqual(page.status_code, 200)
                self.assertContains(page, f'aria-current="page">{label}</a>')
                self.assertContains(page, 'class="collapse show" id="chord-sb-members"')
                self.assertNotContains(page, "chord-settings-menu")
                self.assertContains(page, '<h1 class="h3')

    def test_the_members_links_follow_permissions(self):
        page = self.page(make_user(perms=["accounts.view_user"]))
        self.assertContains(page, f'href="{reverse("accounts:user_list")}"')
        self.assertNotContains(page, f'href="{reverse("accounts:role_list")}"')
        self.assertNotContains(page, f'href="{reverse("audit:log")}"')


class NoModuleTabsTests(TestCase):
    """The Modules' own tab bars are gone: the sidebar holds those pages
    (UI/UX owner, 28 Nov 2026). Tabs that switch something else, such as
    the reports or a list's filter, stay."""

    def test_module_pages_have_no_tab_bar(self):
        complete_setup(members_teams_unlocked=True)
        self.client.force_login(make_user(roles=["administrator"]))
        for name in (
            "occasions:list",
            "occasions:requests",
            "teams:my_schedule",
            "teams:roster",
            "worship:home",
            "worship:calendar",
            "worship:reports",
            "songs:list",
        ):
            with self.subTest(name):
                page = self.client.get(reverse(name))
                self.assertEqual(page.status_code, 200)
                self.assertNotContains(page, "nav-tabs")
                self.assertNotContains(page, 'class="chord-tabs"')
                self.assertContains(page, 'class="chord-sb__sublink is-active"')
        # My Requests is for people who request without approving.
        self.client.force_login(make_user(roles=["church_member"]))
        page = self.client.get(reverse("occasions:my_requests"))
        self.assertNotContains(page, "nav-tabs")
        self.assertContains(page, 'class="chord-sb__sublink is-active"')

    def test_the_sidebar_shows_waiting_requests(self):
        complete_setup()
        OccasionRequest.objects.create(
            church=first_church(),
            requester=make_user(),
            occasion_type=make_occasion_type(name="Garden wedding"),
            starts_at=timezone.now() + datetime.timedelta(days=20),
            occasion_for="Ana and Ben",
        )
        self.client.force_login(make_user(roles=["pastoral_staff"]))
        self.assertContains(
            self.client.get(HOME), 'class="chord-sb__badge" aria-label="1 pending"'
        )
        self.client.force_login(make_user(roles=["team_member"]))
        self.assertNotContains(self.client.get(HOME), "chord-sb__badge")


class SidebarStateTests(TestCase):
    """The sidebar arrives drawn the way the person left it (the cookies
    sidebar.js writes), so moving between pages never resets it."""

    def setUp(self):
        complete_setup()
        self.client.force_login(make_user(roles=["administrator"]))

    def test_categories_and_groups_open_as_left(self):
        self.client.cookies["chord_sidebar_open"] = "songs:1.management-services:0"
        page = self.client.get(HOME)
        self.assertContains(page, 'class="collapse show" id="chord-sb-songs"')
        self.assertContains(page, 'class="collapse" id="chord-sb-planning"')
        self.assertContains(page, 'class="collapse" id="chord-sb-management-services"')
        # A group nobody closed starts open.
        self.assertContains(
            page, 'class="collapse show" id="chord-sb-management-bookings"'
        )

    def test_the_current_page_category_opens_even_if_closed_before(self):
        self.client.cookies["chord_sidebar_open"] = "planning:0"
        page = self.client.get(reverse("worship:calendar"))
        self.assertContains(page, 'class="collapse show" id="chord-sb-planning"')

    def test_the_icon_only_choice_is_drawn_by_the_server(self):
        self.assertNotContains(
            self.client.get(HOME), '<html lang="en" class="chord-sb-icons">'
        )
        self.client.cookies["chord_sidebar"] = "icons"
        self.assertContains(
            self.client.get(HOME), '<html lang="en" class="chord-sb-icons">'
        )

    def test_a_malformed_cookie_is_ignored(self):
        self.client.cookies["chord_sidebar_open"] = "songs:yes.:1.%%%"
        page = self.client.get(HOME)
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, 'class="collapse" id="chord-sb-songs"')


class DashboardFigureTests(TestCase):
    def setUp(self):
        complete_setup()
        self.admin = make_user(roles=["administrator"])

    def page(self, user):
        self.client.force_login(user)
        return self.client.get(HOME)

    def test_the_window_is_the_next_thirty_days(self):
        start, end = stat_window()
        self.assertEqual((end - start).days, 30)
        self.assertTrue(window_label().startswith("Next 30 days · "))

    def test_the_figures_count_the_current_church_and_say_their_dates(self):
        inside = make_service(name="Sunday gathering")
        make_lineup(inside, [make_song()], confirmed=True)
        make_service(name="Midweek prayer")
        make_service(
            name="Far away", starts_at=timezone.now() + datetime.timedelta(days=45)
        )
        make_service(name="Called off", is_cancelled=True)
        other = complete_setup(make_church("Hope Hall"))
        make_service(church=other, name="Elsewhere")
        make_song(church=other)
        OccasionRequest.objects.create(
            church=first_church(),
            requester=self.admin,
            occasion_type=make_occasion_type(name="Garden wedding"),
            starts_at=timezone.now() + datetime.timedelta(days=90),
            occasion_for="Ana and Ben",
        )
        page = self.page(self.admin).content.decode()
        overview = page[page.index('aria-label="Overview"') :][:6000]
        self.assertRegex(
            overview, r"(?s)Upcoming worship services</span>.*?__value\">2<"
        )
        self.assertRegex(
            overview, r"(?s)Confirmed lineups</span>.*?__value\">1<small> of 2</small>"
        )
        self.assertRegex(
            overview, r"(?s)Pending service requests</span>.*?__value\">1<"
        )
        self.assertRegex(overview, r"(?s)Songs in song pool</span>.*?__value\">1<")
        self.assertIn("Next 30 days · ", overview)
        self.assertIn("All pending, any date", overview)
        self.assertIn("Total songs today", overview)

    def test_figures_follow_permissions(self):
        page = self.page(make_user(roles=["team_member"]))
        self.assertNotContains(page, "Pending service requests")
        page = self.page(make_user())
        self.assertNotContains(page, 'aria-label="Overview"')

    def test_smaller_figures(self):
        church = first_church()
        church.members_teams_unlocked = True
        church.save()
        make_member()
        make_occasion(make_occasion_type(name="Garden wedding"))
        service = make_service(name="Sunday gathering")
        make_assignment(service, self.admin, make_team_part(), reply="accepted")
        page = self.page(self.admin)
        # The Member Directory is retired, so no member count.
        self.assertNotContains(page, "active members")
        self.assertContains(page, "<b>1</b> booked services")
        self.assertContains(page, "<b>1</b> upcoming assignment for you")

    def test_lineup_status_for_planners(self):
        make_lineup(
            make_service(name="Sunday gathering"), [make_song()], confirmed=True
        )
        make_lineup(make_service(name="Evening prayer"), [make_song()], confirmed=False)
        make_service(name="Midweek prayer")
        page = self.page(make_user(roles=["worship_leader"]))
        self.assertContains(page, "Lineup status</h2>")
        # The months keep their capitals: "next 30 days · Nov 27 to Dec 27".
        self.assertContains(page, f"Upcoming worship services, n{window_label()[1:]}")
        self.assertContains(
            page, 'aria-label="Confirmed: 1; Draft: 1; No lineup yet: 1"'
        )
        self.assertNotContains(
            self.page(make_user(roles=["team_member"])), "Lineup status"
        )

    def test_a_new_church_shows_empty_states(self):
        church = complete_setup(make_church("New Light"))
        admin = make_user(roles=["administrator"], church=church)
        page = self.page(admin)
        self.assertContains(page, "Nothing needs you right now.")
        self.assertContains(page, "Nothing is coming up.")
        self.assertContains(page, "No worship services in the next 30 days yet.")
        self.assertContains(page, "No announcements yet.")
        self.assertRegex(
            page.content.decode(),
            r"(?s)Upcoming worship services</span>.*?__value\">0<",
        )

    def test_quick_actions_follow_permissions(self):
        create = f'href="{reverse("worship:service_create")}"'
        self.assertContains(self.page(self.admin), create)
        page = self.page(make_user(roles=["church_member"]))
        self.assertNotContains(page, create)
        self.assertNotContains(page, f'<a href="{reverse("occasions:requests")}">')

    def test_signed_out_visitors_get_the_landing_page(self):
        self.client.logout()
        self.assertNotContains(self.client.get(HOME), "chord-kpi")
