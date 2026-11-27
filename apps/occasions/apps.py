from django.apps import AppConfig


class OccasionsConfig(AppConfig):
    """Occasions: weddings, baptisms, funerals and other special services,
    kept apart from worship services (Phase 9A, A5; decision 0013)."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.occasions"
    verbose_name = "Occasions"

    def ready(self):
        from apps.church import homepage

        from . import public_views as public_section

        # The church's public homepage (Phase 9B).
        homepage.register(public_section.homepage_section)
        from apps.church import seeding

        from . import defaults

        # What a new church starts with (Phase 9B).
        seeding.register(defaults.seed)
        from apps.church import dashboard as church_dashboard
        from apps.core.settings_menu import SettingsPage, register
        from apps.worship import bookings

        from . import dashboard

        church_dashboard.register_attention(dashboard.attention)
        church_dashboard.register_coming_up(dashboard.coming_up)
        church_dashboard.register_stat(dashboard.stats)

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
