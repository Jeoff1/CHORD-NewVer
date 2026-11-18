from django.apps import AppConfig


class WorshipConfig(AppConfig):
    """Worship: services, their themes, song suggestions and lineups."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.worship"
    verbose_name = "Worship"
