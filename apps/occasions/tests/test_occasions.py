"""The Occasions Module (Phase 9A, A5; decision 0013)."""

import datetime

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts import roles
from apps.audit.models import AuditEvent
from apps.church.modules import MODULES_BY_CODE
from apps.core.testing import (
    complete_setup,
    first_church,
    make_occasion,
    make_occasion_type,
    make_service,
    make_user,
)
from apps.notifications.models import Notification
from apps.occasions import rules
from apps.occasions.models import Occasion, OccasionRequest, OccasionType
from apps.worship.forms import MOMENT_FORMAT
from apps.worship.scheduling import church_time_zone

Status = OccasionRequest.Status


def soon(days=14, hour=10, minute=0):
    """An aware moment ``days`` from now at a round time."""
    return (timezone.now() + datetime.timedelta(days=days)).replace(
        hour=hour, minute=minute, second=0, microsecond=0
    )


def form_moment(value):
    return timezone.localtime(value, church_time_zone(first_church())).strftime(
        MOMENT_FORMAT
    )


class OccasionTestCase(TestCase):
    def setUp(self):
        complete_setup()
        self.wedding = make_occasion_type(name="Garden wedding", length_minutes=120)
        self.member = make_user(
            roles=["church_member"], first_name="Rosa", last_name="Lim"
        )
        self.pastor = make_user(
            roles=["pastoral_staff"], first_name="Pat", last_name="Pastor"
        )
        self.team = make_user(roles=["team_member"])

    def ask(self, starts_at=None, person=None, occasion_type=None, who="Ana and Ben"):
        return rules.request_occasion(
            person or self.member,
            occasion_type or self.wedding,
            starts_at or soon(),
            who,
            "Small and simple, please.",
        )


class SetupTests(TestCase):
    def test_wedding_baptism_and_funeral_are_seeded_switched_off(self):
        for name in ("Wedding", "Baptism", "Funeral"):
            self.assertFalse(OccasionType.objects.get(name=name).is_active, name)
        self.assertFalse(rules.requestable_types(first_church()).exists())

    def test_default_permissions(self):
        defaults = roles.DEFAULT_ROLE_PERMISSIONS
        pastoral = defaults["pastoral_staff"]
        for codename in ("add_occasion", "change_occasion", "approve_occasion"):
            self.assertIn(f"occasions.{codename}", pastoral)
        for key in ("church_member", "pastoral_staff", "worship_leader"):
            self.assertIn(rules.REQUEST, defaults[key], key)
        for key in ("office_staff", "pastoral_staff", "worship_leader"):
            self.assertIn(rules.VIEW, defaults[key], key)
        for key in ("church_member", "team_member"):
            self.assertNotIn(rules.VIEW, defaults[key], key)
        for key in ("office_staff", "worship_leader", "church_member", "team_member"):
            self.assertNotIn(rules.APPROVE, defaults[key], key)
            self.assertNotIn("occasions.add_occasion", defaults[key], key)

    def test_the_module_opens_for_viewers_and_requesters(self):
        complete_setup()
        module = MODULES_BY_CODE["occasions"]
        self.assertTrue(module.can_open(make_user(roles=["church_member"])))
        self.assertTrue(module.can_open(make_user(roles=["office_staff"])))
        self.assertFalse(module.can_open(make_user(roles=["team_member"])))

    def test_switched_off_examples_cant_be_requested(self):
        complete_setup()
        self.client.force_login(make_user(roles=["church_member"]))
        response = self.client.get(reverse("occasions:request"))
        self.assertRedirects(response, reverse("occasions:my_requests"))


