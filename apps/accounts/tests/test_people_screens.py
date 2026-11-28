"""UI/UX Phase 8 (28 Nov 2026): Users, Roles and permissions, and the Audit log. UI-UX-Master-Plan.md
§14. Initials only (personal pictures were rejected by the lead developer)."""

from django.test import TestCase
from django.urls import reverse

from apps.core.testing import complete_setup, make_administrator


class PeopleScreenTests(TestCase):
    def setUp(self):
        complete_setup()
        self.admin = make_administrator(first_name="Ruth", last_name="Cole")
        self.client.force_login(self.admin)

    def test_users_have_initials_role_chips_and_status_pills(self):
        page = self.client.get(reverse("accounts:user_list"))
        self.assertContains(page, '<ul class="chord-seg">')
        self.assertContains(page, 'aria-current="page">Active</a>')
        self.assertContains(page, ">RC</span>")
        self.assertContains(
            page, '<span class="chord-pill chord-pill--success">Active</span>'
        )
        self.assertContains(
            page,
            f'data-href="{reverse("accounts:user_update", kwargs={"pk": self.admin.pk})}"',
        )
        self.assertNotContains(page, "badge text-bg")

    def test_no_user_found_is_an_empty_state(self):
        page = self.client.get(reverse("accounts:user_list"), {"q": "zzzz"})
        self.assertContains(page, "chord-empty")
        self.assertContains(page, "No users found.")

    def test_roles_mark_full_access(self):
        page = self.client.get(reverse("accounts:role_list"))
        self.assertContains(page, 'chord-pill--accent fw-normal">Full access')
        self.assertContains(page, "chord-page-header")

    def test_the_matrix_has_sticky_sections(self):
        page = self.client.get(reverse("accounts:permission_matrix"))
        self.assertContains(page, "chord-matrix")
        self.assertContains(page, "chord-matrix__section")

    def test_the_audit_log_shows_changes_as_before_and_after(self):
        page = self.client.get(reverse("audit:log"))
        self.assertContains(page, "chord-page-header")
        self.assertContains(page, "Audit log")
