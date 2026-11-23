from django.apps import AppConfig


class TeamsConfig(AppConfig):
    """Teams: Team Parts, Team Profiles, Assignments, Blackout Dates, Swap
    Requests and Notifications."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.teams"
    verbose_name = "Teams"

    def ready(self):
        from apps.worship.signals import lineup_changed

        from .notifying import on_lineup_changed

        lineup_changed.connect(on_lineup_changed, dispatch_uid="teams_notify_lineup")
