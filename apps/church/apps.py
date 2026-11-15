from django.apps import AppConfig


class ChurchConfig(AppConfig):
    """Church Setup: the Church Profile, Modules, Labels and the dashboard."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.church"
    verbose_name = "Church Setup"
