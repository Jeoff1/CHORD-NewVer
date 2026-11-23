"""The roster rules (Design-Decisions, Phase 8, decided 2026-11-23)."""

import datetime
import zoneinfo

from django.test import TestCase
from django.utils import timezone

from apps.audit.models import AuditEvent
from apps.core.testing import (
    complete_setup,
    make_assignment,
    make_service,
    make_team_part,
    make_team_profile,
    make_user,
)
from apps.teams import rostering
from apps.teams.models import Assignment, BlackoutDate, TeamPart, TeamProfile

MANILA = zoneinfo.ZoneInfo("Asia/Manila")
Reply = Assignment.Reply


def days_ahead(days):
    return rostering.church_today() + datetime.timedelta(days=days)


class RosterTestCase(TestCase):
    def setUp(self):
        complete_setup()
        self.leader = make_user(roles=["worship_leader"])
        self.bass = make_team_part("Bass guitar")
        self.drums = make_team_part("Percussion")
        self.player = make_user(first_name="Sam", last_name="Reyes")
        make_team_profile(self.player, [self.bass])
        self.service = make_service()

    def refused(self, call, *args):
        with self.assertRaises(rostering.RosterRefused) as caught:
            call(*args)
        return str(caught.exception)


class SeededPartsTests(TestCase):
    def test_neutral_parts_are_seeded(self):
        self.assertEqual(
            list(TeamPart.objects.values_list("name", flat=True)),
            ["Vocals", "Acoustic guitar", "Electric guitar", "Bass", "Keys", "Drums"],
        )


class AssigningTests(RosterTestCase):
    def test_someone_with_the_part_is_assigned_pending(self):
        assignment = rostering.assign(self.service, self.bass, self.player, self.leader)
        self.assertEqual(assignment.reply, Reply.PENDING)
        self.assertEqual(assignment.assigned_by, self.leader)

    def test_only_people_whose_profile_has_the_part_can_be_assigned(self):
        message = self.refused(
            rostering.assign, self.service, self.drums, self.player, self.leader
        )
        self.assertIn("Team Profile doesn't have Percussion", message)
        no_profile = make_user()
        self.refused(rostering.assign, self.service, self.bass, no_profile, self.leader)
        self.assertFalse(Assignment.objects.exists())

    def test_nobody_can_be_assigned_on_a_blackout_date(self):
        day = rostering.service_day(self.service)
        BlackoutDate.objects.create(person=self.player, starts_on=day, ends_on=day)
        message = self.refused(
            rostering.assign, self.service, self.bass, self.player, self.leader
        )
        self.assertIn("blackout date", message)
        self.assertFalse(Assignment.objects.exists())

    def test_a_blackout_range_covers_every_day_in_it(self):
        day = rostering.service_day(self.service)
        BlackoutDate.objects.create(
            person=self.player,
            starts_on=day - datetime.timedelta(days=2),
            ends_on=day + datetime.timedelta(days=2),
        )
        self.refused(
            rostering.assign, self.service, self.bass, self.player, self.leader
        )

    def test_blackout_days_follow_the_church_time_zone(self):
        complete_setup(time_zone="Asia/Manila")
        late = make_service(
            starts_at=datetime.datetime(2031, 3, 2, 23, 30, tzinfo=MANILA)
        )
        # 00:30 on March 3 in Manila is still March 2 in UTC.
        early = make_service(
            starts_at=datetime.datetime(2031, 3, 3, 0, 30, tzinfo=MANILA)
        )
        march_2 = datetime.date(2031, 3, 2)
        BlackoutDate.objects.create(
            person=self.player, starts_on=march_2, ends_on=march_2
        )
        self.refused(rostering.assign, late, self.bass, self.player, self.leader)
        rostering.assign(early, self.bass, self.player, self.leader)

    def test_a_cancelled_or_past_service_takes_no_new_assignments(self):
        cancelled = make_service(is_cancelled=True)
        past = make_service(starts_at=timezone.now() - datetime.timedelta(hours=1))
        self.assertIn(
            "cancelled",
            self.refused(
                rostering.assign, cancelled, self.bass, self.player, self.leader
            ),
        )
        self.assertIn(
            "already taken place",
            self.refused(rostering.assign, past, self.bass, self.player, self.leader),
        )

    def test_once_per_part_but_a_person_may_take_two_parts(self):
        make_team_profile(self.player, [self.bass, self.drums])
        rostering.assign(self.service, self.bass, self.player, self.leader)
        self.assertIn(
            "Already assigned",
            self.refused(
                rostering.assign, self.service, self.bass, self.player, self.leader
            ),
        )
        rostering.assign(self.service, self.drums, self.player, self.leader)
        self.assertEqual(self.service.assignments.count(), 2)

    def test_a_switched_off_part_or_deactivated_person_cant_be_assigned(self):
        self.bass.is_active = False
        self.bass.save()
        self.refused(
            rostering.assign, self.service, self.bass, self.player, self.leader
        )
        self.bass.is_active = True
        self.bass.save()
        self.player.is_active = False
        self.player.save()
        self.refused(
            rostering.assign, self.service, self.bass, self.player, self.leader
        )

    def test_candidates_give_each_person_a_reason_or_none(self):
        blocked = make_user(first_name="Ana")
        make_team_profile(blocked, [self.bass])
        day = rostering.service_day(self.service)
        BlackoutDate.objects.create(person=blocked, starts_on=day, ends_on=day)
        reasons = dict(rostering.candidates(self.service, self.bass))
        self.assertEqual(reasons[self.player], "")
        self.assertIn("blackout date", reasons[blocked])
        self.assertNotIn(self.leader, reasons)

    def test_assigning_and_removing_are_in_the_audit_trail(self):
        assignment = rostering.assign(self.service, self.bass, self.player, self.leader)
        rostering.remove(assignment, self.leader)
        events = AuditEvent.objects.filter(content_type__model="assignment")
        self.assertEqual(
            list(events.values_list("action", flat=True).order_by("pk")),
            [AuditEvent.Action.CREATED, AuditEvent.Action.DELETED],
        )
        self.assertEqual(
            events.order_by("pk").first().changes["Person"], ["", "Sam Reyes"]
        )
        self.assertFalse(Assignment.objects.exists())

    def test_a_past_services_team_cant_be_removed(self):
        past = make_service(starts_at=timezone.now() - datetime.timedelta(hours=1))
        assignment = make_assignment(past, self.player, self.bass)
        self.refused(rostering.remove, assignment, self.leader)
        self.assertTrue(Assignment.objects.filter(pk=assignment.pk).exists())


