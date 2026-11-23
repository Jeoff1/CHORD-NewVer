"""Announcements (Design-Decisions, Phase 8, decision 7)."""

import datetime

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.announcements import services
from apps.announcements.models import Announcement
from apps.audit.models import AuditEvent
from apps.core.testing import (
    complete_setup,
    make_assignment,
    make_service,
    make_team_part,
    make_user,
)

LIST = reverse("announcements:list")
CREATE = reverse("announcements:create")
Audience = Announcement.Audience


def archive_url(announcement):
    return reverse(
        "announcements:archive", kwargs={"public_id": announcement.public_id}
    )


class AnnouncementTestCase(TestCase):
    def setUp(self):
        complete_setup()
        self.leader = make_user(roles=["worship_leader"])
        self.pastor = make_user(roles=["pastoral_staff"])
        self.member = make_user(roles=["team_member"])
        self.office = make_user(roles=["office_staff"])
        self.service = make_service()
        part = make_team_part()
        self.pending = make_user(roles=["team_member"])
        self.accepted = make_user(roles=["team_member"])
        self.declined = make_user(roles=["team_member"])
        make_assignment(self.service, self.pending, part)
        make_assignment(self.service, self.accepted, part, reply="accepted")
        make_assignment(self.service, self.declined, part, reply="declined")

    def titles(self, user):
        return [a.title for a in services.visible_to(user)]


class AudienceTests(AnnouncementTestCase):
    def test_everyone_means_everyone_signed_in(self):
        services.post(
            self.leader, title="Picnic", body="Bring food.", audience=Audience.EVERYONE
        )
        for user in (self.leader, self.member, self.office, self.declined):
            self.assertEqual(self.titles(user), ["Picnic"], user)

    def test_one_services_team_means_its_pending_and_accepted_people(self):
        services.post(
            self.pastor,
            title="Rehearsal moved",
            body="Now at 6.",
            audience=Audience.SERVICE_TEAM,
            service=self.service,
        )
        for user in (self.pending, self.accepted, self.pastor):
            self.assertEqual(self.titles(user), ["Rehearsal moved"], user)
        for user in (self.declined, self.member, self.office, self.leader):
            self.assertEqual(self.titles(user), [], user)

    def test_a_service_team_needs_a_coming_service_that_isnt_cancelled(self):
        past = make_service(starts_at=timezone.now() - datetime.timedelta(hours=1))
        cancelled = make_service(is_cancelled=True)
        for service in (None, past, cancelled):
            with self.assertRaises(services.AnnouncementRefused):
                services.post(
                    self.leader,
                    title="X",
                    body="Y",
                    audience=Audience.SERVICE_TEAM,
                    service=service,
                )
        self.assertFalse(Announcement.objects.exists())

    def test_while_teams_is_off_only_everyone_is_offered_and_shown(self):
        services.post(
            self.leader,
            title="Team note",
            body="Y",
            audience=Audience.SERVICE_TEAM,
            service=self.service,
        )
        complete_setup(disabled_modules=["teams"])
        self.assertEqual(self.titles(self.accepted), [])
        with self.assertRaises(services.AnnouncementRefused):
            services.post(
                self.leader,
                title="X",
                body="Y",
                audience=Audience.SERVICE_TEAM,
                service=self.service,
            )
        self.client.force_login(self.leader)
        page = self.client.get(CREATE)
        self.assertContains(page, "Everyone signed in")
        self.assertNotContains(page, "team")

    def test_posting_is_in_the_audit_trail(self):
        services.post(self.leader, title="Picnic", body="B", audience=Audience.EVERYONE)
        event = AuditEvent.objects.get(content_type__model="announcement")
        self.assertEqual(event.changes["To"], ["", "Everyone"])


class ArchiveTests(AnnouncementTestCase):
    def setUp(self):
        super().setUp()
        self.note = services.post(
            self.leader, title="Picnic", body="B", audience=Audience.EVERYONE
        )

    def test_only_the_author_archives_and_then_nobody_sees_it(self):
        with self.assertRaises(services.AnnouncementRefused):
            services.archive(self.note, self.pastor)
        self.client.force_login(self.pastor)
        self.assertEqual(self.client.post(archive_url(self.note)).status_code, 404)
        self.client.force_login(self.leader)
        self.assertRedirects(self.client.post(archive_url(self.note)), LIST)
        self.note.refresh_from_db()
        self.assertTrue(self.note.is_archived)
        self.assertEqual(self.titles(self.member), [])
        self.assertEqual(self.titles(self.leader), [])
        # Archiving again changes nothing.
        services.archive(self.note, self.leader)

    def test_the_author_sees_the_archive_button_others_dont(self):
        self.client.force_login(self.leader)
        self.assertContains(self.client.get(LIST), ">Archive</button>")
        self.client.force_login(self.member)
        page = self.client.get(LIST)
        self.assertContains(page, "Picnic")
        self.assertNotContains(page, ">Archive</button>")


class AnnouncementPageTests(AnnouncementTestCase):
    def test_leader_and_pastor_post_others_are_refused(self):
        for user in (self.leader, self.pastor):
            self.client.force_login(user)
            response = self.client.post(
                CREATE,
                {"title": f"From {user.pk}", "body": "Hello", "audience": "everyone"},
            )
            self.assertRedirects(response, LIST)
        for user in (self.member, self.office):
            self.client.force_login(user)
            self.assertEqual(self.client.get(CREATE).status_code, 403)
            response = self.client.post(
                CREATE, {"title": "No", "body": "No", "audience": "everyone"}
            )
            self.assertEqual(response.status_code, 403)
        self.assertEqual(Announcement.objects.count(), 2)

    def test_posting_to_a_services_team(self):
        self.client.force_login(self.leader)
        page = self.client.get(CREATE)
        self.assertContains(page, "worship service&#x27;s team")
        response = self.client.post(
            CREATE,
            {
                "title": "Bring music",
                "body": "Printed charts.",
                "audience": "service_team",
                "service": self.service.pk,
            },
        )
        self.assertRedirects(response, LIST)
        self.client.force_login(self.accepted)
        self.assertContains(self.client.get(LIST), "Bring music")

    def test_a_service_team_without_a_service_is_a_form_error(self):
        self.client.force_login(self.leader)
        response = self.client.post(
            CREATE, {"title": "X", "body": "Y", "audience": "service_team"}
        )
        self.assertContains(response, "Choose whose team it is for.")
        self.assertFalse(Announcement.objects.exists())

    def test_everyone_signed_in_reads_the_list_signed_out_people_dont(self):
        self.assertEqual(self.client.get(LIST).status_code, 302)
        self.client.force_login(self.office)
        self.assertContains(self.client.get(LIST), "There are no announcements.")

    def test_switched_off_announcements_returns_404(self):
        note = services.post(
            self.leader, title="P", body="B", audience=Audience.EVERYONE
        )
        complete_setup(disabled_modules=["announcements"])
        self.client.force_login(self.leader)
        for url in (LIST, CREATE):
            self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(self.client.post(archive_url(note)).status_code, 404)
        self.assertTrue(Announcement.objects.filter(pk=note.pk).exists())
