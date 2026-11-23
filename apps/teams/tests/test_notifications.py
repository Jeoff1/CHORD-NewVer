"""In-app Notifications (Design-Decisions, Phase 8, decision 6)."""

import datetime

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.core.testing import (
    complete_setup,
    make_assignment,
    make_lineup,
    make_service,
    make_song,
    make_team_part,
    make_team_profile,
    make_user,
)
from apps.teams import notifying, rostering
from apps.teams.models import Notification
from apps.worship import lineups
from apps.worship.models import Lineup

NOTIFICATIONS = reverse("teams:notifications")


def texts(user):
    return list(
        Notification.objects.filter(recipient=user).values_list("text", flat=True)
    )


class NotificationTestCase(TestCase):
    def setUp(self):
        complete_setup()
        self.leader = make_user(
            roles=["worship_leader"], first_name="Lea", last_name="Lead"
        )
        self.pastor = make_user(
            roles=["pastoral_staff"], first_name="Pat", last_name="Pastor"
        )
        self.part = make_team_part("Bass guitar")
        self.service = make_service()
        self.pending = make_user(roles=["team_member"])
        self.accepted = make_user(roles=["team_member"])
        self.declined = make_user(roles=["team_member"])
        self.elsewhere = make_user(roles=["team_member"])
        self.outsider = make_user(roles=["team_member"])
        make_assignment(self.service, self.pending, self.part)
        make_assignment(self.service, self.accepted, self.part, reply="accepted")
        make_assignment(self.service, self.declined, self.part, reply="declined")
        make_assignment(make_service(), self.elsewhere, self.part, reply="accepted")
        self.lineup = make_lineup(
            self.service,
            [make_song(title="Alpha"), make_song(title="Beta")],
            confirmed=False,
        )

    def item(self):
        return self.lineup.items.first()

    def assert_only_serving_people_told(self, text):
        self.assertEqual(texts(self.pending), [text])
        self.assertEqual(texts(self.accepted), [text])
        for person in (self.declined, self.elsewhere, self.outsider):
            self.assertEqual(texts(person), [], person)


class LineupNotificationTests(NotificationTestCase):
    def test_confirming_tells_the_pending_and_accepted_team(self):
        lineups.confirm(self.lineup, self.leader)
        self.assert_only_serving_people_told(
            f"The lineup for {self.service} was confirmed."
        )
        self.assertEqual(texts(self.leader), [])

    def test_the_leaders_edit_of_a_confirmed_lineup_says_changed_by(self):
        lineups.confirm(self.lineup, self.leader)
        Notification.objects.all().delete()
        lineups.set_details(self.lineup, self.item(), "G", "", self.leader)
        self.assert_only_serving_people_told(
            f"The confirmed lineup for {self.service} was changed by Lea Lead."
        )

    def test_the_pastors_edit_says_edited_by_the_pastor(self):
        lineups.confirm(self.lineup, self.leader)
        Notification.objects.all().delete()
        lineups.set_details(self.lineup, self.item(), "A", "", self.pastor)
        self.assert_only_serving_people_told(
            f"The confirmed lineup for {self.service} was edited by Pastor (Pat Pastor)."
        )
        self.assertEqual(texts(self.pastor), [])

    def test_the_person_who_caused_it_isnt_told_even_when_assigned(self):
        make_assignment(self.service, self.leader, make_team_part(), reply="accepted")
        lineups.confirm(self.lineup, self.leader)
        self.assertEqual(texts(self.leader), [])
        self.assertEqual(len(texts(self.accepted)), 1)

    def test_drafts_tell_nobody(self):
        """Team members see nothing of a lineup until it is confirmed."""
        lineups.set_details(self.lineup, self.item(), "G", "", self.leader)
        lineups.confirm(self.lineup, self.leader)
        lineups.reopen(Lineup.objects.get(pk=self.lineup.pk), self.pastor)
        Notification.objects.all().delete()
        lineups.set_details(self.lineup, self.item(), "D", "", self.leader)
        self.assertFalse(Notification.objects.exists())

    def test_repeated_edits_update_one_unread_note(self):
        lineups.confirm(self.lineup, self.leader)
        lineups.set_details(self.lineup, self.item(), "G", "", self.leader)
        lineups.set_details(self.lineup, self.item(), "A", "", self.pastor)
        notes = texts(self.accepted)
        self.assertEqual(len(notes), 2)  # the confirmation and one edit note
        self.assertIn("edited by Pastor (Pat Pastor)", notes[0])
        # Once read, a later edit is a new note.
        notifying.mark_all_read(self.accepted)
        # The pastor's lock now stops the leader, so the pastor edits again.
        lineups.set_details(self.lineup, self.item(), "B", "", self.pastor)
        self.assertEqual(len(texts(self.accepted)), 3)

    def test_nothing_for_a_past_or_cancelled_service(self):
        past = make_service(starts_at=timezone.now() - datetime.timedelta(hours=2))
        make_assignment(past, self.accepted, self.part, reply="accepted")
        old = make_lineup(past, [make_song()], confirmed=False)
        lineups.confirm(old, self.leader)
        self.service.is_cancelled = True
        self.service.save()
        Lineup.objects.filter(pk=self.lineup.pk).update(status=Lineup.Status.CONFIRMED)
        lineups.set_details(
            Lineup.objects.get(pk=self.lineup.pk), self.item(), "G", "", self.leader
        )
        self.assertFalse(Notification.objects.exists())

    def test_nothing_while_teams_is_off(self):
        complete_setup(disabled_modules=["teams"])
        lineups.confirm(self.lineup, self.leader)
        self.assertFalse(Notification.objects.exists())


