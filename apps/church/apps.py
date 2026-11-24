from django.apps import AppConfig


class ChurchConfig(AppConfig):
    """Church Setup: the Church Profile, Modules, Labels and the dashboard."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.church"
    verbose_name = "Church Setup"

    def ready(self):
        from apps.core.settings_menu import SettingsPage, register

        # The Church Profile's sections open the Settings hub (Phase 9A, A7).
        manage = "church.change_churchprofile"
        register(
            *(
                SettingsPage(
                    "general",
                    title,
                    "church:settings",
                    manage,
                    order=order,
                    url_kwargs=(("section", section),),
                )
                for order, (section, title) in enumerate(
                    (
                        ("details", "Church details"),
                        ("labels", "Labels"),
                        ("modules", "Modules"),
                    )
                )
            )
        )
