"""Accounts for members, made in a batch (Phase 9A, A4; Design-Decisions,
"Adviser comments, 24 Nov")."""

import re
from urllib.parse import unquote

from django.core import mail
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import Role, User
from apps.audit.models import AuditEvent, SignInEvent
from apps.core.testing import (
    complete_setup,
    make_administrator,
    make_member,
    make_user,
)
from apps.members import accounts as member_accounts
from apps.members.models import Member

URL = reverse("members:accounts")


class BatchAccountsTests(TestCase):
    def setUp(self):
        complete_setup()
        self.admin = make_administrator()
        self.client.force_login(self.admin)
        self.rosa = make_member(
            first_name="Rosa", last_name="Lim", email="rosa@example.com"
        )
        self.ben = make_member(first_name="Ben", last_name="Cruz")
        self.church_member = Role.objects.get(key="church_member")

    def create(self, *members, role=None):
        return self.client.post(
            URL,
            {
                "members": [m.pk for m in members],
                "role": (role or self.church_member).pk,
            },
        )

    # --- The page ---------------------------------------------------------------

    def test_lists_only_current_members_without_an_account(self):
        archived = make_member(last_name="Archived")
        member_accounts.Member.objects.filter(pk=archived.pk).update(
            archived_at="2026-01-01T00:00Z"
        )
        linked = make_member(last_name="Linked", user=make_user())
        response = self.client.get(URL)
        self.assertEqual(response.status_code, 200)
        listed = set(response.context["candidates"])
        self.assertEqual(listed, {self.rosa, self.ben})
        self.assertNotIn(archived, listed)
        self.assertNotIn(linked, listed)
        self.assertEqual(
            response.context["form"]["role"].value(), self.church_member.pk
        )

    def test_search_narrows_the_list(self):
        response = self.client.get(URL, {"q": "Lim"})
        self.assertEqual(list(response.context["candidates"]), [self.rosa])

    def test_needs_both_permissions(self):
        for perms in (["members.view_member"], ["accounts.add_user"]):
            with self.subTest(perms):
                self.client.force_login(make_user(perms=perms))
                self.assertEqual(self.client.get(URL).status_code, 403)
                self.assertEqual(self.create(self.rosa).status_code, 403)
        self.assertFalse(User.objects.filter(username="rosa.lim").exists())

    def test_office_staff_without_add_user_get_no_button(self):
        self.client.force_login(make_user(roles=["office_staff"]))
        response = self.client.get(reverse("members:list"))
        self.assertNotContains(response, f'href="{URL}')
        self.client.force_login(self.admin)
        self.assertContains(self.client.get(reverse("members:list")), f'href="{URL}')

    def test_module_switched_off(self):
        complete_setup(disabled_modules=["members"])
        self.assertEqual(self.client.get(URL).status_code, 404)

    # --- Creating ---------------------------------------------------------------

    def test_creates_linked_accounts_with_the_role(self):
        response = self.create(self.rosa, self.ben)
        self.assertEqual(response.status_code, 200)
        rosa = User.objects.get(username="rosa.lim")
        self.assertEqual((rosa.first_name, rosa.last_name), ("Rosa", "Lim"))
        self.assertEqual(rosa.email, "rosa@example.com")
        self.assertEqual(list(rosa.roles), [self.church_member])
        self.assertTrue(rosa.must_change_password)
        self.rosa.refresh_from_db()
        self.assertEqual(self.rosa.user, rosa)
        self.assertTrue(User.objects.filter(username="ben.cruz").exists())

    def test_the_chosen_role_is_given(self):
        team = Role.objects.get(key="team_member")
        self.create(self.rosa, role=team)
        self.assertEqual(list(User.objects.get(username="rosa.lim").roles), [team])

    def test_usernames_stay_unique(self):
        twin = make_member(first_name="Rosa", last_name="Lim")
        self.create(self.rosa, twin)
        self.assertEqual(
            set(
                User.objects.filter(username__startswith="rosa.lim").values_list(
                    "username", flat=True
                )
            ),
            {"rosa.lim", "rosa.lim2"},
        )

    def test_temporary_password_is_shown_once_and_works(self):
        response = self.create(self.rosa)
        (row,) = response.context["created"]
        self.assertEqual(len(row.password), member_accounts.PASSWORD_LENGTH)
        self.assertContains(response, row.password)
        user = User.objects.get(username="rosa.lim")
        self.assertTrue(user.check_password(row.password))
        self.assertNotEqual(user.password, row.password)  # stored hashed
        self.assertIn("no-store", response["Cache-Control"])

    def test_password_never_reaches_the_audit_trail(self):
        response = self.create(self.rosa)
        (row,) = response.context["created"]
        events = AuditEvent.objects.all()
        self.assertEqual(
            {(e.content_type.model, e.action) for e in events},
            {("user", "created"), ("member", "changed")},
        )
        for event in events:
            self.assertNotIn(row.password, str(event.changes))
        member_event = events.get(content_type__model="member")
        self.assertEqual(member_event.changes["Linked account"], ["", "rosa.lim"])
        self.assertFalse(
            SignInEvent.objects.filter(username__contains=row.password).exists()
        )

    def test_csv_holds_the_accounts_and_is_formula_safe(self):
        tricky = make_member(first_name="=SUM(A1)", last_name="Test")
        response = self.create(self.rosa, tricky)
        href = response.context["csv_href"]
        self.assertTrue(href.startswith("data:text/csv;charset=utf-8,"))
        text = unquote(href.split(",", 1)[1])
        rosa_row = next(r for r in response.context["created"] if r.member == self.rosa)
        self.assertIn(f"Rosa Lim,rosa.lim,{rosa_row.password},", text)
        self.assertIn("'=SUM(A1) Test", text)
        self.assertIn("http://testserver/accounts/login/", text)

    def test_existing_accounts_and_archived_members_are_skipped(self):
        self.create(self.rosa)
        Member.objects.filter(pk=self.ben.pk).update(archived_at="2026-01-01T00:00Z")
        response = self.create(self.rosa, self.ben)
        self.assertEqual(response.context["created"], [])
        reasons = {row.member.pk: row.reason for row in response.context["skipped"]}
        self.assertEqual(
            reasons,
            {self.rosa.pk: "already has an account", self.ben.pk: "is archived"},
        )
        self.assertEqual(User.objects.filter(username__startswith="rosa").count(), 1)

    def test_nothing_ticked(self):
        response = self.client.post(URL, {"role": self.church_member.pk})
        self.assertContains(response, "Tick at least one person.")


