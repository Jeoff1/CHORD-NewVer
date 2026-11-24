"""Notifications move out of Teams into the core ``notifications`` app
(Phase 9A, A5), so they work whichever Modules are switched on.

The table is renamed, never copied, so every Notification is kept;
``notifications/0001_initial`` takes the model over.
"""

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("teams", "0003_notification_swaprequest")]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.AlterModelTable(
                    name="notification", table="notifications_notification"
                ),
            ],
            state_operations=[migrations.DeleteModel(name="Notification")],
        ),
    ]
