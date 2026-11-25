"""The Active switch on church-edited lists: tick to switch an item on or
off straight from the list, shown here on Occasion Types."""

from django.test import TestCase
from django.urls import reverse

from apps.audit.models import AuditEvent
from apps.core.testing import (
    complete_setup,
    make_administrator,
    make_occasion_type,
    make_user,
)

LIST_URL = "occasions:types_list"


def switch_url(item):
    return reverse("occasions:types_switch", kwargs={"pk": item.pk})


class SettingSwitchTests(TestCase):
    def setUp(self):
        complete_setup()
        self.item = make_occasion_type(name="Garden wedding")
        self.admin = make_administrator()

    def test_list_shows_a_switch_to_people_who_may_change(self):
        self.client.force_login(self.admin)
        page = self.client.get(reverse(LIST_URL))
        self.assertContains(page, f'action="{switch_url(self.item)}"')
        self.assertContains(page, 'role="switch"')

    def test_viewer_sees_yes_or_no_without_a_switch(self):
        self.client.force_login(make_user(perms=["occasions.view_occasiontype"]))
        page = self.client.get(reverse(LIST_URL))
        self.assertNotContains(page, 'role="switch"')
        self.assertContains(page, "Yes")
        self.assertEqual(self.client.post(switch_url(self.item)).status_code, 403)
        self.item.refresh_from_db()
        self.assertTrue(self.item.is_active)

    def test_switching_off_with_htmx_returns_the_switch_and_audits(self):
        self.client.force_login(self.admin)
        response = self.client.post(switch_url(self.item), HTTP_HX_REQUEST="true")
        self.assertContains(response, 'role="switch"')
        self.assertNotContains(response, "checked")
        self.assertContains(response, "Off")
        self.item.refresh_from_db()
        self.assertFalse(self.item.is_active)
        event = AuditEvent.objects.get()
        self.assertEqual(event.action, AuditEvent.Action.CHANGED)
        self.assertEqual(event.changes, {"Active": ["Yes", "No"]})

    def test_switching_on_without_htmx_goes_back_to_the_list(self):
        self.item.is_active = False
        self.item.save()
        self.client.force_login(self.admin)
        response = self.client.post(switch_url(self.item), {"is_active": "on"})
        self.assertRedirects(response, reverse(LIST_URL))
        self.item.refresh_from_db()
        self.assertTrue(self.item.is_active)

    def test_asking_for_the_current_state_changes_nothing(self):
        self.client.force_login(self.admin)
        self.client.post(switch_url(self.item), {"is_active": "on"})
        self.item.refresh_from_db()
        self.assertTrue(self.item.is_active)
        self.assertFalse(AuditEvent.objects.exists())

    def test_post_only(self):
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(switch_url(self.item)).status_code, 405)

    def test_switched_off_module_hides_the_switch(self):
        complete_setup(disabled_modules=["occasions"])
        self.client.force_login(self.admin)
        self.assertEqual(self.client.post(switch_url(self.item)).status_code, 404)
