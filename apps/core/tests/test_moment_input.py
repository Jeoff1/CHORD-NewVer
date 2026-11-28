"""Date and time boxes side by side (the owner, 28 Nov 2026): every
date-and-time field is a date box and a time box, each with its icon."""

import datetime
import zoneinfo

from django.test import TestCase
from django.urls import reverse

from apps.core.testing import complete_setup, first_church, make_user
from apps.core.widgets import MomentInput
from apps.worship.models import ServiceTemplate, WorshipService

MANILA = zoneinfo.ZoneInfo("Asia/Manila")


class MomentInputTests(TestCase):
    def test_it_joins_the_two_boxes(self):
        widget = MomentInput()
        data = {"when_0": "2031-03-02", "when_1": "09:30"}
        self.assertEqual(
            widget.value_from_datadict(data, {}, "when"), "2031-03-02 09:30"
        )
        self.assertEqual(widget.value_from_datadict({}, {}, "when"), "")
        self.assertTrue(widget.value_omitted_from_data({}, {}, "when"))
        self.assertFalse(widget.value_omitted_from_data(data, {}, "when"))

    def test_one_combined_value_still_works(self):
        widget = MomentInput()
        data = {"when": "2031-03-02T09:30"}
        self.assertEqual(
            widget.value_from_datadict(data, {}, "when"), "2031-03-02T09:30"
        )
        self.assertFalse(widget.value_omitted_from_data(data, {}, "when"))

    def test_it_splits_a_value_for_the_boxes(self):
        widget = MomentInput()
        self.assertEqual(widget.decompress("2031-03-02 09:30"), ["2031-03-02", "09:30"])
        self.assertEqual(widget.decompress("2031-03-02T09:30"), ["2031-03-02", "09:30"])
        self.assertEqual(widget.decompress(""), [None, None])
        moment = datetime.datetime(2031, 3, 2, 9, 30, tzinfo=datetime.UTC)
        self.assertEqual(len(widget.decompress(moment)), 2)

    def test_it_draws_two_labelled_boxes_with_icons(self):
        html = MomentInput().render("when", "2031-03-02 09:30", {"id": "id_when"})
        self.assertIn('type="date" name="when_0" value="2031-03-02"', html)
        self.assertIn('type="time" name="when_1" value="09:30"', html)
        self.assertIn(
            '<label class="visually-hidden" for="id_when_0">Date</label>', html
        )
        self.assertIn(
            '<label class="visually-hidden" for="id_when_1">Time</label>', html
        )
        self.assertEqual(html.count('class="chord-moment__icon"'), 2)
        self.assertIn("core/moment_input.js", html)


class MomentFieldTests(TestCase):
    def test_a_date_alone_is_refused_not_read_as_midnight(self):
        from django.core.exceptions import ValidationError

        from apps.core.widgets import MomentField

        field = MomentField(required=False)
        with self.assertRaisesMessage(ValidationError, "Enter both a date and a time."):
            field.clean("2031-03-02")
        self.assertIsNotNone(field.clean("2031-03-02 09:30"))
        self.assertIsNotNone(field.clean("2031-03-02T09:30"))
        self.assertIsNone(field.clean(""))


class ServiceFormTests(TestCase):
    def setUp(self):
        complete_setup()
        church = first_church()
        church.time_zone = "Asia/Manila"
        church.save()
        self.client.force_login(
            make_user(
                perms=["worship.view_worshipservice", "worship.add_worshipservice"]
            )
        )
        self.url = reverse("worship:service_create")
        self.template = ServiceTemplate.objects.get()

    def post(self, **fields):
        data = {"template": self.template.pk, "name": "", "notes": ""}
        data.update(fields)
        return self.client.post(self.url, data)

    def test_the_two_boxes_make_the_services_start(self):
        self.post(starts_at_0="2031-03-02", starts_at_1="09:30")
        service = WorshipService.objects.get()
        self.assertEqual(
            service.starts_at.astimezone(MANILA),
            datetime.datetime(2031, 3, 2, 9, 30, tzinfo=MANILA),
        )

    def test_a_date_without_a_time_asks_for_both_and_keeps_the_date(self):
        page = self.post(starts_at_0="2031-03-02", starts_at_1="")
        self.assertFalse(WorshipService.objects.exists())
        self.assertContains(page, "Enter both a date and a time.")
        self.assertContains(page, 'name="starts_at_0" value="2031-03-02"')

    def test_the_label_names_both_boxes(self):
        page = self.client.get(self.url)
        self.assertContains(
            page, '<legend class="form-label fs-6">Date and time</legend>'
        )
        self.assertContains(page, '<legend class="form-label fs-6">Rehearsal</legend>')
