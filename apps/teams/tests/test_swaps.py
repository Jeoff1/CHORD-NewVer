"""Swap Requests (Design-Decisions, Phase 8, decision 5)."""

import datetime
import threading
from unittest import mock

from django.db import connection
from django.test import TestCase, TransactionTestCase
from django.urls import reverse
from django.utils import timezone

from apps.audit.models import AuditEvent
from apps.core.testing import (
    complete_setup,
    first_church,
    make_assignment,
    make_service,
    make_team_part,
    make_team_profile,
    make_user,
)
from apps.teams import rostering
from apps.teams.models import Assignment, BlackoutDate, SwapRequest

Reply = Assignment.Reply
MY_SCHEDULE = reverse("teams:my_schedule")


def action_url(swap, action):
    return reverse(
        "teams:swap_action", kwargs={"public_id": swap.public_id, "action": action}
    )


class SwapTestCase(TestCase):
    def setUp(self):
        complete_setup()
        self.leader = make_user(roles=["worship_leader"])
        self.bass = make_team_part("Bass guitar")
        self.asker = make_user(roles=["team_member"], first_name="Ann", last_name="Ask")
        self.taker = make_user(
            roles=["team_member"], first_name="Tom", last_name="Take"
        )
        make_team_profile(self.asker, [self.bass])
        make_team_profile(self.taker, [self.bass])
        self.service = make_service()
        self.assignment = rostering.assign(
            self.service, self.bass, self.asker, self.leader
        )
        rostering.reply(self.assignment, self.asker, Reply.ACCEPTED)

    def refused(self, call, *args):
        with self.assertRaises(rostering.RosterRefused) as caught:
            call(*args)
        return str(caught.exception)


class AskingTests(SwapTestCase):
    def test_an_accepted_or_pending_person_asks_and_withdraws(self):
        swap = rostering.request_swap(self.assignment, self.asker)
        self.assertTrue(swap.is_open)
        self.assertEqual(swap.part, self.bass)
        self.assertIn(
            "already asked",
            self.refused(rostering.request_swap, self.assignment, self.asker),
        )
        self.refused(rostering.withdraw_swap, swap, self.taker)
        rostering.withdraw_swap(swap, self.asker)
        swap.refresh_from_db()
        self.assertEqual(swap.status, SwapRequest.Status.WITHDRAWN)
        self.assertIn(
            "withdrawn", self.refused(rostering.withdraw_swap, swap, self.asker)
        )
        # A pending person may ask too.
        pending = make_assignment(make_service(), self.asker, self.bass)
        rostering.request_swap(pending, self.asker)

    def test_only_the_assigned_person_on_a_future_open_service_may_ask(self):
        self.refused(rostering.request_swap, self.assignment, self.taker)
        declined = make_assignment(
            make_service(), self.asker, self.bass, reply="declined"
        )
        self.assertIn(
            "declined", self.refused(rostering.request_swap, declined, self.asker)
        )
        cancelled = make_assignment(
            make_service(is_cancelled=True), self.asker, self.bass, reply="accepted"
        )
        self.refused(rostering.request_swap, cancelled, self.asker)
        past = make_assignment(
            make_service(starts_at=timezone.now() - datetime.timedelta(hours=1)),
            self.asker,
            self.bass,
            reply="accepted",
        )
        self.refused(rostering.request_swap, past, self.asker)
        self.assertFalse(SwapRequest.objects.exists())

    def test_declining_or_removal_withdraws_an_open_request(self):
        pending = make_assignment(make_service(), self.asker, self.bass)
        swap = rostering.request_swap(pending, self.asker)
        rostering.reply(pending, self.asker, Reply.DECLINED)
        swap.refresh_from_db()
        self.assertEqual(swap.status, SwapRequest.Status.WITHDRAWN)
        other = rostering.request_swap(self.assignment, self.asker)
        rostering.remove(self.assignment, self.leader)
        other.refresh_from_db()
        self.assertEqual(other.status, SwapRequest.Status.WITHDRAWN)
        self.assertEqual(rostering.swaps_open_to(self.taker, first_church()), [])


