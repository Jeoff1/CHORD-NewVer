from django.apps import AppConfig


class CoreConfig(AppConfig):
    """Shared building blocks used by every CHORD module."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.core"