class ReplyTests(RosterTestCase):
    def setUp(self):
        super().setUp()
        self.assignment = rostering.assign(
            self.service, self.bass, self.player, self.leader
        )

    def test_the_person_accepts_or_declines_once(self):
        rostering.reply(self.assignment, self.player, Reply.ACCEPTED)
        self.assignment.refresh_from_db()
        self.assertEqual(self.assignment.reply, Reply.ACCEPTED)
        self.assertIsNotNone(self.assignment.replied_at)
        self.assertIn(
            "already accepted",
            self.refused(rostering.reply, self.assignment, self.player, Reply.DECLINED),
        )

    def test_a_decline_is_recorded_in_the_audit_trail(self):
        rostering.reply(self.assignment, self.player, Reply.DECLINED)
        event = AuditEvent.objects.filter(action=AuditEvent.Action.CHANGED).get()
        self.assertEqual(event.changes, {"Reply": ["Pending", "Declined"]})
        self.assertEqual(event.actor, self.player)

    def test_only_the_assigned_person_replies(self):
        self.refused(rostering.reply, self.assignment, self.leader, Reply.ACCEPTED)
        self.refused(rostering.reply, self.assignment, self.player, Reply.PENDING)

    def test_no_replies_on_a_cancelled_or_past_service(self):
        self.service.is_cancelled = True
        self.service.save()
        self.refused(rostering.reply, self.assignment, self.player, Reply.ACCEPTED)
        past = make_service(starts_at=timezone.now() - datetime.timedelta(hours=1))
        old = make_assignment(past, self.player, self.bass)
        self.refused(rostering.reply, old, self.player, Reply.ACCEPTED)
        self.assignment.refresh_from_db()
        self.assertEqual(self.assignment.reply, Reply.PENDING)


