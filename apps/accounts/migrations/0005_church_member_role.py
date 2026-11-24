"""The Church Member default role (adviser comments, 24 Nov; Phase 9A, A1).

For ordinary members who sign in: they see the schedule, announcements and
their own member record, never lineups or song pages. Its permissions come
from DEFAULT_ROLE_PERMISSIONS (apps/accounts/roles.py), like every default
role's. A church that already made its own role with this name keeps it,
and the default role is then not created.
"""

from django.db import migrations

KEY = "church_member"
NAME = "Church Member"
DESCRIPTION = (
    "Sees the schedule, announcements and their own member record. "
    "Doesn't see lineups, song pages or chord sheets."
)


def forwards(apps, schema_editor):
    Role = apps.get_model("accounts", "Role")
    Group = apps.get_model("auth", "Group")
    if (
        Role.objects.filter(key=KEY).exists()
        or Group.objects.filter(name=NAME).exists()
    ):
        return
    Role.objects.create(key=KEY, name=NAME, description=DESCRIPTION)


def backwards(apps, schema_editor):
    Role = apps.get_model("accounts", "Role")
    User = apps.get_model("accounts", "User")
    role = Role.objects.filter(key=KEY).first()
    if role and not User.objects.filter(groups=role.pk).exists():
        role.delete()


class Migration(migrations.Migration):
    dependencies = [("accounts", "0004_rescope_default_roles")]

    operations = [migrations.RunPython(forwards, backwards)]