class FirstSignInTests(TestCase):
    """A Temporary Password must be changed at first sign-in."""

    def setUp(self):
        complete_setup()
        member = make_member(first_name="Rosa", last_name="Lim")
        (row,), _ = member_accounts.create_accounts(
            Member.objects.filter(pk=member.pk),
            Role.objects.get(key="church_member"),
            make_administrator(),
        )
        self.user, self.password = row.user, row.password
        self.client.post(
            reverse("accounts:login"),
            {"username": self.user.username, "password": self.password},
        )

    def test_every_page_sends_them_to_change_password(self):
        for url in (
            reverse("home"),
            reverse("worship:home"),
            reverse("accounts:profile"),
        ):
            with self.subTest(url):
                self.assertRedirects(
                    self.client.get(url),
                    reverse("accounts:password_change"),
                    fetch_redirect_response=False,
                )
        page = self.client.get(reverse("accounts:password_change"))
        self.assertContains(page, "temporary password")

    def test_changing_it_lets_them_in(self):
        new = "a-new-Pass-2026!"
        self.client.post(
            reverse("accounts:password_change"),
            {"old_password": self.password, "new_password1": new, "new_password2": new},
        )
        self.user.refresh_from_db()
        self.assertFalse(self.user.must_change_password)
        self.assertEqual(self.client.get(reverse("home")).status_code, 200)

    def test_static_files_and_the_logo_still_load(self):
        for path in ("/static/vendor/htmx-2.0.4/htmx.min.js", "/media/church/logo.png"):
            with self.subTest(path):
                response = self.client.get(path)
                self.assertNotEqual(
                    response.get("Location"), reverse("accounts:password_change")
                )

    def test_resetting_the_password_by_email_also_counts(self):
        self.client.post(reverse("accounts:logout"))
        self.user.email = "rosa@example.com"
        self.user.save(update_fields=["email"])
        self.client.post(
            reverse("accounts:password_reset"), {"email": "rosa@example.com"}
        )
        link = re.search(r"http://testserver(\S+)", mail.outbox[0].body).group(1)
        page = self.client.get(link, follow=True)
        new = "a-new-Pass-2026!"
        self.client.post(
            page.redirect_chain[-1][0], {"new_password1": new, "new_password2": new}
        )
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(new))
        self.assertFalse(self.user.must_change_password)

    def test_they_can_still_sign_out(self):
        response = self.client.post(reverse("accounts:logout"))
        self.assertEqual(response.status_code, 302)
        self.assertNotEqual(response["Location"], reverse("accounts:password_change"))
