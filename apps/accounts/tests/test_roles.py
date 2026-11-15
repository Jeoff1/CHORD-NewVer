from unittest import mock

from django.contrib.auth.models import Permission
from django.test import TestCase

from apps.accounts import roles
from apps.accounts.models import Role
from apps.core.testing import make_user


class DefaultRolesTests(TestCase):
    def test_default_roles_exist(self):
        self.assertEqual(
            set(Role.objects.values_list("key", flat=True)),
            {
                "administrator",
                "office_staff",
                "finance",
                "records_keeper",
                "worship_leader",
                "ministry_leader",
            },
        )

    def test_administrator_has_every_managed_permission(self):
        administrator = Role.objects.get(key=roles.ADMINISTRATOR)
        self.assertEqual(
            set(administrator.permissions.all()), set(roles.managed_permissions())
        )

    def test_managed_permissions_are_only_declared_chord_permissions(self):
        names = {
            f"{p.content_type.app_label}.{p.codename}"
            for p in roles.managed_permissions()
        }
        self.assertIn("church.change_churchprofile", names)
        self.assertIn("audit.view_auditevent", names)
        self.assertIn("accounts.add_user", names)
        # Users are deactivated, never deleted; framework tables aren't shown.
        self.assertNotIn("accounts.delete_user", names)
        self.assertNotIn("sessions.view_session", names)
        self.assertNotIn("church.add_churchprofile", names)


class SyncDefaultPermissionsTests(TestCase):
    def test_default_permission_is_granted_once(self):
        finance = Role.objects.get(key="finance")
        perm = Permission.objects.get(codename="view_auditevent")
        defaults = {"finance": ["audit.view_auditevent"]}
        with mock.patch.dict(roles.DEFAULT_ROLE_PERMISSIONS, defaults, clear=True):
            roles.sync_default_role_permissions()
            self.assertIn(perm, finance.permissions.all())

            # The church removes it; a later sync must not grant it again.
            finance.permissions.remove(perm)
            roles.sync_default_role_permissions()
            self.assertNotIn(perm, finance.permissions.all())

    def test_administrator_regains_any_removed_permission(self):
        administrator = Role.objects.get(key=roles.ADMINISTRATOR)
        administrator.permissions.clear()
        roles.sync_default_role_permissions()
        self.assertEqual(
            administrator.permissions.count(), roles.managed_permissions().count()
        )


class AdministratorTests(TestCase):
    def test_who_counts_as_administrator(self):
        holder = make_user(roles=["administrator"])
        superuser = make_user(is_superuser=True)
        inactive = make_user(roles=["administrator"], is_active=False)
        plain = make_user(roles=["finance"])
        self.assertTrue(roles.is_administrator(holder))
        self.assertTrue(roles.is_administrator(superuser))
        self.assertFalse(roles.is_administrator(inactive))
        self.assertFalse(roles.is_administrator(plain))

    def test_role_permissions_reach_the_user(self):
        user = make_user(roles=["administrator"])
        self.assertTrue(user.has_perm("church.change_churchprofile"))
        self.assertFalse(make_user(roles=["finance"]).has_perm("accounts.view_user"))
