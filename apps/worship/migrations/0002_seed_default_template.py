"""A neutral starting service template. The church renames it, changes its
song slots, or adds templates of its own."""

from django.db import migrations

TEMPLATE_NAME = "Worship Service"
SLOTS = [
    # name, feel
    ("Opening", "upbeat"),
    ("Praise", "mid"),
    ("Worship", "slow"),
    ("Response", "slow"),
]


def create(apps, schema_editor):
    ServiceTemplate = apps.get_model("worship", "ServiceTemplate")
    TemplateSlot = apps.get_model("worship", "TemplateSlot")
    if ServiceTemplate.objects.exists():
        return
    template = ServiceTemplate.objects.create(
        name=TEMPLATE_NAME,
        description="The church's regular gathering for worship.",
        sort_order=10,
    )
    for order, (name, feel) in enumerate(SLOTS, start=1):
        TemplateSlot.objects.create(
            template=template, name=name, feel=feel, position=order * 10
        )


def remove(apps, schema_editor):
    apps.get_model("worship", "ServiceTemplate").objects.filter(
        name=TEMPLATE_NAME, services__isnull=True
    ).delete()


class Migration(migrations.Migration):
    dependencies = [("worship", "0001_initial")]

    operations = [migrations.RunPython(create, remove)]
