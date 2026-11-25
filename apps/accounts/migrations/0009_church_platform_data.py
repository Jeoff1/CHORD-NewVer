"""Phase 9B (decision 0014), step 2 of 3: the church that existed before
keeps every role, and every user, active or not, gets a Membership there
with exactly the roles they held. ``user.groups`` is left as it was, unused
from now on, so this can be reversed."""

from django.db import migrations


def forwards(apps, schema_editor):
    ChurchProfile = apps.get_model("church", "ChurchProfile")
    Role = apps.get_model("accounts", "Role")
    User = apps.get_model("accounts", "User")
    Membership = apps.get_model("accounts", "Membership")
    church = ChurchProfile.objects.order_by("pk").first()
    for role in Role.objects.all():
        role.church = church
        role.title = role.name
        role.name = f"{church.pk}:{role.name}"
        role.save(update_fields=["church", "title", "name"])
    for user in User.objects.all():
        membership = Membership.objects.create(user=user, church=church)
        membership.roles.set(Role.objects.filter(group_ptr__user=user))


def backwards(apps, schema_editor):
    Role = apps.get_model("accounts", "Role")
    apps.get_model("accounts", "Membership").objects.all().delete()
    for role in Role.objects.all():
        role.name = role.title
        role.save(update_fields=["name"])


class Migration(migrations.Migration):
    dependencies = [("accounts", "0008_church_platform_schema")]

    operations = [migrations.RunPython(forwards, backwards)]