class AssignedNotificationTests(NotificationTestCase):
    def test_a_person_is_told_when_assigned(self):
        newcomer = make_user(roles=["team_member"])
        make_team_profile(newcomer, [self.part])
        rostering.assign(self.service, self.part, newcomer, self.leader)
        self.assertEqual(
            texts(newcomer), [f"You were assigned to Bass guitar at {self.service}."]
        )
        self.assertEqual(
            Notification.objects.get(recipient=newcomer).url,
            reverse("teams:my_schedule"),
        )

    def test_assigning_yourself_tells_nobody(self):
        make_team_profile(self.leader, [self.part])
        rostering.assign(self.service, self.part, self.leader, self.leader)
        self.assertFalse(Notification.objects.exists())


class NotificationPageTests(NotificationTestCase):
    def setUp(self):
        super().setUp()
        lineups.confirm(self.lineup, self.leader)
        self.note = Notification.objects.get(recipient=self.accepted)

    def test_the_navigation_shows_the_unread_count(self):
        notifying.notify([self.accepted], "Another note")
        self.client.force_login(self.accepted)
        page = self.client.get(reverse("home"))
        self.assertContains(page, 'aria-label="2 unread"')
        self.client.force_login(self.outsider)
        self.assertNotContains(self.client.get(reverse("home")), "unread")

    def test_opening_marks_it_read_and_goes_to_the_confirmed_lineup(self):
        self.client.force_login(self.accepted)
        response = self.client.post(
            reverse("teams:notification_open", kwargs={"pk": self.note.pk})
        )
        lineup_url = reverse(
            "worship:lineup", kwargs={"public_id": self.service.public_id}
        )
        self.assertRedirects(response, lineup_url)
        self.note.refresh_from_db()
        self.assertTrue(self.note.is_read)

    def test_mark_all_as_read(self):
        notifying.notify([self.accepted], "Another note")
        self.client.force_login(self.accepted)
        page = self.client.get(NOTIFICATIONS)
        self.assertContains(page, "Mark all as read")
        self.assertContains(page, "was confirmed")
        self.assertRedirects(
            self.client.post(reverse("teams:notifications_read")), NOTIFICATIONS
        )
        self.assertEqual(notifying.unread_count(self.accepted), 0)

    def test_someone_elses_notification_is_a_404(self):
        self.client.force_login(self.outsider)
        response = self.client.post(
            reverse("teams:notification_open", kwargs={"pk": self.note.pk})
        )
        self.assertEqual(response.status_code, 404)
        self.note.refresh_from_db()
        self.assertFalse(self.note.is_read)

    def test_a_note_without_a_link_just_marks_read(self):
        notifying.notify([self.accepted], "Plain note")
        plain = Notification.objects.get(text="Plain note")
        self.client.force_login(self.accepted)
        response = self.client.post(
            reverse("teams:notification_open", kwargs={"pk": plain.pk})
        )
        self.assertRedirects(response, NOTIFICATIONS)

    def test_switched_off_teams_hides_notifications(self):
        complete_setup(disabled_modules=["teams"])
        self.client.force_login(self.accepted)
        self.assertEqual(self.client.get(NOTIFICATIONS).status_code, 404)
        self.assertNotContains(self.client.get(reverse("home")), "Notifications")
        self.assertTrue(Notification.objects.filter(pk=self.note.pk).exists())
