import datetime
import zoneinfo

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.audit.models import AuditEvent
from apps.core.testing import (
    complete_setup,
    make_administrator,
    make_service,
    make_theme,
    make_user,
)
from apps.worship import scheduling
from apps.worship.models import (
    SermonSeries,
    ServiceTemplate,
    TemplateSlot,
    Theme,
    WorshipService,
)

MANILA = zoneinfo.ZoneInfo("Asia/Manila")
VIEWER = ["worship.view_worshipservice"]
SCHEDULER = VIEWER + ["worship.add_worshipservice", "worship.change_worshipservice"]
THEME_EDITOR = VIEWER + ["worship.change_theme"]
HOME = reverse("worship:home")


def service_url(service, name="service"):
    return reverse(f"worship:{name}", kwargs={"public_id": service.public_id})


def default_template():
    return ServiceTemplate.objects.active().get()


def service_data(**overrides):
    data = {
        "template": default_template().pk,
        "name": "",
        "starts_at": "2031-03-02T09:00",
        "rehearsal_at": "",
        "notes": "",
    }
    data.update(overrides)
    return data


class WorshipTestCase(TestCase):
    def setUp(self):
        complete_setup()


class ScheduleListTests(WorshipTestCase):
    def names(self, **params):
        response = self.client.get(HOME, params)
        return [service.name for service in response.context["object_list"]]

    def test_needs_permission(self):
        self.client.force_login(make_user())
        self.assertEqual(self.client.get(HOME).status_code, 403)

    def test_switched_off_module_is_404_and_keeps_its_data(self):
        service = make_service()
        complete_setup(disabled_modules=["worship"])
        self.client.force_login(make_administrator())
        self.assertEqual(self.client.get(HOME).status_code, 404)
        self.assertEqual(self.client.get(service_url(service)).status_code, 404)
        self.assertTrue(WorshipService.objects.filter(pk=service.pk).exists())

    def test_upcoming_and_past(self):
        make_service(name="Next week")
        make_service(
            name="Last week", starts_at=timezone.now() - datetime.timedelta(days=7)
        )
        self.client.force_login(make_user(perms=VIEWER))
        self.assertEqual(self.names(), ["Next week"])
        self.assertEqual(self.names(when="past"), ["Last week"])

    def test_search_finds_a_theme(self):
        make_theme(make_service(name="First"), title="Grace that forgives")
        make_service(name="Second")
        self.client.force_login(make_user(perms=VIEWER))
        self.assertEqual(self.names(q="forgives"), ["First"])

    def test_page_uses_the_church_word_for_worship_service(self):
        complete_setup(
            labels={"worship_service": {"singular": "Mass", "plural": "Masses"}}
        )
        self.client.force_login(make_user(perms=SCHEDULER))
        response = self.client.get(HOME)
        self.assertContains(response, '<h1 class="h3 mb-0">Masses</h1>', html=True)
        self.assertContains(response, "Add mass")

    def test_worship_opens_from_the_navigation(self):
        self.client.force_login(make_user(perms=VIEWER))
        self.assertContains(self.client.get(reverse("home")), f'href="{HOME}"')


class CalendarTests(WorshipTestCase):
    def test_shows_the_month_of_a_service(self):
        make_service(
            name="Easter morning",
            starts_at=datetime.datetime(2031, 4, 13, 6, 0, tzinfo=MANILA),
        )
        self.client.force_login(make_user(perms=VIEWER))
        response = self.client.get(reverse("worship:calendar"), {"month": "2031-04"})
        self.assertContains(response, "April 2031")
        self.assertContains(response, "6:00 AM Easter morning")
        self.assertContains(response, "?month=2031-03")
        self.assertContains(response, "?month=2031-05")

    def test_bad_month_falls_back_to_this_month(self):
        self.client.force_login(make_user(perms=VIEWER))
        response = self.client.get(reverse("worship:calendar"), {"month": "soon"})
        self.assertEqual(response.context["month"], timezone.localdate().replace(day=1))

    def test_needs_permission(self):
        self.client.force_login(make_user())
        self.assertEqual(self.client.get(reverse("worship:calendar")).status_code, 403)

    def test_a_late_service_lands_on_its_local_date(self):
        late = make_service(
            starts_at=datetime.datetime(2031, 4, 30, 23, 30, tzinfo=MANILA)
        )
        weeks = scheduling.month_grid(2031, 4, [late])
        days = [day for week in weeks for day in week if day.services]
        self.assertEqual([day.date for day in days], [datetime.date(2031, 4, 30)])


