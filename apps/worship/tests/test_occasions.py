"""Occasions and Occasion Requests (Phase 9A, A5; decision 0012)."""

import datetime

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts import roles
from apps.audit.models import AuditEvent
from apps.core.testing import (
    complete_setup,
    make_occasion_template,
    make_service,
    make_user,
)
from apps.notifications.models import Notification
from apps.worship import occasions
from apps.worship.forms import MOMENT_FORMAT
from apps.worship.models import OccasionRequest, ServiceTemplate, WorshipService
from apps.worship.scheduling import church_time_zone

Status = OccasionRequest.Status


def soon(days=14, hour=10, minute=0):
    """An aware moment ``days`` from now at a round time."""
    return (timezone.now() + datetime.timedelta(days=days)).replace(
        hour=hour, minute=minute, second=0, microsecond=0
    )


def form_moment(value):
    return timezone.localtime(value, church_time_zone()).strftime(MOMENT_FORMAT)


class OccasionTestCase(TestCase):
    def setUp(self):
        complete_setup()
        self.wedding = make_occasion_template(name="Garden wedding", length_minutes=120)
        self.member = make_user(
            roles=["church_member"], first_name="Rosa", last_name="Lim"
        )
        self.pastor = make_user(
            roles=["pastoral_staff"], first_name="Pat", last_name="Pastor"
        )
        self.team = make_user(roles=["team_member"])

    def ask(self, starts_at=None, person=None, template=None, who="Ana and Ben"):
        return occasions.request_occasion(
            person or self.member,
            template or self.wedding,
            starts_at or soon(),
            who,
            "Small and simple, please.",
        )


class SeededExampleTests(TestCase):
    def test_wedding_and_funeral_are_seeded_switched_off(self):
        for name in ("Wedding", "Funeral"):
            template = ServiceTemplate.objects.get(name=name)
            self.assertTrue(template.is_occasion)
            self.assertFalse(template.is_active)
            self.assertTrue(template.slots.exists())

    def test_switched_off_examples_cant_be_requested(self):
        complete_setup()
        self.assertFalse(occasions.occasion_templates().exists())
        self.client.force_login(make_user(roles=["church_member"]))
        response = self.client.get(reverse("worship:occasion_request"))
        self.assertRedirects(response, reverse("worship:my_occasions"))


class DefaultPermissionTests(TestCase):
    def test_who_requests_and_who_approves(self):
        defaults = roles.DEFAULT_ROLE_PERMISSIONS
        for key in ("church_member", "pastoral_staff", "worship_leader"):
            self.assertIn(occasions.REQUEST, defaults[key], key)
        self.assertIn(occasions.APPROVE, defaults["pastoral_staff"])
        for key in ("church_member", "worship_leader", "team_member", "office_staff"):
            self.assertNotIn(occasions.APPROVE, defaults[key], key)


class RequestRuleTests(OccasionTestCase):
    def test_a_request_is_pending_and_audited(self):
        occasion = self.ask()
        self.assertEqual(occasion.status, Status.PENDING)
        self.assertIsNone(occasion.service)
        event = AuditEvent.objects.get(object_id=str(occasion.pk))
        self.assertEqual(event.action, AuditEvent.Action.CREATED)
        self.assertEqual(event.changes["For"], ["", "Ana and Ben"])

    def test_only_an_active_occasion_template_can_be_requested(self):
        regular = ServiceTemplate.objects.get(name="Worship Service")
        with self.assertRaises(occasions.OccasionRefused):
            self.ask(template=regular)
        self.wedding.is_active = False
        self.wedding.save()
        with self.assertRaises(occasions.OccasionRefused):
            self.ask()

    def test_a_past_time_is_refused(self):
        with self.assertRaises(occasions.OccasionRefused):
            self.ask(starts_at=timezone.now() - datetime.timedelta(hours=1))

    def test_an_overlapping_request_is_refused(self):
        make_service(starts_at=soon(hour=9))  # 90 minutes: until 10:30
        with self.assertRaises(occasions.OccasionRefused):
            self.ask(starts_at=soon(hour=10))
        # The wedding's own length counts too: 8:00 to 10:00 reaches 9:00.
        with self.assertRaises(occasions.OccasionRefused):
            self.ask(starts_at=soon(hour=8))

    def test_back_to_back_times_dont_clash(self):
        make_service(starts_at=soon(hour=9))  # until 10:30
        self.assertTrue(self.ask(starts_at=soon(hour=10, minute=30)).is_pending)
        self.assertTrue(self.ask(starts_at=soon(hour=7)).is_pending)  # until 9:00

    def test_a_cancelled_service_frees_its_time(self):
        make_service(starts_at=soon(hour=10), is_cancelled=True)
        self.assertTrue(self.ask(starts_at=soon(hour=10)).is_pending)

    def test_the_clash_is_named_only_for_people_who_may_see_it(self):
        booked = make_service(
            template=self.wedding, name="Secret wedding", starts_at=soon(hour=10)
        )
        found = occasions.clashes(soon(hour=11), soon(hour=12))
        self.assertEqual(found, [booked])
        self.assertNotIn("Secret", occasions.clash_message(found, self.member))
        self.assertIn("Secret wedding", occasions.clash_message(found, self.pastor))


