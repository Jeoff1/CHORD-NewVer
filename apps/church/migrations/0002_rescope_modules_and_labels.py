"""Drop the switches and Labels of Modules that left the project's scope.

Ministries, Events, Giving, Records and Services were never built, so they
hold no data; only their entries in the Church Profile are removed.
"""

from django.db import migrations

REMOVED_MODULES = {"ministries", "events", "giving", "records", "services"}
REMOVED_LABELS = {"ministry", "officiant", "service", "offering"}


def tidy_profile(apps, schema_editor):
    ChurchProfile = apps.get_model("church", "ChurchProfile")
    for profile in ChurchProfile.objects.all():
        profile.disabled_modules = [
            code for code in profile.disabled_modules if code not in REMOVED_MODULES
        ]
        profile.labels = {
            key: value
            for key, value in profile.labels.items()
            if key not in REMOVED_LABELS
        }
        profile.save(update_fields=["disabled_modules", "labels"])


class Migration(migrations.Migration):
    dependencies = [("church", "0001_initial")]

    operations = [migrations.RunPython(tidy_profile, migrations.RunPython.noop)]
