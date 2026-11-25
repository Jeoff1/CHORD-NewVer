from django.contrib.auth.models import AnonymousUser
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase

from apps.audit.models import AuditEvent
from apps.audit.services import diff, display_value, record_change, snapshot
from apps.core.testing import first_church, make_user


class DisplayValueTests(TestCase):
    def test_values_become_short_strings(self):
        profile = first_church()
        self.assertEqual(display_value(None), "")
        self.assertEqual(display_value(True), "Yes")
        self.assertEqual(display_value(False), "No")
        self.assertEqual(display_value(["b", "a"]), "a, b")
        self.assertEqual(display_value({"k": True}), "k: Yes")
        self.assertEqual(display_value(profile.logo), "")  # empty file field
        self.assertEqual(display_value(12), "12")


class SnapshotAndDiffTests(TestCase):
    def test_snapshot_uses_verbose_names_for_plain_field_lists(self):
        user = make_user(first_name="Ana")
        self.assertEqual(snapshot(user, ["first_name"]), {"First name": "Ana"})

    def test_snapshot_accepts_callables(self):
        user = make_user(first_name="Ana")
        values = snapshot(user, {"Shout": lambda u: u.first_name.upper()})
        self.assertEqual(values, {"Shout": "ANA"})

    def test_diff_covers_create_change_and_delete(self):
        self.assertEqual(diff({}, {"Name": "A"}), {"Name": ["", "A"]})
        self.assertEqual(
            diff({"Name": "A", "Email": "x"}, {"Name": "B", "Email": "x"}),
            {"Name": ["A", "B"]},
        )
        self.assertEqual(diff({"Name": "A"}, {}), {"Name": ["A", ""]})


class RecordChangeTests(TestCase):
    def test_records_actor_object_and_changes(self):
        actor = make_user()
        target = make_user(username="target")
        event = record_change(
            actor, target, AuditEvent.Action.CHANGED, {"Email": ["a", "b"]}
        )
        self.assertEqual(event.actor, actor)
        self.assertEqual(event.object_id, str(target.pk))
        self.assertEqual(event.object_repr, "target")
        self.assertEqual(event.content_type, ContentType.objects.get_for_model(target))
        self.assertEqual(event.changes, {"Email": ["a", "b"]})

    def test_change_without_edits_is_not_recorded(self):
        result = record_change(make_user(), make_user(), AuditEvent.Action.CHANGED, {})
        self.assertIsNone(result)
        self.assertFalse(AuditEvent.objects.exists())

    def test_anonymous_actor_is_stored_as_system(self):
        event = record_change(AnonymousUser(), make_user(), AuditEvent.Action.CREATED)
        self.assertIsNone(event.actor)
