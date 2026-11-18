"""Neutral starting entries for the church-edited lists. The church renames,
reorders or switches them off as it likes."""

from django.db import migrations

STATUSES = [
    # name, counts as active, description
    ("Member", True, "Belongs to the church."),
    ("Regular Attendee", True, "Attends regularly but isn't a member."),
    ("Visitor", True, "Has visited the church."),
    ("Inactive", False, "No longer takes part."),
    ("Moved Away", False, "Moved to another place."),
    ("Deceased", False, ""),
]
RELATIONSHIPS = ["Head", "Spouse", "Child", "Other"]


def create(apps, schema_editor):
    MembershipStatus = apps.get_model("members", "MembershipStatus")
    RelationshipType = apps.get_model("members", "RelationshipType")
    for order, (name, active, description) in enumerate(STATUSES, start=1):
        MembershipStatus.objects.get_or_create(
            name=name,
            defaults={
                "counts_as_active": active,
                "description": description,
                "sort_order": order * 10,
            },
        )
    for order, name in enumerate(RELATIONSHIPS, start=1):
        RelationshipType.objects.get_or_create(
            name=name, defaults={"sort_order": order * 10}
        )


def remove(apps, schema_editor):
    apps.get_model("members", "MembershipStatus").objects.filter(
        name__in=[name for name, _, _ in STATUSES], members__isnull=True
    ).delete()
    apps.get_model("members", "RelationshipType").objects.filter(
        name__in=RELATIONSHIPS
    ).delete()


class Migration(migrations.Migration):
    dependencies = [("members", "0001_initial")]

    operations = [migrations.RunPython(create, remove)]
