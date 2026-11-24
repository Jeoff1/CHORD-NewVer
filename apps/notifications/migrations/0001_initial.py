"""Notifications, moved here from Teams (Phase 9A, A5).

``teams/0004_move_notification_out`` renamed the table; this migration
only takes the model over, renames its index and moves its content type,
so every Notification is kept.
"""

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

OLD_INDEX = "teams_notif_recipie_55e9ee_idx"
NEW_INDEX = "notif_unread_idx"


def move_content_type(apps, schema_editor):
    ContentType = apps.get_model("contenttypes", "ContentType")
    ContentType.objects.filter(app_label="teams", model="notification").update(
        app_label="notifications"
    )


def move_content_type_back(apps, schema_editor):
    ContentType = apps.get_model("contenttypes", "ContentType")
    ContentType.objects.filter(app_label="notifications", model="notification").update(
        app_label="teams"
    )


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("contenttypes", "0002_remove_content_type_name"),
        ("teams", "0004_move_notification_out"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    f"ALTER INDEX {OLD_INDEX} RENAME TO {NEW_INDEX}",
                    f"ALTER INDEX {NEW_INDEX} RENAME TO {OLD_INDEX}",
                ),
            ],
            state_operations=[
                migrations.CreateModel(
                    name="Notification",
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
                        ("created_at", models.DateTimeField(auto_now_add=True)),
                        ("updated_at", models.DateTimeField(auto_now=True)),
                        ("text", models.CharField(max_length=300)),
                        ("url", models.CharField(blank=True, max_length=300)),
                        ("key", models.CharField(blank=True, max_length=100)),
                        ("read_at", models.DateTimeField(blank=True, null=True)),
                        (
                            "recipient",
                            models.ForeignKey(
                                on_delete=django.db.models.deletion.CASCADE,
                                related_name="notifications",
                                to=settings.AUTH_USER_MODEL,
                            ),
                        ),
                    ],
                    options={
                        "ordering": ["-created_at", "-pk"],
                        "default_permissions": (),
                        "indexes": [
                            models.Index(
                                fields=["recipient", "read_at"], name=NEW_INDEX
                            )
                        ],
                    },
                ),
            ],
        ),
        migrations.RunPython(move_content_type, move_content_type_back),
    ]
