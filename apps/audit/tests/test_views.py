from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from django.urls import reverse

from apps.audit.models import AuditEvent
from apps.audit.services import record_change
from apps.church.models import ChurchProfile
from apps.core.testing import make_administrator, make_user

URL = reverse("audit:log")


class AuditLogViewTests(TestCase):
    def setUp(self):
        self.admin = make_administrator(username="boss")
        record_change(self.admin, make_user(username="ana"), AuditEvent.Action.CREATED)
        record_change(
            self.admin,
            ChurchProfile.load(),
            AuditEvent.Action.CHANGED,
            {"Church name": ["Old", "New"]},
        )

    def test_requires_permission(self):
        self.client.force_login(make_user())
        self.assertEqual(self.client.get(URL).status_code, 403)

    def test_lists_events_with_changes(self):
        self.client.force_login(self.admin)
        response = self.client.get(URL)
        self.assertContains(response, "ana")
        self.assertContains(response, "Church name:")
        self.assertContains(response, "New")

    def test_filters_by_type(self):
        self.client.force_login(self.admin)
        profile_type = ContentType.objects.get_for_model(ChurchProfile)
        response = self.client.get(URL, {"type": profile_type.pk})
        self.assertEqual(
            [e.object_repr for e in response.context["object_list"]], ["My Church"]
        )

    def test_search(self):
        self.client.force_login(self.admin)
        response = self.client.get(URL, {"q": "ana"})
        self.assertEqual(
            [e.object_repr for e in response.context["object_list"]], ["ana"]
        )
