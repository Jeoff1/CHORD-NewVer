from django.apps import AppConfig


class AnnouncementsConfig(AppConfig):
    """Announcements: notes to everyone, or to one service's team."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.announcements"
    verbose_name = "Announcements"

    def ready(self):
        from apps.church import dashboard as church_dashboard

        from .dashboard import latest

        # The dashboard's side column (Phase 9A, A7).
        church_dashboard.register_panel(latest, order=20)
