"""Teams' records belong to a church (28 Nov 2026, decision 0014).

Team Parts, Team Profiles and Blackout Dates get a church. Every existing
row goes to the first church, the only one that could use Teams before
(the one with ``members_teams_unlocked``); migration 0006 moves them if
that is another church and gives every other church the starting Team
Parts.
"""

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

import apps.church.models


class Migration(migrations.Migration):
    dependencies = [
        ("church", "0005_churchprofile_banner"),
        ("teams", "0004_move_notification_out"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="teampart",
            name="church",
            field=models.ForeignKey(
                default=apps.church.models.first_church_id,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="+",
                to="church.churchprofile",
            ),
        ),
        migrations.AlterField(
            model_name="teampart",
            name="name",
            field=models.CharField(max_length=100),
        ),
        migrations.AddConstraint(
            model_name="teampart",
            constraint=models.UniqueConstraint(
                fields=("church", "name"),
                name="teams_teampart_name_per_church",
                violation_error_message="An item with this name already exists.",
            ),
        ),
        migrations.AddField(
            model_name="teamprofile",
            name="church",
            field=models.ForeignKey(
                default=apps.church.models.first_church_id,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="+",
                to="church.churchprofile",
            ),
        ),
        migrations.AlterField(
            model_name="teamprofile",
            name="user",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="team_profiles",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddConstraint(
            model_name="teamprofile",
            constraint=models.UniqueConstraint(
                fields=("church", "user"), name="one_team_profile_per_church"
            ),
        ),
        migrations.AddField(
            model_name="blackoutdate",
            name="church",
            field=models.ForeignKey(
                default=apps.church.models.first_church_id,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="+",
                to="church.churchprofile",
            ),
        ),
    ]
