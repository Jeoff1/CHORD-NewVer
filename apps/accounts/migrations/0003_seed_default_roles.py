"""Create the default roles once. The church may rename or edit them later.

Permissions are granted after migrations by
``apps.accounts.roles.sync_default_role_permissions`` (post_migrate), because
permission rows don't exist yet while migrations run.
"""

from django.db import migrations

DEFAULT_ROLES = [
    ("administrator", "Administrator", "Full access to every part of CHORD."),
    (
        "office_staff",
        "Office Staff",
        "Day-to-day office work, such as members, events and service requests.",
    ),
    ("finance", "Finance", "Records giving and service fees."),
    (
        "records_keeper",
        "Records Keeper",
        "Keeps the church's official records and certificates.",
    ),
    (
        "worship_leader",
        "Worship Leader",
        "Plans worship and manages songs and teams.",
    ),
    ("ministry_leader", "Ministry Leader", "Leads a ministry and its events."),
]


def create_roles(apps, schema_editor):
    Role = apps.get_model("accounts", "Role")
    for key, name, description in DEFAULT_ROLES:
        if not Role.objects.filter(key=key).exists():
            Role.objects.create(key=key, name=name, description=description)


def remove_roles(apps, schema_editor):
    Role = apps.get_model("accounts", "Role")
    Role.objects.filter(key__in=[key for key, _, _ in DEFAULT_ROLES]).delete()


class Migration(migrations.Migration):
    dependencies = [("accounts", "0002_role_alter_user_options")]

    operations = [migrations.RunPython(create_roles, remove_roles)]
