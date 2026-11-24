"""The dashboard (Phase 9A, A7, part 3): what needs the person now. Each
item shows only to someone who may act on it."""

import datetime

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.core.testing import (
    complete_setup,
    make_assignment,
    make_lineup,
    make_occasion,
    make_occasion_type,
    make_service,
    make_song,
    make_team_part,
    make_theme,
    make_user,
)
from apps.occasions.models import OccasionRequest
from apps.songs.models import ChordSheet

HOME = reverse("home")


class DashboardScreenTests(TestCase):
    def setUp(self):
        complete_setup()
        self.pastor = make_user(roles=["pastoral_staff"], first_name="Pat")
        self.leader = make_user(roles=["worship_leader"])
        self.member = make_user(roles=["team_member"])
        self.church_member = make_user(roles=["church_member"])

    def page(self, user):
        self.client.force_login(user)
        return self.client.get(HOME)

    def test_greeting_and_empty_states(self):
        page = self.page(self.church_member)
        self.assertContains(page, ", user")
        self.assertContains(page, "Nothing needs you right now.")
        page = self.page(self.pastor)
        self.assertRegex(
            page.content.decode(), r"Good (morning|afternoon|evening), Pat"
        )

    def test_a_draft_lineup_is_for_people_who_may_confirm_it(self):
        service = make_service(name="Sunday gathering")
        make_theme(service)
        make_lineup(service, [make_song()], confirmed=False)
        for person in (self.pastor, self.leader):
            with self.subTest(person=person.username):
                page = self.page(person)
                self.assertContains(page, "Confirm the lineup for Sunday gathering")
                self.assertContains(page, ">Review lineup</a>")
        for person in (self.member, self.church_member):
            with self.subTest(person=person.username):
                self.assertNotContains(self.page(person), "Confirm the lineup")

    def test_a_service_without_a_theme_is_for_people_who_post_themes(self):
        make_service(name="Midweek prayer")
        self.assertContains(self.page(self.pastor), "Post the theme for Midweek prayer")
        self.assertNotContains(self.page(self.leader), "Post the theme")

    def test_occasion_requests_are_for_approvers(self):
        OccasionRequest.objects.create(
            requester=self.church_member,
            occasion_type=make_occasion_type(name="Garden wedding"),
            starts_at=timezone.now() + datetime.timedelta(days=20),
            occasion_for="Ana and Ben",
        )
        page = self.page(self.pastor)
        self.assertContains(page, "1 occasion request is waiting")
        self.assertContains(page, ">Open requests</a>")
        self.assertNotContains(self.page(self.leader), "occasion request")

    def test_chord_sheets_waiting_are_for_people_who_approve_them(self):
        ChordSheet.objects.create(
            song=make_song(title="Be Thou My Vision"),
            chordpro="[G]Be thou my vision",
            key="G",
            status=ChordSheet.Status.PENDING,
            added_by=self.member,
        )
        self.assertContains(self.page(self.leader), "1 chord sheet waits for approval")
        self.assertNotContains(self.page(self.member), "chord sheet")

    def test_the_first_item_has_the_primary_button(self):
        make_service(name="Midweek prayer")
        make_service(name="Evening prayer")
        content = self.page(self.pastor).content.decode()
        first = content.index("Post the theme")
        self.assertIn("btn-primary", content[first : first + 400])

    def test_coming_up_with_occasions_for_people_who_see_them(self):
        make_service(name="Sunday gathering")
        make_occasion(
            make_occasion_type(name="Garden wedding"), occasion_for="Ana and Ben"
        )
        page = self.page(self.pastor)
        self.assertContains(page, "Sunday gathering")
        self.assertContains(page, "Garden wedding: Ana and Ben")
        self.assertContains(page, 'class="chord-pill chord-pill--accent">Occasion')
        self.assertContains(page, ">Full schedule</a>")
        page = self.page(self.church_member)
        self.assertContains(page, "Sunday gathering")
        self.assertNotContains(page, "Ana and Ben")

    def test_my_schedule_is_for_the_team(self):
        service = make_service(name="Sunday gathering")
        make_assignment(service, self.member, make_team_part(), reply="accepted")
        page = self.page(self.member)
        self.assertContains(page, "My schedule")
        self.assertContains(page, ">Open my schedule</a>")
        self.assertContains(page, 'class="chord-pill chord-pill--success">Accepted')
        self.assertNotContains(self.page(self.church_member), "My schedule</h2>")

    def test_announcements_and_go_to(self):
        page = self.page(self.church_member)
        self.assertContains(page, "Announcements</h2>")
        self.assertContains(page, "No announcements yet.")
        self.assertContains(page, "Go to</h2>")
        self.assertContains(page, f'href="{reverse("worship:home")}" class="btn')
