"""Phase 9B (decision 0014), step 1 of 3: roles belong to a church, and
users hold them through a Membership."""

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0007_user_theme"),
        ("church", "0003_church_platform"),
    ]

    operations = [
        migrations.AddField(
            model_name="role",
            name="church",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="roles",
                to="church.churchprofile",
            ),
        ),
        migrations.AddField(
            model_name="role",
            name="title",
            field=models.CharField(default="", max_length=150, verbose_name="Name"),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name="role",
            name="key",
            field=models.SlugField(
                blank=True, editable=False, max_length=50, null=True
            ),
        ),
        migrations.CreateModel(
            name="Membership",
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
                ("is_active", models.BooleanField(default=True, verbose_name="Active")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "church",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="memberships",
                        to="church.churchprofile",
                    ),
                ),
                (
                    "roles",
                    models.ManyToManyField(
                        blank=True, related_name="memberships", to="accounts.role"
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="memberships",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["created_at", "pk"],
                "default_permissions": (),
                "constraints": [
                    models.UniqueConstraint(
                        fields=("user", "church"), name="one_membership_per_church"
                    )
                ],
            },
        ),
    ]
