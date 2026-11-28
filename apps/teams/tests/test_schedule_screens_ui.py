"""UI/UX Phase 7 (28 Nov 2026): calendar, team roster and My schedule. UI-UX-Master-Plan.md §13."""

from django.test import TestCase
from django.urls import reverse

from apps.core.testing import (
    complete_setup,
    make_assignment,
    make_service,
    make_team_part,
    make_team_profile,
    make_user,
)


class ScheduleScreenTests(TestCase):
    def setUp(self):
        complete_setup()
        self.admin = make_user(
            roles=["administrator"], first_name="Ruth", last_name="Cole"
        )

    def test_the_calendar_marks_events_by_kind(self):
        service = make_service(name="Evening prayer")
        self.client.force_login(self.admin)
        page = self.client.get(
            reverse("worship:calendar"), {"month": service.starts_at.strftime("%Y-%m")}
        )
        self.assertContains(page, 'class="chord-cal"')
        self.assertContains(page, "chord-cal__event--service")
        self.assertContains(page, 'aria-label="Legend"')

    def test_the_roster_shows_initials_and_part_chips(self):
        person = make_user(roles=["team_member"], first_name="Ana", last_name="Diaz")
        make_team_profile(person, [make_team_part("Hand bells")])
        self.client.force_login(self.admin)
        page = self.client.get(reverse("teams:roster"))
        self.assertContains(
            page, '<span class="chord-person" aria-hidden="true">AD</span>'
        )
        self.assertContains(page, '<span class="chord-chip">Hand bells</span>')

    def test_my_schedule_lists_assignments_with_date_tiles(self):
        person = make_user(roles=["team_member"])
        part = make_team_part("Tambourine")
        make_team_profile(person, [part])
        make_assignment(make_service(name="Morning gathering"), person, part)
        self.client.force_login(person)
        page = self.client.get(reverse("teams:my_schedule"))
        self.assertContains(page, "chord-date__day")
        self.assertContains(page, "Morning gathering")
        self.assertContains(page, "chord-pill")