class WhoSeesItTests(SwapTestCase):
    def setUp(self):
        super().setUp()
        self.swap = rostering.request_swap(self.assignment, self.asker)

    def test_eligible_people_see_it_and_others_dont(self):
        self.assertEqual(
            rostering.swaps_open_to(self.taker, first_church()), [self.swap]
        )
        self.assertEqual(rostering.swaps_open_to(self.asker, first_church()), [])

        no_part = make_user(roles=["team_member"])
        make_team_profile(no_part, [make_team_part()])
        blacked_out = make_user(roles=["team_member"])
        make_team_profile(blacked_out, [self.bass])
        day = rostering.service_day(self.service)
        BlackoutDate.objects.create(
            church=first_church(), person=blacked_out, starts_on=day, ends_on=day
        )
        already_on = make_user(roles=["team_member"])
        make_team_profile(already_on, [self.bass])
        make_assignment(self.service, already_on, make_team_part())
        not_on_team = make_user(roles=["office_staff"])
        make_team_profile(not_on_team, [self.bass])
        for person in (no_part, blacked_out, already_on, not_on_team):
            self.assertEqual(
                rostering.swaps_open_to(person, first_church()), [], person
            )
            self.refused(rostering.take_swap, self.swap, person)

    def test_a_cancelled_service_takes_no_swaps(self):
        self.service.is_cancelled = True
        self.service.save()
        self.assertEqual(rostering.swaps_open_to(self.taker, first_church()), [])
        self.assertIn(
            "cancelled", self.refused(rostering.take_swap, self.swap, self.taker)
        )


class TakingTests(SwapTestCase):
    def setUp(self):
        super().setUp()
        self.swap = rostering.request_swap(self.assignment, self.asker)

    def test_the_taker_gets_the_assignment_accepted_and_the_original_ends(self):
        taken = rostering.take_swap(self.swap, self.taker)
        self.assertEqual(taken.person, self.taker)
        self.assertEqual(taken.reply, Reply.ACCEPTED)
        self.assertEqual(taken.part, self.bass)
        self.assertFalse(Assignment.objects.filter(pk=self.assignment.pk).exists())
        self.assertEqual(
            list(self.service.assignments.values_list("person", flat=True)),
            [self.taker.pk],
        )
        self.swap.refresh_from_db()
        self.assertEqual(self.swap.status, SwapRequest.Status.TAKEN)
        self.assertEqual(self.swap.taken_by, self.taker)
        self.assertIsNone(self.swap.assignment)

    def test_the_audit_trail_records_who_handed_over_and_who_took_it(self):
        rostering.take_swap(self.swap, self.taker)
        swap_event = AuditEvent.objects.filter(
            content_type__model="swaprequest", action=AuditEvent.Action.CHANGED
        ).get()
        self.assertIn("from Ann Ask", swap_event.object_repr)
        self.assertEqual(swap_event.changes["Taken by"], ["", "Tom Take"])
        self.assertEqual(swap_event.changes["Status"], ["Open", "Taken"])
        created = AuditEvent.objects.filter(
            content_type__model="swaprequest", action=AuditEvent.Action.CREATED
        ).get()
        self.assertEqual(created.changes["Handed over by"], ["", "Ann Ask"])
        ended = AuditEvent.objects.get(
            content_type__model="assignment", action=AuditEvent.Action.DELETED
        )
        self.assertEqual(ended.changes["Person"], ["Ann Ask", ""])
        self.assertEqual(ended.actor, self.taker)

    def test_the_second_person_is_refused_once_it_is_taken(self):
        second = make_user(roles=["team_member"])
        make_team_profile(second, [self.bass])
        stale = SwapRequest.objects.get(pk=self.swap.pk)  # read before the take
        rostering.take_swap(self.swap, self.taker)
        self.assertEqual(
            self.refused(rostering.take_swap, stale, second),
            "Someone else took this swap first.",
        )
        self.assertEqual(self.service.assignments.count(), 1)

    def test_a_withdrawn_request_cant_be_taken(self):
        rostering.withdraw_swap(self.swap, self.asker)
        self.assertIn(
            "withdrawn", self.refused(rostering.take_swap, self.swap, self.taker)
        )
        self.assertTrue(Assignment.objects.filter(pk=self.assignment.pk).exists())