class BlackoutTests(RosterTestCase):
    def test_adding_one_is_in_the_audit_trail(self):
        blackout = rostering.add_blackout(self.player, days_ahead(1), days_ahead(3))
        event = AuditEvent.objects.get(content_type__model="blackoutdate")
        self.assertEqual(event.actor, self.player)
        self.assertEqual(event.changes["Dates"][1], blackout.date_range())

    def test_one_over_a_pending_assignment_is_refused_pointing_to_decline(self):
        rostering.assign(self.service, self.bass, self.player, self.leader)
        day = rostering.service_day(self.service)
        message = self.refused(rostering.add_blackout, self.player, day, day)
        self.assertIn("Decline it", message)
        self.assertFalse(BlackoutDate.objects.exists())

    def test_one_over_an_accepted_assignment_is_refused_pointing_to_a_swap(self):
        assignment = rostering.assign(self.service, self.bass, self.player, self.leader)
        rostering.reply(assignment, self.player, Reply.ACCEPTED)
        day = rostering.service_day(self.service)
        message = self.refused(
            rostering.add_blackout,
            self.player,
            day - datetime.timedelta(days=1),
            day + datetime.timedelta(days=1),
        )
        self.assertIn("ask for a swap", message)

    def test_a_declined_or_cancelled_assignment_doesnt_block_it(self):
        assignment = rostering.assign(self.service, self.bass, self.player, self.leader)
        rostering.reply(assignment, self.player, Reply.DECLINED)
        cancelled = make_service(is_cancelled=True)
        make_assignment(cancelled, self.player, self.bass)
        start = min(
            rostering.service_day(self.service), rostering.service_day(cancelled)
        )
        end = max(rostering.service_day(self.service), rostering.service_day(cancelled))
        rostering.add_blackout(self.player, start, end)
        self.assertEqual(BlackoutDate.objects.count(), 1)

    def test_days_the_wrong_way_round_or_already_passed_are_refused(self):
        self.refused(rostering.add_blackout, self.player, days_ahead(3), days_ahead(1))
        self.refused(
            rostering.add_blackout, self.player, days_ahead(-5), days_ahead(-1)
        )
        rostering.add_blackout(self.player, days_ahead(-1), days_ahead(0))

    def test_only_the_person_removes_theirs(self):
        blackout = rostering.add_blackout(self.player, days_ahead(1), days_ahead(1))
        self.refused(rostering.remove_blackout, blackout, self.leader)
        rostering.remove_blackout(blackout, self.player)
        self.assertFalse(BlackoutDate.objects.exists())

    def test_date_range_wording(self):
        one = BlackoutDate(
            starts_on=datetime.date(2031, 3, 2), ends_on=datetime.date(2031, 3, 2)
        )
        span = BlackoutDate(
            starts_on=datetime.date(2031, 3, 2), ends_on=datetime.date(2031, 3, 9)
        )
        years = BlackoutDate(
            starts_on=datetime.date(2031, 12, 30), ends_on=datetime.date(2032, 1, 2)
        )
        self.assertEqual(one.date_range(), "Mar 2, 2031")
        self.assertEqual(span.date_range(), "Mar 2 to Mar 9, 2031")
        self.assertEqual(years.date_range(), "Dec 30, 2031 to Jan 2, 2032")


class TeamProfileTests(RosterTestCase):
    def test_setting_parts_records_the_change(self):
        rostering.set_parts(self.player, [self.bass, self.drums], self.player)
        self.assertEqual(set(rostering.parts_of(self.player)), {self.bass, self.drums})
        event = AuditEvent.objects.get(content_type__model="teamprofile")
        self.assertEqual(
            event.changes["Team parts"], ["Bass guitar", "Bass guitar, Percussion"]
        )

    def test_a_new_profile_is_created_and_holds_only_parts(self):
        newcomer = make_user()
        rostering.set_parts(newcomer, [self.drums], self.leader)
        profile = TeamProfile.objects.get(user=newcomer)
        self.assertEqual(list(profile.parts.all()), [self.drums])
        fields = {field.name for field in TeamProfile._meta.get_fields()}
        self.assertFalse({name for name in fields if "range" in name})
