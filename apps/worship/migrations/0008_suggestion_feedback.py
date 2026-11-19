"""Suggestion Feedback (Phase 6, part B), the song usage report permission,
and each lineup's suggestion outcomes."""

import django.db.models.deletion
from django.db import migrations, models


def backfill_outcomes(apps, schema_editor):
    """Lineups made before feedback was followed: each placed suggestion of
    their run whose song is still in the lineup counts as kept."""
    Lineup = apps.get_model("worship", "Lineup")
    Suggestion = apps.get_model("worship", "Suggestion")
    for lineup in Lineup.objects.exclude(run=None):
        songs = set(lineup.items.values_list("song_id", flat=True))
        placed = Suggestion.objects.filter(
            run_id=lineup.run_id, slot__isnull=False, song_id__in=songs
        )
        lineup.suggestion_outcomes = {str(s.pk): "kept" for s in placed}
        lineup.save(update_fields=["suggestion_outcomes"])


class Migration(migrations.Migration):
    dependencies = [
        ("songs", "0004_smoke_test_fixes"),
        ("worship", "0007_lineup_reason_text"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="lineup",
            options={
                "default_permissions": ("add", "change", "view"),
                "permissions": [
                    ("finalize_lineup", "Can have the final say on lineups"),
                    ("view_song_usage", "Can see the song usage report"),
                ],
            },
        ),
        migrations.AddField(
            model_name="lineup",
            name="suggestion_outcomes",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.CreateModel(
            name="SuggestionFeedback",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "label",
                    models.CharField(
                        choices=[
                            ("kept", "Kept"),
                            ("swapped", "Swapped"),
                            ("removed", "Removed"),
                        ],
                        max_length=10,
                    ),
                ),
                ("recorded_at", models.DateTimeField()),
                (
                    "rank",
                    models.PositiveSmallIntegerField(help_text="Its rank in the run."),
                ),
                ("relevance", models.FloatField()),
                ("match", models.FloatField(blank=True, null=True)),
                (
                    "worship_model_score",
                    models.FloatField(
                        blank=True,
                        help_text="The model's score, from the lyrics alone.",
                        null=True,
                    ),
                ),
                ("familiarity", models.FloatField()),
                ("season", models.FloatField()),
                ("recency", models.FloatField()),
                ("team_knows", models.BooleanField()),
                (
                    "slot_feel",
                    models.CharField(
                        blank=True,
                        help_text="The feel of the slot it was placed in.",
                        max_length=10,
                    ),
                ),
                (
                    "lineup",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="feedback",
                        to="worship.lineup",
                    ),
                ),
                (
                    "run",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="+",
                        to="worship.searchrun",
                    ),
                ),
                (
                    "song",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="+",
                        to="songs.song",
                    ),
                ),
            ],
            options={
                "ordering": ["lineup", "rank"],
                "default_permissions": (),
                "constraints": [
                    models.UniqueConstraint(
                        fields=("lineup", "song"),
                        name="one_feedback_per_song_per_lineup",
                    )
                ],
            },
        ),
        migrations.RunPython(backfill_outcomes, migrations.RunPython.noop),
    ]