class ServiceTests(WorshipTestCase):
    def test_create_takes_the_template_name_and_is_audited(self):
        self.client.force_login(make_user(perms=SCHEDULER))
        response = self.client.post(reverse("worship:service_create"), service_data())
        service = WorshipService.objects.get()
        self.assertRedirects(response, service_url(service))
        self.assertEqual(service.name, "Worship Service")
        self.assertEqual(
            service.starts_at, datetime.datetime(2031, 3, 2, 9, 0, tzinfo=MANILA)
        )
        event = AuditEvent.objects.get()
        self.assertEqual(event.action, AuditEvent.Action.CREATED)
        self.assertEqual(event.changes["Date and time"], ["", "Mar 2, 2031 9:00 AM"])

    def test_create_needs_permission(self):
        self.client.force_login(make_user(perms=VIEWER))
        url = reverse("worship:service_create")
        self.assertEqual(self.client.get(url).status_code, 403)
        self.assertNotContains(self.client.get(HOME), url)

    def test_same_template_and_time_is_rejected(self):
        self.client.force_login(make_user(perms=SCHEDULER))
        self.client.post(reverse("worship:service_create"), service_data())
        response = self.client.post(reverse("worship:service_create"), service_data())
        self.assertContains(response, "already scheduled at that date and time")
        self.assertEqual(WorshipService.objects.count(), 1)

    def test_rehearsal_must_come_first(self):
        self.client.force_login(make_user(perms=SCHEDULER))
        response = self.client.post(
            reverse("worship:service_create"),
            service_data(rehearsal_at="2031-03-02T10:00"),
        )
        self.assertContains(response, "The rehearsal must be before the service.")

    def test_edit_and_cancel(self):
        service = make_service()
        self.client.force_login(make_user(perms=SCHEDULER))
        self.client.post(
            service_url(service, "service_update"),
            service_data(name="Youth night", is_cancelled="on"),
        )
        service.refresh_from_db()
        self.assertEqual(service.name, "Youth night")
        self.assertTrue(service.is_cancelled)
        self.assertEqual(AuditEvent.objects.get().changes["Cancelled"], ["No", "Yes"])
        self.assertContains(self.client.get(service_url(service)), "Cancelled")

    def test_edit_needs_permission(self):
        service = make_service()
        self.client.force_login(make_user(perms=VIEWER))
        url = service_url(service, "service_update")
        self.assertEqual(self.client.get(url).status_code, 403)
        self.assertNotContains(self.client.get(service_url(service)), url)

    def test_detail_needs_permission(self):
        self.client.force_login(make_user())
        self.assertEqual(self.client.get(service_url(make_service())).status_code, 403)


