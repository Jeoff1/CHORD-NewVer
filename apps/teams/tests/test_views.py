"""Teams pages: permissions, module switching and the service team."""

import datetime

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.roles import DEFAULT_ROLE_PERMISSIONS
from apps.core.testing import (
    complete_setup,
    make_assignment,
    make_service,
    make_team_part,
    make_team_profile,
    make_user,
)
from apps.teams import rostering
from apps.teams.models import Assignment, BlackoutDate, TeamProfile

MY_SCHEDULE = reverse("teams:my_schedule")
ROSTER = reverse("teams:roster")
PARTS = reverse("teams:parts_list")


def service_page(service):
    return reverse("worship:service", kwargs={"public_id": service.public_id})


def assign_page(service):
    return reverse("teams:assign", kwargs={"public_id": service.public_id})


def reply_url(assignment):
    return reverse("teams:reply", kwargs={"public_id": assignment.public_id})


def remove_url(assignment):
    return reverse(
        "teams:assignment_remove",
        kwargs={
            "public_id": assignment.service.public_id,
            "assignment_id": assignment.public_id,
        },
    )


class TeamsViewTestCase(TestCase):
    def setUp(self):
        complete_setup()
        self.leader = make_user(roles=["worship_leader"])
        self.pastor = make_user(roles=["pastoral_staff"])
        self.member = make_user(
            roles=["team_member"], first_name="Kim", last_name="Cruz"
        )
        self.office = make_user(roles=["office_staff"])
        self.bass = make_team_part("Bass guitar")
        make_team_profile(self.member, [self.bass])
        self.service = make_service()


class ModuleSwitchTests(TeamsViewTestCase):
    def pages(self, assignment):
        return [
            MY_SCHEDULE,
            reverse("teams:my_parts"),
            reverse("teams:blackout_create"),
            ROSTER,
            PARTS,
            assign_page(self.service),
            reply_url(assignment),
        ]

    def test_switched_off_teams_returns_404_and_keeps_the_data(self):
        assignment = make_assignment(self.service, self.member, self.bass)
        complete_setup(disabled_modules=["teams"])
        self.client.force_login(self.leader)
        for url in self.pages(assignment):
            self.assertEqual(self.client.get(url).status_code, 404, url)
        self.assertNotContains(self.client.get(service_page(self.service)), 'id="team"')
        self.assertTrue(Assignment.objects.filter(pk=assignment.pk).exists())

    def test_teams_counts_as_off_while_worship_is_off(self):
        assignment = make_assignment(self.service, self.member, self.bass)
        complete_setup(disabled_modules=["worship"])
        self.client.force_login(self.leader)
        for url in self.pages(assignment):
            self.assertEqual(self.client.get(url).status_code, 404, url)

    def test_signed_out_people_are_sent_to_sign_in(self):
        response = self.client.get(MY_SCHEDULE)
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("accounts:login"), response["Location"])

    def test_the_nav_and_menu_link_to_my_schedule(self):
        self.client.force_login(self.member)
        page = self.client.get(reverse("home"))
        self.assertContains(page, f'href="{MY_SCHEDULE}"')


