"""Two example occasion templates, switched off (Phase 9A, A5; the owner's
choice, 2026-11-24). The church switches on the ones it holds, renames
them, changes their length and song slots, or adds its own occasions.

A template with the same name the church already made is left alone.
"""

from django.db import migrations

EXAMPLES = [
    # name, description, length in minutes, song slots (name, feel)
    (
        "Wedding",
        "An example occasion. Switch it on to let people request it.",
        120,
        [("Processional", "slow"), ("Worship", "mid"), ("Recessional", "upbeat")],
    ),
    (
        "Funeral",
        "An example occasion. Switch it on to let people request it.",
        90,
        [("Opening", "slow"), ("Comfort", "slow"), ("Closing", "slow")],
    ),
]


def create(apps, schema_editor):
    ServiceTemplate = apps.get_model("worship", "ServiceTemplate")
    TemplateSlot = apps.get_model("worship", "TemplateSlot")
    for order, (name, description, length, slots) in enumerate(EXAMPLES, start=1):
        if ServiceTemplate.objects.filter(name__iexact=name).exists():
            continue
        template = ServiceTemplate.objects.create(
            name=name,
            description=description,
            sort_order=100 + order * 10,
            is_active=False,
            is_occasion=True,
            length_minutes=length,
        )
        for position, (slot, feel) in enumerate(slots, start=1):
            TemplateSlot.objects.create(
                template=template, name=slot, feel=feel, position=position * 10
            )


def remove(apps, schema_editor):
    ServiceTemplate = apps.get_model("worship", "ServiceTemplate")
    ServiceTemplate.objects.filter(
        name__in=[name for name, *_ in EXAMPLES],
        is_occasion=True,
        services__isnull=True,
        occasion_requests__isnull=True,
    ).delete()


class Migration(migrations.Migration):
    dependencies = [("worship", "0012_occasions")]

    operations = [migrations.RunPython(create, remove)]
