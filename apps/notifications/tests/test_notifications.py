"""The Notifications pages (Phase 8; core since Phase 9A, A5): anyone
signed in sees their own, whichever Modules are switched on."""

from django.test import TestCase
from django.urls import reverse

from apps.core.testing import complete_setup, first_church, make_user
from apps.notifications.models import Notification
from apps.notifications.services import notify, unread_count

NOTIFICATIONS = reverse("notifications:list")
LINK = "/worship/"


class NotificationPageTests(TestCase):
    def setUp(self):
        complete_setup()
        self.person = make_user(roles=["church_member"])
        self.other = make_user(roles=["church_member"])
        notify([self.person], "Your request was approved.", LINK, church=first_church())
        self.note = Notification.objects.get(recipient=self.person)

    def test_the_navigation_shows_the_unread_count(self):
        notify([self.person], "Another note", church=first_church())
        self.client.force_login(self.person)
        page = self.client.get(reverse("home"))
        self.assertContains(page, 'aria-label="2 unread"')
        self.client.force_login(self.other)
        self.assertNotContains(self.client.get(reverse("home")), "unread")

    def test_the_list_shows_only_your_own(self):
        notify([self.other], "Someone else's note", church=first_church())
        self.client.force_login(self.person)
        page = self.client.get(NOTIFICATIONS)
        self.assertContains(page, "Your request was approved.")
        self.assertNotContains(page, "Someone else&#x27;s note")

    def test_opening_marks_it_read_and_goes_where_it_points(self):
        self.client.force_login(self.person)
        response = self.client.post(
            reverse("notifications:open", kwargs={"pk": self.note.pk})
        )
        self.assertRedirects(response, LINK, fetch_redirect_response=False)
        self.note.refresh_from_db()
        self.assertTrue(self.note.is_read)

    def test_an_outside_link_is_never_followed(self):
        notify(
            [self.person],
            "Odd note",
            "https://example.com/elsewhere",
            church=first_church(),
        )
        odd = Notification.objects.get(text="Odd note")
        self.client.force_login(self.person)
        response = self.client.post(
            reverse("notifications:open", kwargs={"pk": odd.pk})
        )
        self.assertRedirects(response, NOTIFICATIONS)

    def test_mark_all_as_read(self):
        notify([self.person], "Another note", church=first_church())
        self.client.force_login(self.person)
        page = self.client.get(NOTIFICATIONS)
        self.assertContains(page, "Mark all as read")
        self.assertRedirects(
            self.client.post(reverse("notifications:read_all")), NOTIFICATIONS
        )
        self.assertEqual(unread_count(self.person), 0)

    def test_someone_elses_notification_is_a_404(self):
        self.client.force_login(self.other)
        response = self.client.post(
            reverse("notifications:open", kwargs={"pk": self.note.pk})
        )
        self.assertEqual(response.status_code, 404)
        self.note.refresh_from_db()
        self.assertFalse(self.note.is_read)

    def test_a_note_without_a_link_just_marks_read(self):
        notify([self.person], "Plain note", church=first_church())
        plain = Notification.objects.get(text="Plain note")
        self.client.force_login(self.person)
        response = self.client.post(
            reverse("notifications:open", kwargs={"pk": plain.pk})
        )
        self.assertRedirects(response, NOTIFICATIONS)

    def test_a_key_updates_the_unread_note_instead_of_adding_one(self):
        notify([self.person], "First", key="k", church=first_church())
        notify([self.person], "Second", key="k", church=first_church())
        self.assertEqual(
            list(Notification.objects.filter(key="k").values_list("text", flat=True)),
            ["Second"],
        )

    def test_they_work_with_every_module_switched_off(self):
        complete_setup(
            disabled_modules=["members", "worship", "teams", "announcements"]
        )
        self.client.force_login(self.person)
        page = self.client.get(reverse("home"))
        self.assertContains(page, 'aria-label="1 unread"')
        self.assertContains(self.client.get(NOTIFICATIONS), "was approved")

    def test_signed_out_people_are_sent_to_sign_in(self):
        response = self.client.get(NOTIFICATIONS)
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("accounts:login"), response["Location"])
