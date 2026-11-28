"""Teams is on for the churches where it was locked (28 Nov 2026).

While Teams was locked (Phase 9B, §5), saving a church's Modules page wrote
"teams" into its switched-off Modules although the church never chose
that: it had no switch. Every Module starts switched on, so those churches
get Teams on now. The church that could already use Teams keeps its own
choice.
"""

from django.db import migrations


def forwards(apps, schema_editor):
    ChurchProfile = apps.get_model("church", "ChurchProfile")
    for church in ChurchProfile.objects.filter(members_teams_unlocked=False):
        if "teams" in church.disabled_modules:
            church.disabled_modules = [
                code for code in church.disabled_modules if code != "teams"
            ]
            church.save(update_fields=["disabled_modules"])


class Migration(migrations.Migration):
    dependencies = [
        ("church", "0005_churchprofile_banner"),
        ("teams", "0006_church_required"),
    ]

    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
