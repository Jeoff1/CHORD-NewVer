from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import Role, User
from apps.audit.models import AuditEvent
from apps.core.testing import TEST_PASSWORD, make_administrator, make_user


def edit_data(user, **overrides):
    data = {
        "username": user.username,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "email": user.email,
        "is_active": "on" if user.is_active else "",
        "roles": [role.pk for role in user.roles],
    }
    data.update(overrides)
    return {key: value for key, value in data.items() if value != ""}


class UserPagesPermissionTests(TestCase):
    def test_plain_user_is_refused(self):
        self.client.force_login(make_user())
        target = make_user()
        for url in (
            reverse("accounts:user_list"),
            reverse("accounts:user_create"),
            reverse("accounts:user_update", kwargs={"pk": target.pk}),
            reverse("accounts:user_password", kwargs={"pk": target.pk}),
        ):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 403)

    def test_view_permission_alone_shows_the_list_without_edit_buttons(self):
        self.client.force_login(make_user(perms=["accounts.view_user"]))
        response = self.client.get(reverse("accounts:user_list"))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Add user")


class UserListTests(TestCase):
    def setUp(self):
        self.admin = make_administrator(username="boss")
        self.client.force_login(self.admin)
        make_user(username="ana", first_name="Ana")
        make_user(username="ben", is_active=False)

    def usernames(self, **params):
        response = self.client.get(reverse("accounts:user_list"), params)
        return [u.username for u in response.context["object_list"]]

    def test_status_filter(self):
        self.assertEqual(self.usernames(), ["ana", "boss"])
        self.assertEqual(self.usernames(status="inactive"), ["ben"])
        self.assertEqual(self.usernames(status="all"), ["ana", "ben", "boss"])

    def test_search(self):
        self.assertEqual(self.usernames(q="Ana"), ["ana"])


class UserCreateTests(TestCase):
    def test_creates_user_with_roles_and_audits(self):
        admin = make_administrator()
        self.client.force_login(admin)
        finance = Role.objects.get(key="finance")
        response = self.client.post(
            reverse("accounts:user_create"),
            {
                "username": "treasurer",
                "first_name": "Tess",
                "last_name": "Cruz",
                "email": "tess@example.com",
                "password1": TEST_PASSWORD,
                "password2": TEST_PASSWORD,
                "roles": [finance.pk],
            },
        )
        self.assertRedirects(response, reverse("accounts:user_list"))
        user = User.objects.get(username="treasurer")
        self.assertEqual(list(user.roles), [finance])
        self.assertTrue(user.check_password(TEST_PASSWORD))
        event = AuditEvent.objects.get(action=AuditEvent.Action.CREATED)
        self.assertEqual(event.changes["Roles"], ["", "Finance"])
        self.assertNotIn("Password", event.changes)


class UserUpdateTests(TestCase):
    def setUp(self):
        self.admin = make_administrator()
        self.client.force_login(self.admin)

    def url(self, user):
        return reverse("accounts:user_update", kwargs={"pk": user.pk})

    def test_changes_roles_and_keeps_plain_groups(self):
        other_group = Group.objects.create(name="Legacy group")
        user = make_user(roles=["finance"])
        user.groups.add(other_group)
        office = Role.objects.get(key="office_staff")
        response = self.client.post(self.url(user), edit_data(user, roles=[office.pk]))
        self.assertRedirects(response, reverse("accounts:user_list"))
        self.assertEqual(list(user.roles), [office])
        self.assertIn(other_group, user.groups.all())
        event = AuditEvent.objects.get()
        self.assertEqual(event.changes["Roles"], ["Finance", "Office Staff"])

    def test_deactivates_another_user(self):
        user = make_user()
        self.client.post(self.url(user), edit_data(user, is_active=""))
        user.refresh_from_db()
        self.assertFalse(user.is_active)

    def test_cannot_deactivate_self(self):
        make_administrator()  # so the last-administrator rule isn't the reason
        response = self.client.post(
            self.url(self.admin), edit_data(self.admin, is_active="")
        )
        self.assertContains(response, "deactivate your own account")
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_active)

    def test_last_administrator_keeps_the_role(self):
        response = self.client.post(
            self.url(self.admin), edit_data(self.admin, roles=[])
        )
        self.assertContains(response, "only active administrator")
        self.assertEqual(list(self.admin.roles)[0].key, "administrator")

    def test_administrator_role_can_move_when_another_exists(self):
        make_administrator()
        response = self.client.post(
            self.url(self.admin), edit_data(self.admin, roles=[])
        )
        # The editor just gave up their own access, so don't follow the redirect.
        self.assertRedirects(
            response, reverse("accounts:user_list"), fetch_redirect_response=False
        )
        self.assertEqual(list(self.admin.roles), [])


class UserSetPasswordTests(TestCase):
    def test_sets_password_without_logging_it(self):
        admin = make_administrator()
        self.client.force_login(admin)
        user = make_user()
        response = self.client.post(
            reverse("accounts:user_password", kwargs={"pk": user.pk}),
            {
                "new_password1": "Another-pass-9911",
                "new_password2": "Another-pass-9911",
            },
        )
        self.assertRedirects(response, reverse("accounts:user_list"))
        user.refresh_from_db()
        self.assertTrue(user.check_password("Another-pass-9911"))
        event = AuditEvent.objects.get()
        self.assertNotIn("Another-pass-9911", str(event.changes))