class SimultaneousTakeTests(TransactionTestCase):
    """Two people press Take at once: the row lock lets only the first in."""

    serialized_rollback = True

    def test_only_the_first_of_two_gets_it(self):
        complete_setup()
        leader = make_user(roles=["worship_leader"])
        bass = make_team_part("Bass guitar")
        asker, first, second = (make_user(roles=["team_member"]) for _ in range(3))
        for person in (asker, first, second):
            make_team_profile(person, [bass])
        service = make_service()
        assignment = rostering.assign(service, bass, asker, leader)
        swap = rostering.request_swap(assignment, asker)

        first_inside = threading.Event()
        let_first_finish = threading.Event()
        real_lock = rostering._lock
        results = {}

        def slow_lock(person):
            real_lock(person)
            if person.pk == first.pk:
                first_inside.set()
                let_first_finish.wait(10)

        def take(name, person):
            try:
                rostering.take_swap(swap, person)
                results[name] = "took"
            except rostering.RosterRefused as refused:
                results[name] = str(refused)
            finally:
                connection.close()

        with mock.patch.object(rostering, "_lock", slow_lock):
            one = threading.Thread(target=take, args=("first", first))
            one.start()
            self.assertTrue(first_inside.wait(10))
            two = threading.Thread(target=take, args=("second", second))
            two.start()
            two.join(0.5)
            self.assertTrue(two.is_alive(), "The second take didn't wait for the lock.")
            let_first_finish.set()
            one.join(10)
            two.join(10)

        self.assertEqual(
            results, {"first": "took", "second": "Someone else took this swap first."}
        )
        self.assertEqual(
            list(Assignment.objects.values_list("person", "reply")),
            [(first.pk, Reply.ACCEPTED)],
        )


class SwapPageTests(SwapTestCase):
    def test_asking_from_my_schedule_then_withdrawing(self):
        self.client.force_login(self.asker)
        url = rostering.swap_url(self.assignment)
        self.assertContains(self.client.get(MY_SCHEDULE), f'href="{url}"')
        self.assertContains(self.client.get(url), "the first to take it gets it")
        self.assertRedirects(self.client.post(url), MY_SCHEDULE)
        swap = SwapRequest.objects.get()
        page = self.client.get(MY_SCHEDULE)
        self.assertContains(page, "Swap requested")
        self.assertContains(page, "Withdraw swap")
        self.client.post(action_url(swap, "withdraw"))
        swap.refresh_from_db()
        self.assertEqual(swap.status, SwapRequest.Status.WITHDRAWN)

    def test_an_eligible_person_takes_it_from_my_schedule(self):
        swap = rostering.request_swap(self.assignment, self.asker)
        self.client.force_login(self.taker)
        page = self.client.get(MY_SCHEDULE)
        self.assertContains(page, "Take it")
        self.assertContains(page, "from Ann Ask")
        response = self.client.post(action_url(swap, "take"), follow=True)
        self.assertContains(response, "You took Bass guitar")
        self.assertEqual(Assignment.objects.get().person, self.taker)

    def test_someone_elses_assignment_or_an_unknown_action_is_a_404(self):
        swap = rostering.request_swap(self.assignment, self.asker)
        self.client.force_login(self.taker)
        url = rostering.swap_url(self.assignment)
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(self.client.post(action_url(swap, "approve")).status_code, 404)

    def test_people_not_on_the_team_are_refused(self):
        swap = rostering.request_swap(self.assignment, self.asker)
        office = make_user(roles=["office_staff"])
        self.client.force_login(office)
        self.assertEqual(self.client.post(action_url(swap, "take")).status_code, 403)
        self.assertEqual(
            self.client.get(rostering.swap_url(self.assignment)).status_code, 403
        )

    def test_the_service_page_shows_a_swap_is_requested(self):
        rostering.request_swap(self.assignment, self.asker)
        self.client.force_login(self.leader)
        page = self.client.get(
            reverse("worship:service", kwargs={"public_id": self.service.public_id})
        )
        self.assertContains(page, "Swap requested")

    def test_the_blackout_refusal_links_to_asking_for_a_swap(self):
        day = rostering.service_day(self.service).isoformat()
        self.client.force_login(self.asker)
        response = self.client.post(
            reverse("teams:blackout_create"),
            {"starts_on": day, "ends_on": day, "note": ""},
        )
        self.assertContains(response, "ask for a swap first")
        self.assertContains(response, f'href="{rostering.swap_url(self.assignment)}"')
        rostering.request_swap(self.assignment, self.asker)
        response = self.client.post(
            reverse("teams:blackout_create"),
            {"starts_on": day, "ends_on": day, "note": ""},
        )
        self.assertContains(response, "Your swap request is open on My schedule")

    def test_a_pending_conflict_links_to_my_schedule_to_decline(self):
        later = make_service(starts_at=timezone.now() + datetime.timedelta(days=21))
        make_assignment(later, self.asker, self.bass)
        day = rostering.service_day(later).isoformat()
        self.client.force_login(self.asker)
        response = self.client.post(
            reverse("teams:blackout_create"),
            {"starts_on": day, "ends_on": day, "note": ""},
        )
        self.assertContains(response, "Decline it on My schedule")
