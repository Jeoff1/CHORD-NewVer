from django.apps import AppConfig


class OccasionsConfig(AppConfig):
    """Occasions: weddings, baptisms, funerals and other special services,
    kept apart from worship services (Phase 9A, A5; decision 0013)."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.occasions"
    verbose_name = "Occasions"

    def ready(self):
        from apps.core.settings_menu import SettingsPage, register
        from apps.worship import bookings

        from .rules import calendar_source

        # Occasions show on the Worship calendar; Worship never imports
        # this Module.
        bookings.register(calendar_source)
        register(
            SettingsPage(
                "teams_occasions",
                "Occasion types",
                "occasions:types_list",
                "occasions.view_occasiontype",
                "occasions",
                order=20,
            )
        )