class BookingRuleTests(OccasionTestCase):
    def test_adding_an_occasion_is_audited(self):
        occasion = Occasion(
            church=first_church(),
            occasion_type=self.wedding,
            starts_at=soon(),
            length_minutes=120,
            occasion_for="Ana and Ben",
        )
        rules.save_occasion(occasion, self.pastor)
        event = AuditEvent.objects.get(object_id=str(occasion.pk))
        self.assertEqual(event.action, AuditEvent.Action.CREATED)
        self.assertEqual(occasion.ends_at, soon(hour=12))

    def test_an_occasion_over_a_worship_service_is_refused(self):
        make_service(starts_at=soon(hour=9))  # 90 minutes: until 10:30
        occasion = Occasion(
            church=first_church(),
            occasion_type=self.wedding,
            starts_at=soon(hour=10),
            length_minutes=60,
            occasion_for="X",
        )
        with self.assertRaises(rules.OccasionRefused):
            rules.save_occasion(occasion, self.pastor)
        self.assertFalse(Occasion.objects.exists())

    def test_an_occasion_over_another_occasion_is_refused(self):
        make_occasion(self.wedding, starts_at=soon(hour=10))  # until 12:00
        with self.assertRaises(rules.OccasionRefused):
            self.ask(starts_at=soon(hour=11))
        with self.assertRaises(rules.OccasionRefused):
            self.ask(starts_at=soon(hour=9))  # 9:00 to 11:00

    def test_back_to_back_times_dont_clash(self):
        make_service(starts_at=soon(hour=9))  # until 10:30
        self.assertTrue(self.ask(starts_at=soon(hour=10, minute=30)).is_pending)
        self.assertTrue(self.ask(starts_at=soon(hour=7)).is_pending)  # until 9:00

    def test_a_cancelled_booking_frees_its_time(self):
        make_service(starts_at=soon(hour=10), is_cancelled=True)
        make_occasion(self.wedding, starts_at=soon(hour=14), is_cancelled=True)
        self.assertTrue(self.ask(starts_at=soon(hour=10)).is_pending)
        self.assertTrue(self.ask(starts_at=soon(hour=14)).is_pending)

    def test_moving_an_occasion_doesnt_clash_with_itself(self):
        occasion = make_occasion(self.wedding, starts_at=soon(hour=10))
        occasion.starts_at = soon(hour=11)
        rules.save_occasion(occasion, self.pastor)
        occasion.refresh_from_db()
        self.assertEqual(occasion.starts_at, soon(hour=11))

    def test_the_clash_is_named_only_for_people_who_may_see_it(self):
        make_occasion(self.wedding, starts_at=soon(hour=10), occasion_for="Secret")
        found = rules.clashes(first_church(), soon(hour=11), soon(hour=12))
        self.assertNotIn("Garden wedding", rules.clash_message(found, self.member))
        self.assertIn("Garden wedding", rules.clash_message(found, self.pastor))
        service = make_service(name="Morning prayer", starts_at=soon(days=20))
        found = rules.clashes(first_church(), service.starts_at, service.ends_at)
        self.assertIn("Morning prayer", rules.clash_message(found, self.member))