class DecisionRuleTests(OccasionTestCase):
    def test_approving_creates_the_service_and_tells_the_requester(self):
        occasion = self.ask()
        service = occasions.approve(
            occasion, self.pastor, officiant=self.pastor, venue="The garden"
        )
        occasion.refresh_from_db()
        self.assertEqual(occasion.status, Status.APPROVED)
        self.assertEqual(occasion.service, service)
        self.assertEqual(occasion.decided_by, self.pastor)
        self.assertEqual(service.template, self.wedding)
        self.assertEqual(service.starts_at, soon())
        self.assertEqual(service.name, "Garden wedding: Ana and Ben")
        self.assertEqual(service.occasion_for, "Ana and Ben")
        self.assertEqual(service.officiant, self.pastor)
        self.assertEqual(service.venue, "The garden")
        self.assertTrue(service.is_occasion)
        self.assertEqual(service.ends_at, soon(hour=12))
        note = Notification.objects.get(recipient=self.member)
        self.assertIn("was approved by Pat Pastor", note.text)
        self.assertEqual(note.url, reverse("worship:my_occasions"))

    def test_the_approver_may_move_the_time(self):
        service = occasions.approve(self.ask(), self.pastor, starts_at=soon(hour=15))
        self.assertEqual(service.starts_at, soon(hour=15))

    def test_an_approval_that_overlaps_is_refused_and_changes_nothing(self):
        occasion = self.ask(starts_at=soon(hour=10))
        make_service(starts_at=soon(hour=11))  # booked after the request
        with self.assertRaises(occasions.OccasionRefused):
            occasions.approve(occasion, self.pastor)
        occasion.refresh_from_db()
        self.assertTrue(occasion.is_pending)
        self.assertFalse(WorshipService.objects.filter(template=self.wedding).exists())
        self.assertFalse(Notification.objects.exists())

    def test_two_requests_for_one_time_only_the_first_approval_holds(self):
        first, second = self.ask(), self.ask(who="Cy and Di")
        occasions.approve(first, self.pastor)
        with self.assertRaises(occasions.OccasionRefused):
            occasions.approve(second, self.pastor)

    def test_declining_needs_a_reason_and_tells_the_requester(self):
        occasion = self.ask()
        with self.assertRaises(occasions.OccasionRefused):
            occasions.decline(occasion, self.pastor, "  ")
        occasions.decline(occasion, self.pastor, "The church is closed that day.")
        occasion.refresh_from_db()
        self.assertEqual(occasion.status, Status.DECLINED)
        note = Notification.objects.get(recipient=self.member)
        self.assertIn("declined: The church is closed that day.", note.text)

    def test_a_decided_request_cant_be_decided_again(self):
        occasion = self.ask()
        occasions.decline(occasion, self.pastor, "No.")
        with self.assertRaises(occasions.OccasionRefused):
            occasions.approve(occasion, self.pastor)
        with self.assertRaises(occasions.OccasionRefused):
            occasions.withdraw(occasion, self.member)

    def test_only_the_requester_withdraws_and_only_while_pending(self):
        occasion = self.ask()
        with self.assertRaises(occasions.OccasionRefused):
            occasions.withdraw(occasion, self.pastor)
        occasions.withdraw(occasion, self.member)
        occasion.refresh_from_db()
        self.assertEqual(occasion.status, Status.WITHDRAWN)
        with self.assertRaises(occasions.OccasionRefused):
            occasions.approve(occasion, self.pastor)

    def test_the_requester_is_told_even_with_teams_switched_off(self):
        complete_setup(disabled_modules=["teams"])
        occasions.approve(self.ask(), self.pastor)
        self.assertTrue(Notification.objects.filter(recipient=self.member).exists())

    def test_pending_count(self):
        self.ask()
        occasions.decline(self.ask(who="Cy and Di"), self.pastor, "No.")
        self.assertEqual(occasions.pending_count(), 1)


