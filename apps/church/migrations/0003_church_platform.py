"""Phase 9B (decision 0014): many churches on one installation.

The single-row rule goes; each church gets a slug and the homepage and
directory settings. The church that existed before keeps every record and
is the only one allowed the Members and Teams Modules for now. A new
installation starts with one church, as before.
"""

from django.core.management.color import no_style
from django.db import migrations, models
from django.utils.text import slugify


def reset_sequence(schema_editor, model):
    # Rows saved with an explicit pk (the old pk=1 rule) never moved the
    # sequence, so the next new row would reuse an id.
    ops = schema_editor.connection.ops
    for sql in ops.sequence_reset_sql(no_style(), [model]):
        schema_editor.execute(sql)


def forwards(apps, schema_editor):
    ChurchProfile = apps.get_model("church", "ChurchProfile")
    if not ChurchProfile.objects.exists():
        ChurchProfile.objects.create(pk=1)
    taken = set()
    for church in ChurchProfile.objects.order_by("pk"):
        base = slugify(church.name)[:70] or "church"
        slug, n = base, 1
        while slug in taken:
            n += 1
            slug = f"{base}-{n}"
        taken.add(slug)
        church.slug = slug
        church.save(update_fields=["slug"])
    first = ChurchProfile.objects.order_by("pk").first()
    first.members_teams_unlocked = True
    first.save(update_fields=["members_teams_unlocked"])
    reset_sequence(schema_editor, ChurchProfile)


class Migration(migrations.Migration):
    dependencies = [("church", "0002_rescope_modules_and_labels")]

    operations = [
        migrations.RemoveConstraint(
            model_name="churchprofile", name="church_profile_single_row"
        ),
        migrations.AlterModelOptions(
            name="churchprofile",
            options={"default_permissions": ("change",), "ordering": ["pk"]},
        ),
        migrations.AddField(
            model_name="churchprofile",
            name="about",
            field=models.TextField(
                blank=True, help_text="Shown on the church's homepage."
            ),
        ),
        migrations.AddField(
            model_name="churchprofile",
            name="show_in_directory",
            field=models.BooleanField(
                default=True,
                help_text="List the church on the platform's public list of churches.",
                verbose_name="Show in the directory",
            ),
        ),
        migrations.AddField(
            model_name="churchprofile",
            name="show_upcoming_services",
            field=models.BooleanField(
                default=False,
                help_text="Show the next worship services on the homepage: "
                "date, time and kind only.",
                verbose_name="Show upcoming services",
            ),
        ),
        migrations.AddField(
            model_name="churchprofile",
            name="members_teams_unlocked",
            field=models.BooleanField(default=False, editable=False),
        ),
        migrations.AddField(
            model_name="churchprofile",
            name="slug",
            field=models.SlugField(
                db_index=False, default="", editable=False, max_length=80
            ),
            preserve_default=False,
        ),
        migrations.RunPython(forwards, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="churchprofile",
            name="slug",
            field=models.SlugField(
                editable=False,
                help_text="The church's address on the platform: /churches/<slug>/.",
                max_length=80,
                unique=True,
            ),
        ),
    ]
