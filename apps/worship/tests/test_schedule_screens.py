"""The Worship schedule and calendar screens (Phase 9A, A7, part 3)."""

from django.test import TestCase
from django.urls import reverse

from apps.core.testing import (
    complete_setup,
    make_assignment,
    make_lineup,
    make_service,
    make_song,
    make_team_part,
    make_theme,
    make_user,
)

SCHEDULE = reverse("worship:home")
CALENDAR = reverse("worship:calendar")


class ScheduleScreenTests(TestCase):
    def setUp(self):
        complete_setup()
        self.pastor = make_user(roles=["pastoral_staff"])
        self.service = make_service(name="Sunday gathering")
        make_theme(self.service, title="Grace that forgives", scripture="Ephesians 2:8")
        make_lineup(self.service, [make_song()], confirmed=False)
        part = make_team_part()
        make_assignment(
            self.service, make_user(roles=["team_member"]), part, reply="accepted"
        )
        make_assignment(self.service, make_user(roles=["team_member"]), part)

    def test_the_planner_sees_every_column(self):
        self.client.force_login(self.pastor)
        page = self.client.get(SCHEDULE)
        self.assertContains(page, "Sunday gathering")
        self.assertContains(page, "Grace that forgives")
        self.assertContains(page, "Ephesians 2:8")
        self.assertContains(page, 'class="chord-pill chord-pill--warning">Draft')
        self.assertContains(page, "1 of 2 accepted")
        self.assertContains(page, ">Open</a>")
        self.assertContains(page, 'aria-pressed="true"')
        self.assertContains(page, 'placeholder="Search by name or theme"')
        # No tab bar: the sidebar marks the page (UI/UX owner, 28 Nov 2026).
        self.assertNotContains(page, 'aria-label="Worship sections"')
        self.assertContains(
            page, f'class="chord-sb__sublink is-active" href="{SCHEDULE}"'
        )

    def test_the_team_never_sees_a_draft(self):
        self.client.force_login(make_user(roles=["team_member"]))
        page = self.client.get(SCHEDULE)
        self.assertNotContains(page, ">Draft")
        self.assertContains(page, "None yet")

    def test_a_church_member_sees_no_lineup_or_team_column(self):
        self.client.force_login(make_user(roles=["church_member"]))
        page = self.client.get(SCHEDULE)
        self.assertContains(page, "Sunday gathering")
        self.assertNotContains(page, "accepted")
        self.assertNotContains(page, "chord-pill--warning")
        self.assertNotContains(page, ">More</button>")
        self.assertNotContains(page, "Add worship service")

    def test_more_holds_schedule_ahead_and_worship_settings(self):
        self.client.force_login(self.pastor)
        page = self.client.get(SCHEDULE)
        self.assertContains(page, ">More</button>")
        self.assertContains(page, ">Worship settings</a>")
        self.assertContains(page, ">Add worship service</a>")
        # Schedule weeks ahead needs a template with a usual day and time.
        self.assertNotContains(page, "Schedule weeks ahead")

    def test_moved_actions_still_need_their_permission(self):
        self.client.force_login(make_user(roles=["church_member"]))
        for url in (
            reverse("worship:schedule_ahead"),
            reverse("worship:service_create"),
        ):
            with self.subTest(url):
                self.assertEqual(self.client.get(url).status_code, 403)

    def test_past_and_search(self):
        self.client.force_login(self.pastor)
        self.assertNotContains(
            self.client.get(SCHEDULE + "?when=past"), "Sunday gathering"
        )
        self.assertContains(
            self.client.get(SCHEDULE + "?q=forgives"), "Sunday gathering"
        )
        self.assertNotContains(
            self.client.get(SCHEDULE + "?q=nothing-like-it"), "Sunday gathering"
        )

    def test_a_cancelled_service_has_its_pill(self):
        self.service.is_cancelled = True
        self.service.save()
        self.client.force_login(self.pastor)
        self.assertContains(
            self.client.get(SCHEDULE), 'class="chord-pill chord-pill--danger">Cancelled'
        )


class CalendarScreenTests(TestCase):
    def setUp(self):
        complete_setup()

    def test_month_controls_legend_and_tabs(self):
        self.client.force_login(make_user(roles=["pastoral_staff"]))
        page = self.client.get(CALENDAR)
        self.assertContains(page, 'aria-label="Previous month"')
        self.assertContains(page, 'aria-label="Next month"')
        self.assertContains(page, ">Today</a>")
        self.assertContains(page, "Booked (details hidden)")
        self.assertNotContains(page, 'aria-label="Worship sections"')
        self.assertContains(page, '<h1 class="h3 mb-0">Calendar</h1>')
        self.assertContains(page, 'class="chord-sb__sublink is-active"')
        self.assertContains(page, ">Worship settings</a>")