class RequesterPageTests(OccasionTestCase):
    def test_a_church_member_requests_and_sees_their_own(self):
        self.client.force_login(self.member)
        self.assertEqual(
            self.client.get(reverse("worship:occasion_request")).status_code, 200
        )
        response = self.client.post(
            reverse("worship:occasion_request"),
            {
                "template": self.wedding.pk,
                "starts_at": form_moment(soon()),
                "occasion_for": "Ana and Ben",
                "note": "",
            },
        )
        self.assertRedirects(response, reverse("worship:my_occasions"))
        self.ask(person=self.pastor, who="Someone else", starts_at=soon(days=20))
        page = self.client.get(reverse("worship:my_occasions"))
        self.assertContains(page, "Garden wedding for Ana and Ben")
        self.assertContains(page, "Pending")
        self.assertNotContains(page, "Someone else")

    def test_a_clashing_request_shows_the_refusal_on_the_form(self):
        make_service(starts_at=soon(hour=10))
        self.client.force_login(self.member)
        response = self.client.post(
            reverse("worship:occasion_request"),
            {
                "template": self.wedding.pk,
                "starts_at": form_moment(soon(hour=10)),
                "occasion_for": "Ana and Ben",
            },
        )
        # A regular service is no secret, so the refusal names it.
        self.assertContains(response, "overlaps Worship Service")
        self.assertFalse(OccasionRequest.objects.exists())

    def test_withdrawing_from_the_page(self):
        occasion = self.ask()
        self.client.force_login(self.member)
        response = self.client.post(
            reverse(
                "worship:occasion_withdraw", kwargs={"public_id": occasion.public_id}
            )
        )
        self.assertRedirects(response, reverse("worship:my_occasions"))
        occasion.refresh_from_db()
        self.assertEqual(occasion.status, Status.WITHDRAWN)

    def test_someone_elses_request_cant_be_withdrawn(self):
        occasion = self.ask()
        other = make_user(roles=["church_member"])
        self.client.force_login(other)
        response = self.client.post(
            reverse(
                "worship:occasion_withdraw", kwargs={"public_id": occasion.public_id}
            )
        )
        self.assertEqual(response.status_code, 404)

    def test_without_the_permission_the_pages_are_refused(self):
        self.client.force_login(self.team)
        for name in ("worship:occasion_request", "worship:my_occasions"):
            with self.subTest(name):
                self.assertEqual(self.client.get(reverse(name)).status_code, 403)


class ApproverPageTests(OccasionTestCase):
    def decide_url(self, occasion):
        return reverse(
            "worship:occasion_decide", kwargs={"public_id": occasion.public_id}
        )

    def test_the_list_shows_pending_requests_and_the_count(self):
        self.ask()
        self.client.force_login(self.pastor)
        page = self.client.get(reverse("worship:occasion_requests"))
        self.assertContains(page, "Garden wedding for Ana and Ben")
        self.assertContains(page, 'aria-label="1 pending"')

    def test_approving_from_the_page_goes_to_the_new_service(self):
        occasion = self.ask()
        self.client.force_login(self.pastor)
        self.assertContains(self.client.get(self.decide_url(occasion)), "Approve")
        response = self.client.post(
            self.decide_url(occasion),
            {
                "action": "approve",
                "starts_at": form_moment(occasion.starts_at),
                "name": "",
                "officiant": self.pastor.pk,
                "venue": "",
            },
        )
        occasion.refresh_from_db()
        self.assertRedirects(
            response,
            reverse(
                "worship:service", kwargs={"public_id": occasion.service.public_id}
            ),
        )
        page = self.client.get(response["Location"])
        self.assertContains(page, "Ana and Ben")
        self.assertContains(page, "Small and simple, please.")

    def test_a_clashing_approval_shows_the_refusal(self):
        occasion = self.ask(starts_at=soon(hour=10))
        make_service(name="Morning prayer", starts_at=soon(hour=11))
        self.client.force_login(self.pastor)
        self.assertContains(
            self.client.get(self.decide_url(occasion)), "Morning prayer"
        )
        response = self.client.post(
            self.decide_url(occasion),
            {"action": "approve", "starts_at": form_moment(occasion.starts_at)},
        )
        self.assertContains(response, "overlaps Morning prayer")
        occasion.refresh_from_db()
        self.assertTrue(occasion.is_pending)

    def test_declining_without_a_reason_is_refused(self):
        occasion = self.ask()
        self.client.force_login(self.pastor)
        response = self.client.post(
            self.decide_url(occasion), {"action": "decline", "reason": ""}
        )
        self.assertEqual(response.status_code, 200)
        occasion.refresh_from_db()
        self.assertTrue(occasion.is_pending)
        response = self.client.post(
            self.decide_url(occasion), {"action": "decline", "reason": "Full that day."}
        )
        self.assertRedirects(response, reverse("worship:occasion_requests"))

    def test_only_approvers_open_the_requests(self):
        occasion = self.ask()
        leader = make_user(roles=["worship_leader"])
        for person in (self.member, leader, self.team):
            self.client.force_login(person)
            with self.subTest(person=person.username):
                self.assertEqual(
                    self.client.get(reverse("worship:occasion_requests")).status_code,
                    403,
                )
                response = self.client.post(
                    self.decide_url(occasion),
                    {"action": "decline", "reason": "No."},
                )
                self.assertEqual(response.status_code, 403)
        occasion.refresh_from_db()
        self.assertTrue(occasion.is_pending)

    def test_switched_off_worship_hides_the_pages(self):
        occasion = self.ask()
        complete_setup(disabled_modules=["worship"])
        self.client.force_login(self.pastor)
        for url in (
            reverse("worship:occasion_requests"),
            reverse("worship:my_occasions"),
            self.decide_url(occasion),
        ):
            with self.subTest(url):
                self.assertEqual(self.client.get(url).status_code, 404)


