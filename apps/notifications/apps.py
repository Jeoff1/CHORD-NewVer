from django.apps import AppConfig


class NotificationsConfig(AppConfig):
    """In-app Notifications: core, like Accounts, so they work whichever
    Modules the church switches on (Phase 9A, A5). Never email or SMS."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.notifications"
    verbose_name = "Notifications"
