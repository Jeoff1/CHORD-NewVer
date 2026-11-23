from django.apps import AppConfig


class TeamsConfig(AppConfig):
    """Teams: Team Parts, Team Profiles, Assignments and Blackout Dates."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.teams"
    verbose_name = "Teams"
