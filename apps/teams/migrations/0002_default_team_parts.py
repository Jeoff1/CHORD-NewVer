"""Neutral starting Team Parts. The church renames them, switches them off
or adds its own."""

from django.db import migrations

PARTS = [
    "Vocals",
    "Acoustic guitar",
    "Electric guitar",
    "Bass",
    "Keys",
    "Drums",
]


def create(apps, schema_editor):
    TeamPart = apps.get_model("teams", "TeamPart")
    if TeamPart.objects.exists():
        return
    for order, name in enumerate(PARTS, start=1):
        TeamPart.objects.create(name=name, sort_order=order * 10)


def remove(apps, schema_editor):
    apps.get_model("teams", "TeamPart").objects.filter(
        name__in=PARTS, assignments__isnull=True, profiles__isnull=True
    ).delete()


class Migration(migrations.Migration):
    dependencies = [("teams", "0001_initial")]

    operations = [migrations.RunPython(create, remove)]
