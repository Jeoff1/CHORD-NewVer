"""A new worship service's date and time start filled in (the owner,
28 Nov 2026): the template's next usual day and time, still editable."""

import datetime
import zoneinfo

from django.test import TestCase
from django.urls import reverse

from apps.core.testing import complete_setup, first_church, make_user
from apps.worship.models import ServiceTemplate
from apps.worship.scheduling import suggested_start

MANILA = zoneinfo.ZoneInfo("Asia/Manila")
SCHEDULER = ["worship.view_worshipservice", "worship.add_worshipservice"]
# A Wednesday, 10:00 in Manila.
WEDNESDAY_10AM = datetime.datetime(2026, 12, 2, 10, 0, tzinfo=MANILA)


def at(day, hour, minute=0):
    return datetime.datetime(2026, 12, day, hour, minute, tzinfo=MANILA)


class SuggestedStartTests(TestCase):
    def setUp(self):
        self.church = complete_setup()
        self.church.time_zone = "Asia/Manila"
        self.church.save()
        self.template = ServiceTemplate.objects.get()

    def suggest(self, weekday, start_time, now=WEDNESDAY_10AM):
        self.template.weekday = weekday
        self.template.start_time = start_time
        return suggested_start(self.church, self.template, now=now)

    def test_the_next_usual_day_at_the_usual_time(self):
        sunday = ServiceTemplate.Weekday.SUNDAY
        self.assertEqual(self.suggest(sunday, datetime.time(9)), at(6, 9))

    def test_today_while_the_time_is_still_ahead_else_next_week(self):
        wednesday = ServiceTemplate.Weekday.WEDNESDAY
        self.assertEqual(self.suggest(wednesday, datetime.time(19)), at(2, 19))
        self.assertEqual(self.suggest(wednesday, datetime.time(8)), at(9, 8))

    def test_a_usual_time_without_a_day_is_today_or_tomorrow(self):
        self.assertEqual(self.suggest(None, datetime.time(18)), at(2, 18))
        self.assertEqual(self.suggest(None, datetime.time(7)), at(3, 7))

    def test_without_a_usual_time_the_next_whole_hour(self):
        now = at(2, 10, 25)
        self.assertEqual(self.suggest(None, None, now=now), at(2, 11))
        self.assertEqual(suggested_start(self.church, None, now=now), at(2, 11))


class ServiceFormDateTests(TestCase):
    def setUp(self):
        complete_setup()
        church = first_church()
        church.time_zone = "Asia/Manila"
        church.save()
        self.template = ServiceTemplate.objects.get()
        self.template.weekday = ServiceTemplate.Weekday.SUNDAY
        self.template.start_time = datetime.time(9, 30)
        self.template.save()
        self.client.force_login(make_user(perms=SCHEDULER))
        self.url = reverse("worship:service_create")

    def test_the_new_service_form_is_filled_in(self):
        page = self.client.get(self.url)
        expected = suggested_start(first_church(), self.template)
        local = expected.astimezone(MANILA).strftime("%Y-%m-%dT%H:%M")
        self.assertEqual(expected.astimezone(MANILA).weekday(), 6)
        day, time = local.split("T")
        # A date box and a time box (the owner, 28 Nov 2026).
        self.assertContains(page, f'type="date" name="starts_at_0" value="{day}"')
        self.assertContains(page, f'type="time" name="starts_at_1" value="{time}"')
        # Each template option carries its own next start, for the script.
        self.assertContains(page, f'data-next-start="{local}"')
        self.assertContains(page, "worship/service_form.js")

    def test_another_template_without_a_usual_time_still_gets_a_date(self):
        other = ServiceTemplate.objects.create(
            church=first_church(), name="Prayer night"
        )
        page = self.client.get(self.url)
        self.assertContains(page, "data-next-start=", count=2)
        self.assertContains(page, f'value="{other.pk}" data-next-start="')

    def test_editing_a_service_keeps_its_own_date(self):
        from apps.core.testing import make_service

        service = make_service(template=self.template)
        self.client.force_login(
            make_user(perms=SCHEDULER + ["worship.change_worshipservice"])
        )
        page = self.client.get(
            reverse("worship:service_update", kwargs={"public_id": service.public_id})
        )
        local = service.starts_at.astimezone(MANILA)
        self.assertContains(page, f'name="starts_at_0" value="{local:%Y-%m-%d}"')
        self.assertContains(page, f'name="starts_at_1" value="{local:%H:%M}"')
