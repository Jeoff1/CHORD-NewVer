"""A role change keeps history (Phase 9A, A2; Design-Decisions, "Adviser
comments, 24 Nov"): "what if X is no longer the Worship Leader next month?"
"""

import datetime

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import Role
from apps.accounts.tests.test_user_management import edit_data
from apps.audit.models import AuditEvent
from apps.core.testing import (
    complete_setup,
    first_church,
    make_administrator,
    make_assignment,
    make_chord_sheet,
    make_lineup,
    make_service,
    make_song,
    make_user,
)
from apps.teams.models import Assignment


class RoleChangeKeepsHistoryTests(TestCase):
    def setUp(self):
        complete_setup()
        self.admin = make_administrator()
        self.client.force_login(self.admin)
        self.leader = make_user(
            roles=["worship_leader"], first_name="Ana", last_name="Cruz"
        )
        self.church_member = Role.objects.get(key="church_member")
        # What the leader did while leading worship.
        past = make_service(starts_at=timezone.now() - datetime.timedelta(days=14))
        self.lineup = make_lineup(past, [make_song()])
        self.lineup.confirmed_by = self.lineup.edited_by = self.leader
        self.lineup.confirmed_at = self.lineup.edited_at = timezone.now()
        self.lineup.save()
        self.sheet = make_chord_sheet(
            make_song(), added_by=self.leader, approved_by=self.leader
        )
        self.past_assignment = make_assignment(past, self.leader, reply="accepted")

    def make_church_member(self):
        return self.client.post(
            reverse("accounts:user_update", kwargs={"pk": self.leader.pk}),
            edit_data(self.leader, roles=[self.church_member.pk]),
        )

    def test_past_records_stay_under_their_name(self):
        response = self.make_church_member()
        self.assertRedirects(response, reverse("accounts:user_list"))
        self.leader.refresh_from_db()
        self.assertEqual(
            list(self.leader.roles_in(first_church())), [self.church_member]
        )

        self.lineup.refresh_from_db()
        self.sheet.refresh_from_db()
        self.assertEqual(self.lineup.confirmed_by, self.leader)
        self.assertEqual(self.lineup.edited_by, self.leader)
        self.assertEqual(self.sheet.added_by, self.leader)
        self.assertEqual(self.sheet.approved_by, self.leader)
        self.assertEqual(
            Assignment.objects.get(pk=self.past_assignment.pk).reply, "accepted"
        )
        # Their earlier Audit Trail entries are still theirs.
        self.assertTrue(AuditEvent.objects.filter(actor=self.admin).exists())

    def test_role_history_lists_both_roles(self):
        self.make_church_member()
        response = self.client.get(
            reverse("accounts:user_update", kwargs={"pk": self.leader.pk})
        )
        history = response.context["role_history"]
        self.assertEqual(len(history), 1)
        event, rows = history[0]
        self.assertEqual(rows, [("Roles", "Worship Leader", "Church Member")])
        self.assertEqual(event.actor, self.admin)
        self.assertContains(response, "Role history")
        self.assertContains(response, "Worship Leader → Church Member")

    def test_deactivating_shows_in_the_history(self):
        self.client.post(
            reverse("accounts:user_update", kwargs={"pk": self.leader.pk}),
            edit_data(self.leader, is_active=""),
        )
        response = self.client.get(
            reverse("accounts:user_update", kwargs={"pk": self.leader.pk})
        )
        _, rows = response.context["role_history"][0]
        self.assertEqual(rows, [("Active", "Yes", "No")])

    def test_no_history_yet(self):
        response = self.client.get(
            reverse("accounts:user_update", kwargs={"pk": self.leader.pk})
        )
        self.assertEqual(response.context["role_history"], [])
        self.assertContains(response, "No role changes recorded yet.")

    def test_history_needs_the_edit_permission(self):
        self.client.force_login(make_user(roles=["worship_leader"]))
        response = self.client.get(
            reverse("accounts:user_update", kwargs={"pk": self.leader.pk})
        )
        self.assertEqual(response.status_code, 403)
