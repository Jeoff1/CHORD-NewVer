"""Teams' existing records go to the church that used Teams, every other
church gets the starting Team Parts, and a church becomes required
(28 Nov 2026, decision 0014)."""

import django.db.models.deletion
from django.db import migrations, models

# The same starting parts as migration 0002 and ``apps/teams/defaults.py``.
PARTS = [
    "Vocals",
    "Acoustic guitar",
    "Electric guitar",
    "Bass",
    "Keys",
    "Drums",
]


def forwards(apps, schema_editor):
    ChurchProfile = apps.get_model("church", "ChurchProfile")
    TeamPart = apps.get_model("teams", "TeamPart")
    TeamProfile = apps.get_model("teams", "TeamProfile")
    BlackoutDate = apps.get_model("teams", "BlackoutDate")
    teams_church = (
        ChurchProfile.objects.filter(members_teams_unlocked=True).order_by("pk").first()
    )
    if teams_church is not None:
        for model in (TeamPart, TeamProfile, BlackoutDate):
            model.objects.exclude(church=teams_church).update(church=teams_church)
    for church in ChurchProfile.objects.all():
        if TeamPart.objects.filter(church=church).exists():
            continue
        for order, name in enumerate(PARTS, start=1):
            TeamPart.objects.create(church=church, name=name, sort_order=order * 10)


class Migration(migrations.Migration):
    dependencies = [
        ("church", "0005_churchprofile_banner"),
        ("teams", "0005_church_platform"),
    ]

    operations = [
        migrations.RunPython(forwards, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="teampart",
            name="church",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="+",
                to="church.churchprofile",
            ),
        ),
        migrations.AlterField(
            model_name="teamprofile",
            name="church",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="+",
                to="church.churchprofile",
            ),
        ),
        migrations.AlterField(
            model_name="blackoutdate",
            name="church",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="+",
                to="church.churchprofile",
            ),
        ),
    ]