class BookedVisibilityTests(OccasionTestCase):
    def setUp(self):
        super().setUp()
        self.occasion = make_service(
            template=self.wedding,
            name="Wedding of Ana and Ben",
            occasion_for="Ana and Ben",
            starts_at=soon(hour=14),
        )
        self.regular = make_service(name="Sunday gathering", starts_at=soon(hour=9))
        local = timezone.localtime(self.occasion.starts_at, church_time_zone())
        self.calendar = reverse("worship:calendar") + f"?month={local:%Y-%m}"
        self.page = reverse(
            "worship:service", kwargs={"public_id": self.occasion.public_id}
        )

    def test_a_church_member_sees_only_booked(self):
        self.client.force_login(self.member)
        calendar = self.client.get(self.calendar)
        self.assertContains(calendar, "Booked")
        self.assertNotContains(calendar, "Ana and Ben")
        self.assertContains(calendar, "Sunday gathering")
        schedule = self.client.get(reverse("worship:home"))
        self.assertNotContains(schedule, "Ana and Ben")
        self.assertContains(schedule, "Sunday gathering")
        self.assertEqual(self.client.get(self.page).status_code, 404)

    def test_searching_the_schedule_doesnt_reveal_it(self):
        self.client.force_login(self.member)
        page = self.client.get(reverse("worship:home") + "?q=Ana")
        self.assertNotContains(page, "Wedding of")

    def test_a_cancelled_occasion_isnt_booked(self):
        self.occasion.is_cancelled = True
        self.occasion.save()
        self.client.force_login(self.member)
        self.assertNotContains(self.client.get(self.calendar), "Booked")

    def test_people_who_plan_or_play_see_the_details(self):
        office = make_user(roles=["office_staff"])
        for person in (self.pastor, self.team, office):
            self.client.force_login(person)
            with self.subTest(person=person.username):
                self.assertContains(
                    self.client.get(self.calendar), "Wedding of Ana and Ben"
                )
                self.assertContains(
                    self.client.get(reverse("worship:home")), "Wedding of Ana and Ben"
                )
                self.assertContains(self.client.get(self.page), "Ana and Ben")

    def test_the_service_page_shows_the_booked_time(self):
        self.client.force_login(self.pastor)
        self.assertContains(self.client.get(self.page), "Booked")


class TemplateSettingsTests(TestCase):
    def test_a_template_can_be_marked_as_an_occasion_with_a_length(self):
        complete_setup()
        self.client.force_login(make_user(roles=["pastoral_staff"]))
        response = self.client.post(
            reverse("worship:template_create"),
            {
                "name": "Child dedication",
                "description": "",
                "weekday": "",
                "start_time": "",
                "length_minutes": "60",
                "is_occasion": "on",
                "sort_order": "50",
                "is_active": "on",
                "slots-TOTAL_FORMS": "0",
                "slots-INITIAL_FORMS": "0",
                "slots-MIN_NUM_FORMS": "0",
                "slots-MAX_NUM_FORMS": "1000",
            },
        )
        self.assertRedirects(response, reverse("worship:template_list"))
        template = ServiceTemplate.objects.get(name="Child dedication")
        self.assertTrue(template.is_occasion)
        self.assertEqual(template.length_minutes, 60)
        self.assertIn(template, occasions.occasion_templates())

    def test_a_template_saved_without_a_length_keeps_ninety_minutes(self):
        complete_setup()
        self.client.force_login(make_user(roles=["pastoral_staff"]))
        self.client.post(
            reverse("worship:template_create"),
            {
                "name": "Youth night",
                "length_minutes": "",
                "sort_order": "60",
                "is_active": "on",
                "slots-TOTAL_FORMS": "0",
                "slots-INITIAL_FORMS": "0",
                "slots-MIN_NUM_FORMS": "0",
                "slots-MAX_NUM_FORMS": "1000",
            },
        )
        template = ServiceTemplate.objects.get(name="Youth night")
        self.assertEqual(template.length_minutes, 90)
        self.assertFalse(template.is_occasion)
