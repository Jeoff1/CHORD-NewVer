from django.apps import AppConfig


class WorshipConfig(AppConfig):
    """Worship: services, their themes, song suggestions and lineups."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.worship"
    verbose_name = "Worship"

    def ready(self):
        from apps.church import homepage

        from . import public as public_section

        # The church's public homepage (Phase 9B).
        homepage.register(public_section.homepage_section)
        from apps.church import seeding

        from . import defaults

        # What a new church starts with (Phase 9B).
        seeding.register(defaults.seed)
        from apps.church import dashboard as church_dashboard
        from apps.core.settings_menu import SettingsPage, register

        from . import dashboard

        # The dashboard's "Needs your attention" and "Coming up" (Phase 9A, A7).
        church_dashboard.register_attention(dashboard.attention)
        church_dashboard.register_coming_up(dashboard.coming_up)
        # The overview figures and the lineup status bar (dashboard redesign).
        church_dashboard.register_stat(dashboard.stats)
        church_dashboard.register_breakdown(dashboard.lineup_breakdown)

        from .views.base import SETTINGS_GROUPS, SETTINGS_PAGES

        # The Worship settings (with the song pool's) in the Settings hub,
        # in two groups (Phase 9A, A7).
        for order, (label, permission, url_name) in enumerate(SETTINGS_PAGES):
            register(
                SettingsPage(
                    "worship",
                    _settings_label(label),
                    url_name,
                    permission,
                    "worship",
                    group=SETTINGS_GROUPS[url_name],
                    order=order,
                )
            )


def _settings_label(label):
    """A label that may name the church's word for a sermon."""
    if "{sermon}" not in label:
        return label

    def with_sermon(request):
        from apps.church.labels import Labels

        church = getattr(request, "church", None)
        labels = church.label_set if church is not None else Labels({})
        return label.format(sermon=labels.get("sermon"))

    return with_sermon
