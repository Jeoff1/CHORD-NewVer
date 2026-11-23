from django.apps import AppConfig


class AnnouncementsConfig(AppConfig):
    """Announcements: notes to everyone, or to one service's team."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.announcements"
    verbose_name = "Announcements"