class RequestRuleTests(OccasionTestCase):
    def test_a_request_is_pending_and_audited(self):
        record = self.ask()
        self.assertEqual(record.status, Status.PENDING)
        event = AuditEvent.objects.get(object_id=str(record.pk))
        self.assertEqual(event.changes["For"], ["", "Ana and Ben"])

    def test_a_switched_off_type_or_a_past_time_is_refused(self):
        with self.assertRaises(rules.OccasionRefused):
            self.ask(starts_at=timezone.now() - datetime.timedelta(hours=1))
        self.wedding.is_active = False
        self.wedding.save()
        with self.assertRaises(rules.OccasionRefused):
            self.ask()

    def test_approving_books_the_occasion_and_tells_the_requester(self):
        record = self.ask()
        occasion = rules.approve(
            record, self.pastor, officiant=self.pastor, venue="The garden"
        )
        record.refresh_from_db()
        self.assertEqual(record.status, Status.APPROVED)
        self.assertEqual(record.occasion, occasion)
        self.assertEqual(record.decided_by, self.pastor)
        self.assertEqual(occasion.occasion_type, self.wedding)
        self.assertEqual(occasion.starts_at, soon())
        self.assertEqual(occasion.length_minutes, 120)
        self.assertEqual(occasion.occasion_for, "Ana and Ben")
        self.assertEqual(occasion.officiant, self.pastor)
        self.assertEqual(occasion.venue, "The garden")
        self.assertEqual(occasion.notes, "Small and simple, please.")
        self.assertFalse(hasattr(occasion, "lineup"))
        note = Notification.objects.get(recipient=self.member)
        self.assertIn("was approved by Pat Pastor", note.text)
        # My requests at every church: the requester may be from elsewhere.
        self.assertEqual(note.url, reverse("public_requests:my_requests"))

    def test_the_approver_may_move_the_time(self):
        occasion = rules.approve(self.ask(), self.pastor, starts_at=soon(hour=15))
        self.assertEqual(occasion.starts_at, soon(hour=15))

    def test_an_approval_that_overlaps_is_refused_and_changes_nothing(self):
        record = self.ask(starts_at=soon(hour=10))
        make_service(starts_at=soon(hour=11))  # booked after the request
        with self.assertRaises(rules.OccasionRefused):
            rules.approve(record, self.pastor)
        record.refresh_from_db()
        self.assertTrue(record.is_pending)
        self.assertFalse(Occasion.objects.exists())
        # Nobody is told of a decision (the approvers heard of the request).
        self.assertFalse(Notification.objects.filter(recipient=self.member).exists())

    def test_two_requests_for_one_time_only_the_first_approval_holds(self):
        first, second = self.ask(), self.ask(who="Cy and Di")
        rules.approve(first, self.pastor)
        with self.assertRaises(rules.OccasionRefused):
            rules.approve(second, self.pastor)

    def test_declining_needs_a_reason_and_tells_the_requester(self):
        record = self.ask()
        with self.assertRaises(rules.OccasionRefused):
            rules.decline(record, self.pastor, "  ")
        rules.decline(record, self.pastor, "The church is closed that day.")
        record.refresh_from_db()
        self.assertEqual(record.status, Status.DECLINED)
        note = Notification.objects.get(recipient=self.member)
        self.assertIn("declined: The church is closed that day.", note.text)

    def test_a_decided_request_cant_be_decided_again(self):
        record = self.ask()
        rules.decline(record, self.pastor, "No.")
        with self.assertRaises(rules.OccasionRefused):
            rules.approve(record, self.pastor)
        with self.assertRaises(rules.OccasionRefused):
            rules.withdraw(record, self.member)

    def test_only_the_requester_withdraws_and_only_while_pending(self):
        record = self.ask()
        with self.assertRaises(rules.OccasionRefused):
            rules.withdraw(record, self.pastor)
        rules.withdraw(record, self.member)
        record.refresh_from_db()
        self.assertEqual(record.status, Status.WITHDRAWN)

    def test_the_requester_is_told_even_with_teams_switched_off(self):
        complete_setup(disabled_modules=["teams"])
        rules.approve(self.ask(), self.pastor)
        self.assertTrue(Notification.objects.filter(recipient=self.member).exists())


