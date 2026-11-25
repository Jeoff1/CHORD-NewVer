"""Phase 9B (decision 0014), step 3 of 3: every role belongs to a church,
and its name and key are unique within that church."""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("accounts", "0009_church_platform_data")]

    operations = [
        migrations.AlterField(
            model_name="role",
            name="church",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="roles",
                to="church.churchprofile",
            ),
        ),
        migrations.AlterModelOptions(name="role", options={"ordering": ["title"]}),
        migrations.AddConstraint(
            model_name="role",
            constraint=models.UniqueConstraint(
                fields=("church", "title"),
                name="role_title_unique_per_church",
                violation_error_message="This church already has a role with "
                "that name.",
            ),
        ),
        migrations.AddConstraint(
            model_name="role",
            constraint=models.UniqueConstraint(
                fields=("church", "key"), name="role_key_unique_per_church"
            ),
        ),
    ]