class ThemeTests(WorshipTestCase):
    def setUp(self):
        super().setUp()
        self.service = make_service()
        self.url = service_url(self.service, "theme")

    def theme_data(self, **overrides):
        data = {
            "title": "Grace that forgives",
            "scripture": "Ephesians 2:1-10",
            "series": "",
            "notes": "We were dead in sin, but God made us alive.",
        }
        data.update(overrides)
        return data

    def test_posting_records_who_posted_it(self):
        pastor = make_user(perms=THEME_EDITOR)
        self.client.force_login(pastor)
        response = self.client.post(self.url, self.theme_data())
        self.assertRedirects(response, service_url(self.service))
        theme = Theme.objects.get()
        self.assertEqual(theme.posted_by, pastor)
        self.assertEqual(
            theme.text(),
            "Grace that forgives\nEphesians 2:1-10\n"
            "We were dead in sin, but God made us alive.",
        )
        event = AuditEvent.objects.get()
        self.assertEqual(event.action, AuditEvent.Action.CREATED)
        self.assertEqual(event.changes["Title"], ["", "Grace that forgives"])

    def test_editing_is_audited_and_keeps_the_poster(self):
        pastor = make_user()
        make_theme(self.service, title="Grace", posted_by=pastor)
        series = SermonSeries.objects.create(name="Ephesians")
        self.client.force_login(make_user(perms=THEME_EDITOR))
        self.client.post(self.url, self.theme_data(series=series.pk))
        theme = Theme.objects.get()
        self.assertEqual(theme.posted_by, pastor)
        self.assertEqual(theme.series, series)
        event = AuditEvent.objects.get()
        self.assertEqual(event.action, AuditEvent.Action.CHANGED)
        self.assertEqual(event.changes["Series"], ["", "Ephesians"])

    def test_needs_permission(self):
        self.client.force_login(make_user(perms=VIEWER))
        self.assertEqual(self.client.get(self.url).status_code, 403)
        self.assertNotContains(self.client.get(service_url(self.service)), self.url)

    def test_notes_are_for_people_who_plan(self):
        make_theme(self.service, title="Grace", notes="Private outline")
        self.client.force_login(make_user(perms=VIEWER))
        response = self.client.get(service_url(self.service))
        self.assertContains(response, "Grace")
        self.assertNotContains(response, "Private outline")

        self.client.force_login(make_user(perms=THEME_EDITOR))
        self.assertContains(
            self.client.get(service_url(self.service)), "Private outline"
        )

    def test_form_uses_the_church_word_for_sermon(self):
        complete_setup(labels={"sermon": {"singular": "Homily", "plural": "Homilies"}})
        self.client.force_login(make_user(perms=THEME_EDITOR))
        response = self.client.get(self.url)
        self.assertContains(response, "Homily notes")
        self.assertContains(response, "Homily series")


class AttendanceTests(WorshipTestCase):
    def setUp(self):
        super().setUp()
        self.service = make_service()
        self.url = service_url(self.service, "attendance")

    def test_saving_the_headcount_is_audited(self):
        self.client.force_login(make_user(perms=VIEWER + ["worship.record_attendance"]))
        response = self.client.post(self.url, {"attendance": "142"})
        self.assertRedirects(response, service_url(self.service))
        self.service.refresh_from_db()
        self.assertEqual(self.service.attendance, 142)
        self.assertEqual(AuditEvent.objects.get().changes["Headcount"], ["", "142"])

    def test_needs_permission(self):
        self.client.force_login(make_user(perms=VIEWER))
        self.assertEqual(self.client.post(self.url, {"attendance": 5}).status_code, 403)
        self.assertNotContains(self.client.get(service_url(self.service)), "Headcount")

    def test_viewer_sees_a_recorded_headcount(self):
        self.service.attendance = 1
        self.service.save()
        self.client.force_login(make_user(perms=VIEWER))
        self.assertContains(self.client.get(service_url(self.service)), "1 person")

    def test_rejects_text(self):
        self.client.force_login(make_user(perms=VIEWER + ["worship.record_attendance"]))
        response = self.client.post(self.url, {"attendance": "many"}, follow=True)
        self.assertContains(response, "Enter the headcount as a whole number.")


