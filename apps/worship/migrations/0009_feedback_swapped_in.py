"""Suggestion Feedback gets the label "swapped in": an alternative the
leader chose in a swap (decided 2026-11-19).

Nothing is backfilled. Lineups reviewed before this kept no record of
which "kept" songs came from a swap, so their outcomes stay "kept".
"""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("worship", "0008_suggestion_feedback"),
    ]

    operations = [
        migrations.AlterField(
            model_name="suggestionfeedback",
            name="label",
            field=models.CharField(
                choices=[
                    ("kept", "Kept"),
                    ("swapped_in", "Swapped in"),
                    ("swapped", "Swapped"),
                    ("removed", "Removed"),
                ],
                max_length=10,
            ),
        ),
    ]