class OccasionPageTests(OccasionTestCase):
    def test_the_pastor_adds_an_occasion_directly(self):
        self.client.force_login(self.pastor)
        self.assertEqual(self.client.get(reverse("occasions:create")).status_code, 200)
        response = self.client.post(
            reverse("occasions:create"),
            {
                "occasion_type": self.wedding.pk,
                "starts_at": form_moment(soon()),
                "length_minutes": "",
                "occasion_for": "Ana and Ben",
                "officiant": self.pastor.pk,
                "venue": "The garden",
                "notes": "",
            },
        )
        occasion = Occasion.objects.get()
        self.assertRedirects(
            response,
            reverse("occasions:detail", kwargs={"public_id": occasion.public_id}),
        )
        self.assertEqual(occasion.length_minutes, 120)  # the type's usual length
        page = self.client.get(response["Location"])
        self.assertContains(page, "Garden wedding: Ana and Ben")
        self.assertContains(page, "The garden")

    def test_adding_over_a_booking_shows_the_refusal(self):
        make_service(name="Morning prayer", starts_at=soon(hour=10))
        self.client.force_login(self.pastor)
        response = self.client.post(
            reverse("occasions:create"),
            {
                "occasion_type": self.wedding.pk,
                "starts_at": form_moment(soon(hour=10)),
                "occasion_for": "Ana and Ben",
            },
        )
        self.assertContains(response, "overlaps Morning prayer")
        self.assertFalse(Occasion.objects.exists())

    def test_editing_and_cancelling(self):
        occasion = make_occasion(self.wedding, starts_at=soon(hour=10))
        self.client.force_login(self.pastor)
        url = reverse("occasions:update", kwargs={"public_id": occasion.public_id})
        response = self.client.post(
            url,
            {
                "occasion_type": self.wedding.pk,
                "starts_at": form_moment(soon(hour=10)),
                "length_minutes": "90",
                "occasion_for": "Ana and Ben",
                "is_cancelled": "on",
            },
        )
        self.assertEqual(response.status_code, 302)
        occasion.refresh_from_db()
        self.assertTrue(occasion.is_cancelled)
        self.assertEqual(occasion.length_minutes, 90)

    def test_the_list_shows_upcoming_occasions(self):
        make_occasion(self.wedding, occasion_for="Ana and Ben")
        self.client.force_login(self.pastor)
        page = self.client.get(reverse("occasions:list"))
        self.assertContains(page, "Garden wedding: Ana and Ben")

    def test_the_home_page_sends_each_person_to_their_page(self):
        self.client.force_login(self.pastor)
        self.assertRedirects(
            self.client.get(reverse("occasions:home")), reverse("occasions:list")
        )
        self.client.force_login(self.member)
        self.assertRedirects(
            self.client.get(reverse("occasions:home")),
            reverse("occasions:my_requests"),
        )
        self.client.force_login(self.team)
        self.assertEqual(self.client.get(reverse("occasions:home")).status_code, 403)

    def test_people_without_the_permissions_are_refused(self):
        occasion = make_occasion(self.wedding)
        detail = reverse("occasions:detail", kwargs={"public_id": occasion.public_id})
        office = make_user(roles=["office_staff"])
        self.client.force_login(office)
        self.assertEqual(self.client.get(detail).status_code, 200)
        self.assertEqual(self.client.get(reverse("occasions:create")).status_code, 403)
        for person in (self.member, self.team):
            self.client.force_login(person)
            with self.subTest(person=person.username):
                self.assertEqual(self.client.get(detail).status_code, 403)
                self.assertEqual(
                    self.client.get(reverse("occasions:list")).status_code, 403
                )

    def test_occasion_types_are_a_settings_list(self):
        self.client.force_login(self.pastor)
        page = self.client.get(reverse("occasions:types_list"))
        self.assertContains(page, "Baptism")
        self.assertContains(page, "120 min")

    def test_switched_off_occasions_hide_everything(self):
        occasion = make_occasion(self.wedding)
        complete_setup(disabled_modules=["occasions"])
        self.client.force_login(self.pastor)
        for url in (
            reverse("occasions:home"),
            reverse("occasions:list"),
            reverse("occasions:detail", kwargs={"public_id": occasion.public_id}),
            reverse("occasions:requests"),
        ):
            with self.subTest(url):
                self.assertEqual(self.client.get(url).status_code, 404)
        self.assertNotContains(self.client.get(reverse("home")), "/occasions/")

    def test_switching_worship_off_switches_occasions_off(self):
        complete_setup(disabled_modules=["worship"])
        self.client.force_login(self.pastor)
        self.assertEqual(self.client.get(reverse("occasions:home")).status_code, 404)