class ScheduleAheadTests(WorshipTestCase):
    def setUp(self):
        super().setUp()
        self.template = default_template()
        self.template.weekday = ServiceTemplate.Weekday.SUNDAY
        self.template.start_time = datetime.time(9, 0)
        self.template.save()
        self.url = reverse("worship:schedule_ahead")

    def test_creates_one_service_a_week_at_the_usual_time(self):
        friday = datetime.date(2031, 2, 28)
        created = scheduling.schedule_ahead(self.template, 3, None, today=friday)
        self.assertEqual(
            [service.starts_at for service in created],
            [
                datetime.datetime(2031, 3, 2, 9, 0, tzinfo=MANILA),
                datetime.datetime(2031, 3, 9, 9, 0, tzinfo=MANILA),
                datetime.datetime(2031, 3, 16, 9, 0, tzinfo=MANILA),
            ],
        )
        self.assertEqual(AuditEvent.objects.count(), 3)

    def test_starts_today_when_today_is_the_usual_day(self):
        sunday = datetime.date(2031, 3, 2)
        created = scheduling.schedule_ahead(self.template, 1, None, today=sunday)
        self.assertEqual(created[0].local_date, sunday)

    def test_running_it_again_only_fills_the_gaps(self):
        friday = datetime.date(2031, 2, 28)
        scheduling.schedule_ahead(self.template, 2, None, today=friday)
        created = scheduling.schedule_ahead(self.template, 3, None, today=friday)
        self.assertEqual(len(created), 1)
        self.assertEqual(WorshipService.objects.count(), 3)

    def test_follows_the_church_time_zone(self):
        complete_setup(time_zone="America/New_York")
        created = scheduling.schedule_ahead(
            self.template, 1, None, today=datetime.date(2031, 3, 2)
        )
        new_york = zoneinfo.ZoneInfo("America/New_York")
        self.assertEqual(
            created[0].starts_at, datetime.datetime(2031, 3, 2, 9, 0, tzinfo=new_york)
        )

    def test_template_without_a_usual_time_cannot_be_scheduled(self):
        self.template.weekday = None
        self.template.start_time = None
        self.template.save()
        with self.assertRaises(ValueError):
            scheduling.schedule_ahead(self.template, 1, None)
        self.client.force_login(make_user(perms=SCHEDULER))
        self.assertNotContains(self.client.get(HOME), self.url)
        response = self.client.post(
            self.url, {"template": self.template.pk, "weeks": 4}
        )
        self.assertContains(response, "is-invalid")

    def test_page_schedules_and_reports_the_count(self):
        self.client.force_login(make_user(perms=SCHEDULER))
        self.assertContains(self.client.get(HOME), self.url)
        response = self.client.post(
            self.url, {"template": self.template.pk, "weeks": 4}, follow=True
        )
        self.assertContains(response, "4 services were added to the schedule.")
        response = self.client.post(
            self.url, {"template": self.template.pk, "weeks": 4}, follow=True
        )
        self.assertContains(response, "Those weeks were already scheduled.")

    def test_needs_permission(self):
        self.client.force_login(make_user(perms=VIEWER))
        self.assertEqual(self.client.get(self.url).status_code, 403)


