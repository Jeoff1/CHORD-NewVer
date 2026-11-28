"""Each church keeps its own team (28 Nov 2026, decision 0014): Team Parts,
Team Profiles and Blackout Dates belong to one church, so a church
registered after Phase 9B gets the Praise Team step and nothing of another
church's team."""

import datetime

from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import Membership, Role
from apps.church.middleware import SESSION_KEY
from apps.core.testing import (
    complete_setup,
    first_church,
    make_church,
    make_service,
    make_team_profile,
    make_user,
)
from apps.teams import rostering
from apps.teams.models import TeamPart


def join(user, church, role):
    membership = Membership.objects.create(user=user, church=church)
    membership.roles.add(Role.objects.get(church=church, key=role))


class ChurchTeamsTests(TestCase):
    def setUp(self):
        self.a = complete_setup(first_church())
        self.b = complete_setup(make_church("Hope Chapel"))
        self.leader_b = make_user(church=self.b, roles=["worship_leader"])
        # One person on both churches' teams.
        self.ana = make_user(roles=["team_member"])
        join(self.ana, self.b, "team_member")
        self.vocals_a = TeamPart.objects.for_church(self.a).get(name="Vocals")
        self.vocals_b = TeamPart.objects.for_church(self.b).get(name="Vocals")

    def test_a_new_church_starts_with_its_own_team_parts(self):
        self.assertNotEqual(self.vocals_a.pk, self.vocals_b.pk)
        names = set(TeamPart.objects.for_church(self.b).values_list("name", flat=True))
        self.assertIn("Drums", names)

    def test_a_person_has_a_team_profile_in_each_church(self):
        rostering.set_parts(self.ana, [self.vocals_a], self.ana, self.a)
        rostering.set_parts(self.ana, [self.vocals_b], self.ana, self.b)
        self.assertEqual(rostering.parts_of(self.ana, self.a), [self.vocals_a])
        self.assertEqual(rostering.parts_of(self.ana, self.b), [self.vocals_b])

    def test_another_churchs_part_cant_go_in_a_profile_or_an_assignment(self):
        with self.assertRaises(rostering.RosterRefused):
            rostering.set_parts(self.ana, [self.vocals_a], self.ana, self.b)
        service_b = make_service(church=self.b)
        make_team_profile(self.ana, [self.vocals_a])
        with self.assertRaises(rostering.RosterRefused):
            rostering.assign(service_b, self.vocals_a, self.ana, self.leader_b)

    def test_candidates_and_blackouts_are_the_services_church(self):
        service_b = make_service(church=self.b)
        make_team_profile(self.ana, [self.vocals_b])
        day = rostering.service_day(service_b)
        # A blackout at the other church doesn't keep Ana off this service.
        rostering.add_blackout(self.ana, self.a, day, day)
        candidates = rostering.candidates(service_b, self.vocals_b)
        self.assertEqual(candidates, [(self.ana, "")])
        # Only church B's team: church A's people aren't offered.
        only_a = make_user(roles=["team_member"])
        make_team_profile(only_a, [self.vocals_a])
        self.assertNotIn(
            only_a,
            [person for person, _ in rostering.candidates(service_b, self.vocals_b)],
        )

    def test_my_schedule_shows_the_current_churchs_assignments_only(self):
        service_a = make_service(name="Aldermoor Sunday")
        service_b = make_service(church=self.b, name="Hope Sunday")
        make_team_profile(self.ana, [self.vocals_a])
        make_team_profile(self.ana, [self.vocals_b])
        rostering.assign(service_a, self.vocals_a, self.ana, self.ana)
        rostering.assign(service_b, self.vocals_b, self.ana, self.leader_b)
        self.assertEqual(
            [a.service for a in rostering.upcoming_assignments(self.ana, self.b)],
            [service_b],
        )
        self.assertEqual(
            [a.service for a in rostering.upcoming_assignments(self.ana, self.a)],
            [service_a],
        )

    def test_the_praise_team_step_shows_in_a_church_registered_later(self):
        service_b = make_service(church=self.b, name="Hope Sunday")
        self.client.force_login(self.leader_b)
        session = self.client.session
        session[SESSION_KEY] = self.b.pk
        session.save()
        page = self.client.get(
            reverse("worship:service", kwargs={"public_id": service_b.public_id})
        )
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, "Praise Team")
        self.assertContains(
            page, reverse("teams:assign", kwargs={"public_id": service_b.public_id})
        )

    def test_the_roster_lists_only_the_churchs_team(self):
        only_a = make_user(roles=["team_member"], first_name="Aldous")
        make_team_profile(only_a, [self.vocals_a])
        self.client.force_login(self.leader_b)
        session = self.client.session
        session[SESSION_KEY] = self.b.pk
        session.save()
        page = self.client.get(reverse("teams:roster"))
        self.assertNotContains(page, "Aldous")

    def test_blackout_dates_are_kept_per_church(self):
        day = rostering.church_today(self.a) + datetime.timedelta(days=40)
        blackout = rostering.add_blackout(self.ana, self.a, day, day)
        self.assertEqual(
            list(rostering.upcoming_blackouts(self.ana, self.a)), [blackout]
        )
        self.assertEqual(list(rostering.upcoming_blackouts(self.ana, self.b)), [])


class SwitchOnWhereLockedTests(TestCase):
    def test_teams_comes_on_where_it_was_locked_and_stays_as_chosen_elsewhere(self):
        import importlib

        from django.apps import apps as django_apps

        migration = importlib.import_module(
            "apps.teams.migrations.0007_switch_on_where_it_was_locked"
        )
        first = complete_setup(first_church())
        first.disabled_modules = ["teams"]
        first.save()
        later = complete_setup(make_church("Hope Chapel"))
        later.disabled_modules = ["members", "teams"]
        later.save()
        migration.forwards(django_apps, None)
        first.refresh_from_db()
        later.refresh_from_db()
        self.assertEqual(first.disabled_modules, ["teams"])
        self.assertEqual(later.disabled_modules, ["members"])