class RequestPageTests(OccasionTestCase):
    def decide_url(self, record):
        return reverse("occasions:decide", kwargs={"public_id": record.public_id})

    def test_a_church_member_requests_and_sees_their_own(self):
        self.client.force_login(self.member)
        response = self.client.post(
            reverse("occasions:request"),
            {
                "occasion_type": self.wedding.pk,
                "starts_at": form_moment(soon()),
                "occasion_for": "Ana and Ben",
                "note": "",
            },
        )
        self.assertRedirects(response, reverse("occasions:my_requests"))
        self.ask(person=self.pastor, who="Someone else", starts_at=soon(days=20))
        page = self.client.get(reverse("occasions:my_requests"))
        self.assertContains(page, "Garden wedding for Ana and Ben")
        self.assertNotContains(page, "Someone else")

    def test_a_church_member_is_never_told_whose_booking_clashes(self):
        make_occasion(self.wedding, starts_at=soon(hour=10), occasion_for="Secret")
        self.client.force_login(self.member)
        response = self.client.post(
            reverse("occasions:request"),
            {
                "occasion_type": self.wedding.pk,
                "starts_at": form_moment(soon(hour=11)),
                "occasion_for": "Ana and Ben",
            },
        )
        self.assertContains(response, "already booked")
        self.assertNotContains(response, "Secret")

    def test_withdrawing_only_your_own(self):
        record = self.ask()
        url = reverse("occasions:withdraw", kwargs={"public_id": record.public_id})
        self.client.force_login(make_user(roles=["church_member"]))
        self.assertEqual(self.client.post(url).status_code, 404)
        self.client.force_login(self.member)
        self.assertRedirects(self.client.post(url), reverse("occasions:my_requests"))
        record.refresh_from_db()
        self.assertEqual(record.status, Status.WITHDRAWN)

    def test_approvers_see_the_pending_count_and_approve(self):
        record = self.ask()
        self.client.force_login(self.pastor)
        page = self.client.get(reverse("occasions:requests"))
        self.assertContains(page, "Garden wedding for Ana and Ben")
        self.assertContains(page, 'aria-label="1 pending"')
        response = self.client.post(
            self.decide_url(record),
            {
                "action": "approve",
                "starts_at": form_moment(record.starts_at),
                "officiant": self.pastor.pk,
            },
        )
        record.refresh_from_db()
        self.assertRedirects(
            response,
            reverse(
                "occasions:detail", kwargs={"public_id": record.occasion.public_id}
            ),
        )
        self.assertContains(self.client.get(response["Location"]), "Requested")

    def test_a_clashing_approval_shows_the_refusal(self):
        record = self.ask(starts_at=soon(hour=10))
        make_service(name="Morning prayer", starts_at=soon(hour=11))
        self.client.force_login(self.pastor)
        self.assertContains(self.client.get(self.decide_url(record)), "Morning prayer")
        response = self.client.post(
            self.decide_url(record),
            {"action": "approve", "starts_at": form_moment(record.starts_at)},
        )
        self.assertContains(response, "overlaps Morning prayer")
        record.refresh_from_db()
        self.assertTrue(record.is_pending)

    def test_declining_without_a_reason_is_refused(self):
        record = self.ask()
        self.client.force_login(self.pastor)
        self.client.post(self.decide_url(record), {"action": "decline", "reason": ""})
        record.refresh_from_db()
        self.assertTrue(record.is_pending)
        response = self.client.post(
            self.decide_url(record), {"action": "decline", "reason": "Full that day."}
        )
        self.assertRedirects(response, reverse("occasions:requests"))

    def test_only_approvers_decide(self):
        record = self.ask()
        leader = make_user(roles=["worship_leader"])
        for person in (self.member, leader, self.team):
            self.client.force_login(person)
            with self.subTest(person=person.username):
                self.assertEqual(
                    self.client.get(reverse("occasions:requests")).status_code, 403
                )
                response = self.client.post(
                    self.decide_url(record), {"action": "decline", "reason": "No."}
                )
                self.assertEqual(response.status_code, 403)
        record.refresh_from_db()
        self.assertTrue(record.is_pending)


class CalendarTests(OccasionTestCase):
    def setUp(self):
        super().setUp()
        self.occasion = make_occasion(
            self.wedding, starts_at=soon(hour=14), occasion_for="Ana and Ben"
        )
        make_service(name="Sunday gathering", starts_at=soon(hour=9))
        local = timezone.localtime(
            self.occasion.starts_at, church_time_zone(first_church())
        )
        self.calendar = reverse("worship:calendar") + f"?month={local:%Y-%m}"

    def test_a_church_member_sees_only_booked(self):
        self.client.force_login(self.member)
        page = self.client.get(self.calendar)
        self.assertContains(page, " Booked</span>")
        self.assertNotContains(page, "Ana and Ben")
        self.assertContains(page, "Sunday gathering")

    def test_people_who_see_occasions_get_the_details_and_a_link(self):
        self.client.force_login(self.pastor)
        page = self.client.get(self.calendar)
        self.assertContains(page, "Garden wedding: Ana and Ben")
        self.assertContains(
            page,
            reverse("occasions:detail", kwargs={"public_id": self.occasion.public_id}),
        )

    def test_a_cancelled_occasion_isnt_booked(self):
        self.occasion.is_cancelled = True
        self.occasion.save()
        self.client.force_login(self.member)
        self.assertNotContains(self.client.get(self.calendar), " Booked</span>")

    def test_occasions_never_show_as_worship_services(self):
        self.client.force_login(self.pastor)
        schedule = self.client.get(reverse("worship:home"))
        self.assertNotContains(schedule, "Ana and Ben")
        self.assertContains(schedule, "Sunday gathering")

    def test_switched_off_occasions_leave_the_calendar(self):
        complete_setup(disabled_modules=["occasions"])
        self.client.force_login(self.pastor)
        page = self.client.get(self.calendar)
        self.assertNotContains(page, "Ana and Ben")
        self.assertNotContains(page, " Booked</span>")
