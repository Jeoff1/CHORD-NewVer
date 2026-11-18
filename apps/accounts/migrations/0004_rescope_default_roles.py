"""Default roles for worship planning.

Adds Pastoral Staff and Team Member. Finance, Records Keeper and Ministry
Leader belonged to Modules that left the project's scope; each is removed
only when no user holds it, so a church that put one to use keeps it.
"""

from django.db import migrations

NEW_ROLES = [
    (
        "pastoral_staff",
        "Pastoral Staff",
        "Schedules worship services, posts each service's theme, and has the "
        "final say on its lineup.",
    ),
    (
        "team_member",
        "Team Member",
        "Sees confirmed lineups and song pages, and marks their own availability.",
    ),
]
OBSOLETE_ROLES = [
    ("finance", "Finance", "Records giving and service fees."),
    (
        "records_keeper",
        "Records Keeper",
        "Keeps the church's official records and certificates.",
    ),
    ("ministry_leader", "Ministry Leader", "Leads a ministry and its events."),
]
# key -> (description before, description after); changed only if unedited.
DESCRIPTIONS = {
    "office_staff": (
        "Day-to-day office work, such as members, events and service requests.",
        "Day-to-day office work, such as keeping the member directory.",
    ),
    "worship_leader": (
        "Plans worship and manages songs and teams.",
        "Builds and confirms lineups, and manages songs, chord sheets and teams.",
    ),
}


def forwards(apps, schema_editor):
    Role = apps.get_model("accounts", "Role")
    User = apps.get_model("accounts", "User")
    for key, name, description in NEW_ROLES:
        if not Role.objects.filter(key=key).exists():
            Role.objects.create(key=key, name=name, description=description)
    for key, _, _ in OBSOLETE_ROLES:
        role = Role.objects.filter(key=key).first()
        if role and not User.objects.filter(groups=role.pk).exists():
            role.delete()
    for key, (before, after) in DESCRIPTIONS.items():
        Role.objects.filter(key=key, description=before).update(description=after)


def backwards(apps, schema_editor):
    Role = apps.get_model("accounts", "Role")
    User = apps.get_model("accounts", "User")
    for key, name, description in OBSOLETE_ROLES:
        if not Role.objects.filter(key=key).exists():
            Role.objects.create(key=key, name=name, description=description)
    for key, _, _ in NEW_ROLES:
        role = Role.objects.filter(key=key).first()
        if role and not User.objects.filter(groups=role.pk).exists():
            role.delete()
    for key, (before, after) in DESCRIPTIONS.items():
        Role.objects.filter(key=key, description=after).update(description=before)


class Migration(migrations.Migration):
    dependencies = [("accounts", "0003_seed_default_roles")]

    operations = [migrations.RunPython(forwards, backwards)]
