"""UI/UX Phase 9 (28 Nov 2026): notifications and announcements screens. UI-UX-Master-Plan.md §15.
The bell's popover reuses the Notifications page's list; no new endpoint."""

from django.test import TestCase
from django.urls import reverse

from apps.core.testing import complete_setup, first_church, make_user
from apps.notifications.services import notify


class NotificationScreenTests(TestCase):
    def setUp(self):
        complete_setup()
        self.person = make_user(roles=["team_member"])
        self.client.force_login(self.person)

    def test_the_header_bell_has_a_popover_that_falls_back_to_the_link(self):
        page = self.client.get(reverse("home"))
        self.assertContains(page, "data-chord-bell")
        self.assertContains(
            page, f'href="{reverse("notifications:list")}" aria-haspopup="dialog"'
        )
        self.assertContains(
            page, 'id="chord-bell-pop" role="dialog" aria-label="Notifications" hidden'
        )

    def test_unread_notifications_are_marked(self):
        notify([self.person], "You were assigned to Sunday.", church=first_church())
        page = self.client.get(reverse("notifications:list"))
        self.assertContains(page, "data-notif-list")
        self.assertContains(page, 'class="chord-notif is-unread"')
        self.assertContains(page, '<span class="visually-hidden">New: </span>')
        self.assertNotContains(page, "badge text-bg")

    def test_no_notifications_is_an_empty_state(self):
        page = self.client.get(reverse("notifications:list"))
        self.assertContains(page, "chord-empty")
        self.assertContains(page, "No notifications.")

    def test_announcements_are_a_feed(self):
        page = self.client.get(reverse("announcements:list"))
        self.assertContains(page, 'class="chord-feed"')
        self.assertContains(page, "There are no announcements.")