class TemplateTests(WorshipTestCase):
    def slot_data(self, rows, initial=0):
        data = {
            "slots-TOTAL_FORMS": str(len(rows)),
            "slots-INITIAL_FORMS": str(initial),
            "slots-MIN_NUM_FORMS": "0",
            "slots-MAX_NUM_FORMS": "1000",
        }
        for index, row in enumerate(rows):
            for name, value in row.items():
                data[f"slots-{index}-{name}"] = value
        return data

    def test_a_neutral_template_is_seeded(self):
        template = default_template()
        self.assertEqual(template.name, "Worship Service")
        self.assertEqual(
            template.slot_summary(),
            "Opening (Upbeat), Praise (Mid-tempo), Worship (Slow), Response (Slow)",
        )
        self.assertFalse(template.repeats_weekly)

    def test_list_needs_permission(self):
        url = reverse("worship:template_list")
        self.client.force_login(make_user(perms=VIEWER))
        self.assertEqual(self.client.get(url).status_code, 403)
        self.client.force_login(make_user(perms=["worship.view_servicetemplate"]))
        response = self.client.get(url)
        self.assertContains(response, "Opening (Upbeat)")
        self.assertNotContains(response, "Add service template")

    def test_create_with_slots(self):
        self.client.force_login(make_administrator())
        response = self.client.post(
            reverse("worship:template_create"),
            {
                "name": "Youth night",
                "description": "",
                "weekday": "4",
                "start_time": "19:00",
                "sort_order": "20",
                "is_active": "on",
                **self.slot_data(
                    [
                        {"name": "Opener", "feel": "upbeat", "position": "1"},
                        {"name": "Response", "feel": "", "position": "2"},
                        {"name": "", "feel": "", "position": "0"},
                    ]
                ),
            },
        )
        self.assertRedirects(response, reverse("worship:template_list"))
        template = ServiceTemplate.objects.get(name="Youth night")
        self.assertTrue(template.repeats_weekly)
        self.assertEqual(template.slot_summary(), "Opener (Upbeat), Response")
        event = AuditEvent.objects.get()
        self.assertEqual(event.action, AuditEvent.Action.CREATED)
        self.assertEqual(
            event.changes["Song slots"], ["", "Opener (Upbeat) / Response"]
        )
        self.assertEqual(event.changes["Usual day"], ["", "Friday"])

    def test_edit_changes_and_removes_slots(self):
        template = default_template()
        opening, praise, worship, response = template.slots.all()
        self.client.force_login(make_administrator())
        rows = [
            {
                "id": opening.pk,
                "name": "Call to worship",
                "feel": "mid",
                "position": 10,
            },
            {"id": praise.pk, "name": "Praise", "feel": "mid", "position": 20},
            {"id": worship.pk, "name": "Worship", "feel": "slow", "position": 30},
            {
                "id": response.pk,
                "name": "Response",
                "feel": "slow",
                "position": 40,
                "DELETE": "on",
            },
        ]
        self.client.post(
            reverse("worship:template_update", kwargs={"pk": template.pk}),
            {
                "name": template.name,
                "description": template.description,
                "weekday": "",
                "start_time": "",
                "sort_order": "10",
                "is_active": "on",
                **self.slot_data(rows, initial=4),
            },
        )
        self.assertEqual(
            list(template.slots.values_list("name", flat=True)),
            ["Call to worship", "Praise", "Worship"],
        )
        self.assertFalse(TemplateSlot.objects.filter(pk=response.pk).exists())
        changes = AuditEvent.objects.get().changes
        self.assertEqual(list(changes), ["Song slots"])

    def test_usual_day_and_time_go_together(self):
        self.client.force_login(make_administrator())
        response = self.client.post(
            reverse("worship:template_create"),
            {
                "name": "Midweek",
                "weekday": "2",
                "start_time": "",
                "sort_order": "0",
                "is_active": "on",
                **self.slot_data([]),
            },
        )
        self.assertContains(
            response, "Give both the usual day and the usual start time"
        )
        self.assertFalse(ServiceTemplate.objects.filter(name="Midweek").exists())

    def test_create_and_edit_need_permission(self):
        template = default_template()
        self.client.force_login(make_user(perms=["worship.view_servicetemplate"]))
        for url in (
            reverse("worship:template_create"),
            reverse("worship:template_update", kwargs={"pk": template.pk}),
        ):
            self.assertEqual(self.client.get(url).status_code, 403)

    def test_inactive_template_is_not_offered_for_new_services(self):
        template = default_template()
        template.is_active = False
        template.save()
        self.client.force_login(make_user(perms=SCHEDULER))
        form = self.client.get(reverse("worship:service_create")).context["form"]
        self.assertNotIn(template, form.fields["template"].queryset)


class SeriesTests(WorshipTestCase):
    def test_list_is_named_in_the_church_words(self):
        complete_setup(labels={"sermon": {"singular": "Message", "plural": "Messages"}})
        self.client.force_login(make_administrator())
        response = self.client.get(reverse("worship:series_list"))
        self.assertContains(
            response, '<h1 class="h3 mb-0">Message series</h1>', html=True
        )
        self.assertContains(response, "Service templates")  # settings tabs

    def test_add_a_series(self):
        self.client.force_login(make_administrator())
        self.client.post(
            reverse("worship:series_create"),
            {"name": "Advent", "sort_order": 0, "is_active": "on"},
        )
        self.assertTrue(SermonSeries.objects.filter(name="Advent").exists())

    def test_needs_permission(self):
        self.client.force_login(make_user(perms=VIEWER))
        self.assertEqual(
            self.client.get(reverse("worship:series_list")).status_code, 403
        )


class DefaultRoleTests(WorshipTestCase):
    def test_pastoral_staff_schedule_and_post_themes(self):
        user = make_user(roles=["pastoral_staff"])
        for permission in (
            "worship.add_worshipservice",
            "worship.change_theme",
            "worship.add_servicetemplate",
        ):
            self.assertTrue(user.has_perm(permission), permission)

    def test_worship_leader_and_team_member_see_the_schedule_only(self):
        for role in ("worship_leader", "team_member"):
            user = make_user(roles=[role])
            self.assertTrue(user.has_perm("worship.view_worshipservice"))
            self.assertFalse(user.has_perm("worship.add_worshipservice"))
            self.assertFalse(user.has_perm("worship.change_theme"))
