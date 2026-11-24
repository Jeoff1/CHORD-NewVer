"""Example Occasion Types, switched off (Phase 9A, A5; the owner's choice,
2026-11-24). The church switches on the ones it holds, renames them,
changes their usual length, or adds its own.

A type with the same name the church already made is left alone.
"""

from django.db import migrations

EXAMPLES = [
    # name, usual length in minutes
    ("Wedding", 120),
    ("Baptism", 60),
    ("Funeral", 90),
]
DESCRIPTION = "An example. Switch it on to let people request it."


def create(apps, schema_editor):
    OccasionType = apps.get_model("occasions", "OccasionType")
    for order, (name, length) in enumerate(EXAMPLES, start=1):
        if OccasionType.objects.filter(name__iexact=name).exists():
            continue
        OccasionType.objects.create(
            name=name,
            description=DESCRIPTION,
            length_minutes=length,
            sort_order=order * 10,
            is_active=False,
        )


def remove(apps, schema_editor):
    apps.get_model("occasions", "OccasionType").objects.filter(
        name__in=[name for name, _ in EXAMPLES],
        description=DESCRIPTION,
        occasions__isnull=True,
        requests__isnull=True,
    ).delete()


class Migration(migrations.Migration):
    dependencies = [("occasions", "0001_initial")]

    operations = [migrations.RunPython(create, remove)]
