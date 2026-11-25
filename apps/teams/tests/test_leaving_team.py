"""Leaving the team through a role change (Phase 9A, A2; Design-Decisions,
"Adviser comments, 24 Nov").

When a role change or deactivation takes away ``teams.view_assignment``,
the user form lists the person's Pending or Accepted assignments on coming
services that aren't cancelled; the admin ends them or keeps them. Past
assignments are never touched.
"""

import datetime

from django.contrib.auth.models import Permission
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
    make_service,
    make_user,
)
from apps.teams.models import Assignment, SwapRequest


class LeavingTheTeamTests(TestCase):
    def setUp(self):
        complete_setup()
        self.admin = make_administrator()
        self.client.force_login(self.admin)
        self.person = make_user(roles=["team_member"], first_name="Ben")
        self.url = reverse("accounts:user_update", kwargs={"pk": self.person.pk})
        self.church_member = Role.objects.get(key="church_member")
        now = timezone.now()
        self.coming = make_assignment(make_service(), self.person, reply="accepted")
        self.pending = make_assignment(
            make_service(starts_at=now + datetime.timedelta(days=14)), self.person
        )
        self.declined = make_assignment(
            make_service(starts_at=now + datetime.timedelta(days=21)),
            self.person,
            reply="declined",
        )
        self.cancelled = make_assignment(
            make_service(
                starts_at=now + datetime.timedelta(days=28), is_cancelled=True
            ),
            self.person,
        )
        self.past = make_assignment(
            make_service(starts_at=now - datetime.timedelta(days=7)),
            self.person,
            reply="accepted",
        )

    def post(self, **extra):
        data = edit_data(self.person, roles=[self.church_member.pk])
        data.update(extra)
        return self.client.post(self.url, data)

    def ids(self):
        return set(Assignment.objects.values_list("pk", flat=True))

    def test_first_save_lists_coming_assignments_and_changes_nothing(self):
        response = self.post()
        self.assertEqual(response.status_code, 200)
        (consequence,) = response.context["consequences"]
        self.assertEqual(consequence.title, "Assignments on coming services")
        self.assertEqual(len(consequence.items), 2)
        self.assertIn("(Accepted)", consequence.items[0])
        self.assertIn("(Pending)", consequence.items[1])
        self.assertContains(response, "This change takes Ben off the team.")
        self.person.refresh_from_db()
        self.assertEqual(
            [r.key for r in self.person.roles_in(first_church())], ["team_member"]
        )
        self.assertEqual(len(self.ids()), 5)

    def test_end_frees_the_places_and_withdraws_open_swaps(self):
        swap = SwapRequest.objects.create(
            assignment=self.coming,
            service=self.coming.service,
            part=self.coming.part,
            requested_by=self.person,
        )
        response = self.post(after_change="end", after_change_shown="1")
        self.assertRedirects(response, reverse("accounts:user_list"))
        self.assertEqual(
            self.ids(), {self.declined.pk, self.cancelled.pk, self.past.pk}
        )
        swap.refresh_from_db()
        self.assertEqual(swap.status, SwapRequest.Status.WITHDRAWN)
        self.person.refresh_from_db()
        self.assertEqual(
            [r.key for r in self.person.roles_in(first_church())], ["church_member"]
        )
        event = AuditEvent.objects.filter(object_id=str(self.person.pk)).first()
        self.assertEqual(
            event.changes["Assignments on coming services"], ["", "Ended (2)"]
        )
        self.assertEqual(
            AuditEvent.objects.filter(action=AuditEvent.Action.DELETED).count(), 2
        )

    def test_keep_changes_no_assignment(self):
        response = self.post(after_change="keep", after_change_shown="1")
        self.assertRedirects(response, reverse("accounts:user_list"))
        self.assertEqual(len(self.ids()), 5)
        event = AuditEvent.objects.filter(object_id=str(self.person.pk)).first()
        self.assertEqual(
            event.changes["Assignments on coming services"], ["", "Kept (2)"]
        )

    def test_saving_the_warning_without_a_choice_asks_again(self):
        response = self.post(after_change_shown="1")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Choose whether to end or keep them.")
        self.assertEqual(len(self.ids()), 5)

    def test_past_assignments_are_never_changed(self):
        self.post(after_change="end", after_change_shown="1")
        past = Assignment.objects.get(pk=self.past.pk)
        self.assertEqual(past.reply, "accepted")
        self.assertEqual(past.person, self.person)

    def test_deactivating_also_lists_them(self):
        data = edit_data(self.person, is_active="")
        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["consequences"][0].items), 2)

    def test_still_on_the_team_through_another_role(self):
        leader = Role.objects.get(key="worship_leader")
        data = edit_data(self.person, roles=[self.church_member.pk, leader.pk])
        response = self.client.post(self.url, data)
        self.assertRedirects(response, reverse("accounts:user_list"))
        self.assertEqual(len(self.ids()), 5)

    def test_a_permission_given_to_the_user_directly_doesnt_keep_them_on(self):
        # Permissions come only from roles (decision 0014).
        person = make_user(roles=["team_member"])
        person.user_permissions.add(Permission.objects.get(codename="view_assignment"))
        make_assignment(make_service(), person)
        response = self.client.post(
            reverse("accounts:user_update", kwargs={"pk": person.pk}),
            edit_data(person, roles=[self.church_member.pk]),
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["consequences"][0].items), 1)

    def test_no_coming_assignments_saves_at_once(self):
        person = make_user(roles=["team_member"])
        response = self.client.post(
            reverse("accounts:user_update", kwargs={"pk": person.pk}),
            edit_data(person, roles=[self.church_member.pk]),
        )
        self.assertRedirects(response, reverse("accounts:user_list"))

    def test_teams_switched_off_saves_at_once(self):
        complete_setup(disabled_modules=["teams"])
        response = self.post()
        self.assertRedirects(response, reverse("accounts:user_list"))
        self.assertEqual(len(self.ids()), 5)