class MySchedulePageTests(TeamsViewTestCase):
    def test_shows_my_assignments_parts_and_blackouts(self):
        make_assignment(self.service, self.member, self.bass)
        other = make_user()
        make_assignment(make_service(), other, self.bass)
        BlackoutDate.objects.create(
            person=self.member,
            starts_on=rostering.church_today() + datetime.timedelta(days=30),
            ends_on=rostering.church_today() + datetime.timedelta(days=31),
            note="Away",
        )
        self.client.force_login(self.member)
        page = self.client.get(MY_SCHEDULE)
        self.assertEqual(len(page.context["assignments"]), 1)
        self.assertContains(page, ">Accept</button>")
        self.assertContains(page, "Bass guitar")
        self.assertContains(page, "Away")

    def test_a_team_member_edits_their_own_parts(self):
        drums = make_team_part("Percussion")
        self.client.force_login(self.member)
        response = self.client.post(reverse("teams:my_parts"), {"parts": [drums.pk]})
        self.assertRedirects(response, MY_SCHEDULE)
        self.assertEqual(rostering.parts_of(self.member), [drums])

    def test_people_not_on_the_team_are_refused_my_parts_and_blackouts(self):
        """Only holders of teams.view_assignment have a Team Profile or
        Blackout Dates; Office Staff don't."""
        day = (rostering.church_today() + datetime.timedelta(days=60)).isoformat()
        own = BlackoutDate.objects.create(
            person=self.office,
            starts_on=rostering.church_today(),
            ends_on=rostering.church_today(),
        )
        self.client.force_login(self.office)
        for url in (reverse("teams:my_parts"), reverse("teams:blackout_create")):
            self.assertEqual(self.client.get(url).status_code, 403, url)
        self.assertEqual(
            self.client.post(
                reverse("teams:blackout_create"),
                {"starts_on": day, "ends_on": day, "note": ""},
            ).status_code,
            403,
        )
        remove = reverse("teams:blackout_delete", kwargs={"pk": own.pk})
        self.assertEqual(self.client.post(remove).status_code, 403)
        self.assertEqual(
            self.client.post(
                reverse("teams:my_parts"), {"parts": [self.bass.pk]}
            ).status_code,
            403,
        )
        self.assertFalse(TeamProfile.objects.filter(user=self.office).exists())
        page = self.client.get(reverse("home"))
        self.assertNotContains(page, ">My schedule</a>")
        self.assertRedirects(
            self.client.get(MY_SCHEDULE), reverse("notifications:list")
        )

    def test_adding_a_blackout_over_an_assignment_shows_the_refusal(self):
        make_assignment(self.service, self.member, self.bass)
        day = rostering.service_day(self.service)
        self.client.force_login(self.member)
        response = self.client.post(
            reverse("teams:blackout_create"),
            {"starts_on": day.isoformat(), "ends_on": day.isoformat(), "note": ""},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Decline it on My schedule first")
        self.assertFalse(BlackoutDate.objects.exists())

    def test_adding_and_removing_a_blackout(self):
        day = rostering.church_today() + datetime.timedelta(days=60)
        self.client.force_login(self.member)
        response = self.client.post(
            reverse("teams:blackout_create"),
            {"starts_on": day.isoformat(), "ends_on": day.isoformat(), "note": ""},
        )
        self.assertRedirects(response, MY_SCHEDULE)
        blackout = BlackoutDate.objects.get(person=self.member)
        remove = reverse("teams:blackout_delete", kwargs={"pk": blackout.pk})
        self.client.force_login(self.leader)
        self.assertEqual(self.client.post(remove).status_code, 404)
        self.client.force_login(self.member)
        self.assertRedirects(self.client.post(remove), MY_SCHEDULE)
        self.assertFalse(BlackoutDate.objects.exists())

    def test_a_blackout_ending_before_it_starts_is_a_form_error(self):
        self.client.force_login(self.member)
        response = self.client.post(
            reverse("teams:blackout_create"),
            {"starts_on": "2031-03-09", "ends_on": "2031-03-02", "note": ""},
        )
        self.assertContains(response, "can&#x27;t be before the first")


class ReplyViewTests(TeamsViewTestCase):
    def setUp(self):
        super().setUp()
        self.assignment = make_assignment(self.service, self.member, self.bass)

    def test_the_assigned_person_accepts(self):
        self.client.force_login(self.member)
        response = self.client.post(reply_url(self.assignment), {"reply": "accepted"})
        self.assertRedirects(response, MY_SCHEDULE)
        self.assignment.refresh_from_db()
        self.assertEqual(self.assignment.reply, Assignment.Reply.ACCEPTED)

    def test_replying_from_the_service_page_goes_back_there(self):
        self.client.force_login(self.member)
        response = self.client.post(
            reply_url(self.assignment), {"reply": "declined", "back": "service"}
        )
        self.assertRedirects(response, service_page(self.service))

    def test_someone_else_gets_a_404(self):
        self.client.force_login(self.leader)
        response = self.client.post(reply_url(self.assignment), {"reply": "accepted"})
        self.assertEqual(response.status_code, 404)
        self.assignment.refresh_from_db()
        self.assertEqual(self.assignment.reply, Assignment.Reply.PENDING)

    def test_a_refused_reply_shows_why(self):
        self.service.is_cancelled = True
        self.service.save()
        self.client.force_login(self.member)
        response = self.client.post(
            reply_url(self.assignment), {"reply": "accepted"}, follow=True
        )
        self.assertContains(response, "cancelled, so its team can&#x27;t change")


class AssignViewTests(TeamsViewTestCase):
    def test_the_leader_assigns_someone_with_the_part(self):
        self.client.force_login(self.leader)
        page = self.client.get(assign_page(self.service), {"part": self.bass.pk})
        self.assertContains(page, "Kim Cruz")
        response = self.client.post(
            assign_page(self.service), {"part": self.bass.pk, "person": self.member.pk}
        )
        # Phase 9C: the page stays open, with the team so far, and "Done"
        # goes back to the service.
        self.assertRedirects(response, assign_page(self.service))
        assignment = Assignment.objects.get()
        self.assertEqual(assignment.person, self.member)
        self.assertEqual(assignment.assigned_by, self.leader)
        page = self.client.get(assign_page(self.service))
        self.assertContains(page, "Praise Team so far")
        self.assertContains(page, "Kim Cruz")
        self.assertContains(
            page,
            f'href="{service_page(self.service)}" class="btn btn-primary chord-btn">Done',
        )

    def test_people_without_the_part_arent_offered(self):
        outsider = make_user(first_name="Lee", last_name="Outsider")
        self.client.force_login(self.leader)
        page = self.client.get(assign_page(self.service), {"part": self.bass.pk})
        self.assertNotContains(page, "Lee Outsider")
        response = self.client.post(
            assign_page(self.service), {"part": self.bass.pk, "person": outsider.pk}
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Assignment.objects.exists())

    def test_someone_with_parts_but_not_on_the_team_isnt_offered(self):
        """A profile left from before, without teams.view_assignment."""
        make_team_profile(self.office, [self.bass])
        self.office.first_name, self.office.last_name = "Ola", "Office"
        self.office.save()
        self.client.force_login(self.leader)
        page = self.client.get(assign_page(self.service), {"part": self.bass.pk})
        self.assertNotContains(page, "Ola Office")
        response = self.client.post(
            assign_page(self.service), {"part": self.bass.pk, "person": self.office.pk}
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Assignment.objects.exists())

    def test_a_blacked_out_person_is_listed_with_the_reason_and_not_offered(self):
        day = rostering.service_day(self.service)
        BlackoutDate.objects.create(person=self.member, starts_on=day, ends_on=day)
        self.client.force_login(self.leader)
        page = self.client.get(assign_page(self.service), {"part": self.bass.pk})
        self.assertContains(page, "Can't be assigned")
        self.assertContains(page, "a blackout date")
        self.assertEqual(page.context["form"].fields["person"].choices, [])
        self.client.post(
            assign_page(self.service), {"part": self.bass.pk, "person": self.member.pk}
        )
        self.assertFalse(Assignment.objects.exists())

    def test_a_cancelled_service_shows_why_it_cant_be_assigned(self):
        cancelled = make_service(is_cancelled=True)
        self.client.force_login(self.leader)
        page = self.client.get(assign_page(cancelled))
        self.assertContains(page, "is cancelled, so its team can&#x27;t change")

    def test_an_unknown_part_is_a_404(self):
        self.client.force_login(self.leader)
        self.assertEqual(
            self.client.get(assign_page(self.service), {"part": "x"}).status_code, 404
        )
        self.assertEqual(self.client.post(assign_page(self.service)).status_code, 404)

    def test_people_without_the_permission_are_refused(self):
        # Pastors may assign since Phase 9C.
        for user in (self.member, self.office):
            self.client.force_login(user)
            self.assertEqual(
                self.client.get(assign_page(self.service)).status_code, 403
            )
            response = self.client.post(
                assign_page(self.service),
                {"part": self.bass.pk, "person": self.member.pk},
            )
            self.assertEqual(response.status_code, 403)
        self.assertFalse(Assignment.objects.exists())

    def test_the_leader_removes_an_assignment_others_cant(self):
        assignment = make_assignment(self.service, self.member, self.bass)
        self.client.force_login(self.member)
        self.assertEqual(self.client.post(remove_url(assignment)).status_code, 403)
        self.client.force_login(self.leader)
        self.assertRedirects(
            self.client.post(remove_url(assignment)), service_page(self.service)
        )
        self.assertFalse(Assignment.objects.exists())

    def test_a_past_services_assignment_isnt_removed(self):
        past = make_service(starts_at=timezone.now() - datetime.timedelta(hours=1))
        assignment = make_assignment(past, self.member, self.bass)
        self.client.force_login(self.leader)
        response = self.client.post(remove_url(assignment), follow=True)
        self.assertContains(response, "already taken place")
        self.assertTrue(Assignment.objects.exists())


class ServicePageTeamTests(TeamsViewTestCase):
    def test_team_members_see_the_team_with_their_reply_buttons(self):
        make_assignment(self.service, self.member, self.bass)
        self.client.force_login(self.member)
        page = self.client.get(service_page(self.service))
        self.assertContains(page, 'id="team"')
        self.assertContains(page, "Kim Cruz")
        self.assertContains(page, ">Accept</button>")
        self.assertNotContains(page, ">Assign</a>")
        self.assertNotContains(page, ">Remove</button>")

    def test_a_declined_assignment_stays_for_the_leader_to_fill(self):
        make_assignment(self.service, self.member, self.bass, reply="declined")
        self.client.force_login(self.leader)
        page = self.client.get(service_page(self.service))
        self.assertContains(page, "Kim Cruz")
        self.assertContains(page, "Declined")
        self.assertContains(page, "Needs filling")
        self.assertContains(page, ">Assign</a>")

    def test_people_without_the_permission_dont_see_the_team(self):
        make_assignment(self.service, self.member, self.bass)
        self.client.force_login(self.office)
        self.assertNotContains(self.client.get(service_page(self.service)), 'id="team"')

    def test_a_past_service_shows_its_team_without_changes(self):
        past = make_service(starts_at=timezone.now() - datetime.timedelta(hours=1))
        make_assignment(past, self.member, self.bass)
        self.client.force_login(self.leader)
        page = self.client.get(service_page(past))
        self.assertContains(page, "Kim Cruz")
        self.assertContains(page, "already taken place")
        self.assertNotContains(page, ">Assign</a>")
        self.assertNotContains(page, ">Remove</button>")


class RosterAndPartsTests(TeamsViewTestCase):
    def test_the_leader_and_pastor_see_the_roster_team_members_dont(self):
        for user in (self.leader, self.pastor):
            self.client.force_login(user)
            self.assertContains(self.client.get(ROSTER), "Kim Cruz")
        for user in (self.member, self.office):
            self.client.force_login(user)
            self.assertEqual(self.client.get(ROSTER).status_code, 403)

    def test_only_the_leader_edits_someone_elses_parts(self):
        drums = make_team_part("Percussion")
        url = reverse("teams:person_parts", kwargs={"pk": self.member.pk})
        for user in (self.pastor, self.office):
            self.client.force_login(user)
            self.assertEqual(
                self.client.post(url, {"parts": [drums.pk]}).status_code, 403
            )
        self.client.force_login(self.leader)
        self.assertContains(self.client.get(url), "Team parts: Kim Cruz")
        self.assertRedirects(self.client.post(url, {"parts": [drums.pk]}), ROSTER)
        self.assertEqual(rostering.parts_of(self.member), [drums])

    def test_the_leader_keeps_the_team_parts_list(self):
        self.client.force_login(self.leader)
        self.assertContains(self.client.get(PARTS), "Acoustic guitar")
        response = self.client.post(
            reverse("teams:parts_create"),
            {"name": "Strings", "description": "", "sort_order": 70, "is_active": "on"},
        )
        self.assertRedirects(response, PARTS)
        self.client.force_login(self.member)
        self.assertEqual(self.client.get(PARTS).status_code, 403)

    def test_the_teams_tabs_follow_permissions(self):
        self.client.force_login(self.member)
        page = self.client.get(MY_SCHEDULE)
        self.assertNotContains(page, f'href="{ROSTER}"')
        self.client.force_login(self.leader)
        page = self.client.get(MY_SCHEDULE)
        self.assertContains(page, f'href="{ROSTER}"')
        self.assertContains(page, f'href="{PARTS}"')


class DefaultRoleTests(TestCase):
    def test_default_roles_get_the_teams_permissions(self):
        leader = DEFAULT_ROLE_PERMISSIONS["worship_leader"]
        self.assertIn("teams.add_assignment", leader)
        self.assertIn("teams.change_teamprofile", leader)
        # Phase 9C (owner, 2026-11-26): the pastor assigns the team too.
        pastor = DEFAULT_ROLE_PERMISSIONS["pastoral_staff"]
        self.assertIn("teams.add_assignment", pastor)
        self.assertIn("teams.delete_assignment", pastor)
        self.assertNotIn("teams.change_teamprofile", pastor)
        self.assertEqual(
            [
                p
                for p in DEFAULT_ROLE_PERMISSIONS["team_member"]
                if p.startswith("teams.")
            ],
            ["teams.view_assignment"],
        )
        member = make_user(roles=["team_member"])
        self.assertTrue(member.has_perm("teams.view_assignment"))
