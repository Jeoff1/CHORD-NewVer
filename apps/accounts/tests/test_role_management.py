from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import Role
from apps.accounts.roles import managed_permissions
from apps.audit.models import AuditEvent
from apps.core.testing import make_administrator, make_user

MATRIX = reverse("accounts:permission_matrix")


def current_ticks():
    """The matrix form as the page submits it: every editable role's ticks."""
    managed = {p.pk for p in managed_permissions()}
    return {
        f"role-{role.pk}": [
            str(p.pk) for p in role.permissions.all() if p.pk in managed
        ]
        for role in Role.objects.exclude(key="administrator")
    }


class RoleCrudTests(TestCase):
    def setUp(self):
        self.client.force_login(make_administrator())

    def test_list_shows_roles_and_counts(self):
        make_user(roles=["finance"])
        response = self.client.get(reverse("accounts:role_list"))
        self.assertContains(response, "Finance")
        finance = next(r for r in response.context["object_list"] if r.key == "finance")
        self.assertEqual(finance.user_count, 1)

    def test_create_edit_delete(self):
        self.client.post(
            reverse("accounts:role_create"),
            {"name": "Ushers", "description": "Welcome people."},
        )
        role = Role.objects.get(name="Ushers")
        self.assertIsNone(role.key)

        self.client.post(
            reverse("accounts:role_update", kwargs={"pk": role.pk}),
            {"name": "Welcome Team", "description": "Welcome people."},
        )
        role.refresh_from_db()
        self.assertEqual(role.name, "Welcome Team")

        response = self.client.post(
            reverse("accounts:role_delete", kwargs={"pk": role.pk})
        )
        self.assertRedirects(response, reverse("accounts:role_list"))
        self.assertFalse(Role.objects.filter(pk=role.pk).exists())
        self.assertEqual(
            list(AuditEvent.objects.values_list("action", flat=True).order_by("pk")),
            ["created", "changed", "deleted"],
        )
        deleted = AuditEvent.objects.get(action="deleted")
        self.assertEqual(deleted.changes["Name"], ["Welcome Team", ""])

    def test_administrator_role_cannot_be_deleted(self):
        administrator = Role.objects.get(key="administrator")
        url = reverse("accounts:role_delete", kwargs={"pk": administrator.pk})
        self.assertEqual(self.client.post(url).status_code, 403)
        self.assertTrue(Role.objects.filter(pk=administrator.pk).exists())


class PermissionMatrixTests(TestCase):
    def setUp(self):
        self.finance = Role.objects.get(key="finance")
        self.view_audit = Permission.objects.get(codename="view_auditevent")

    def test_viewer_sees_matrix_but_cannot_save(self):
        self.client.force_login(make_user(perms=["accounts.view_role"]))
        response = self.client.get(MATRIX)
        self.assertContains(response, "Can view audit event")
        self.assertNotContains(response, "Save permissions")
        response = self.client.post(MATRIX, {f"role-{self.finance.pk}": [1]})
        self.assertEqual(response.status_code, 403)

    def test_saves_role_permissions_and_audits(self):
        self.client.force_login(make_administrator())
        before = set(self.finance.permissions.all())
        ticks = current_ticks()
        ticks[f"role-{self.finance.pk}"].append(str(self.view_audit.pk))
        response = self.client.post(MATRIX, ticks)
        self.assertRedirects(response, MATRIX)
        self.assertEqual(
            set(self.finance.permissions.all()), before | {self.view_audit}
        )
        event = AuditEvent.objects.get()  # only the changed role is recorded
        self.assertEqual(event.object_repr, "Finance")
        self.assertIn("Can view audit event", event.changes["Permissions"][1])

    def test_ignores_unmanaged_permissions_and_administrator_column(self):
        self.client.force_login(make_administrator())
        administrator = Role.objects.get(key="administrator")
        session_perm = Permission.objects.get(codename="view_session")
        before = set(self.finance.permissions.all())
        ticks = current_ticks()
        ticks[f"role-{self.finance.pk}"] += [str(session_perm.pk), "junk"]
        # No Administrator ticks are sent; its permissions must stay.
        self.client.post(MATRIX, ticks)
        self.assertEqual(set(self.finance.permissions.all()), before)
        self.assertEqual(
            administrator.permissions.count(), managed_permissions().count()
        )
