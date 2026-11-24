from django.apps import AppConfig


class TeamsConfig(AppConfig):
    """Teams: Team Parts, Team Profiles, Assignments, Blackout Dates and Swap
    Requests. It sends Notifications through the core ``notifications`` app."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.teams"
    verbose_name = "Teams"

    def ready(self):
        from apps.accounts import role_changes
        from apps.church import dashboard as church_dashboard

        from .dashboard import my_schedule

        church_dashboard.register_panel(my_schedule, order=10)
        from apps.core.settings_menu import SettingsPage, register
        from apps.worship.signals import lineup_changed

        from .leaving import leaving_team
        from .notifying import on_lineup_changed

        lineup_changed.connect(on_lineup_changed, dispatch_uid="teams_notify_lineup")
        # A role change that takes someone off the team lists their coming
        # assignments for the admin to end or keep (Phase 9A, A2).
        role_changes.register(leaving_team)
        register(
            SettingsPage(
                "teams_occasions",
                "Team parts",
                "teams:parts_list",
                "teams.view_teampart",
                "teams",
                order=10,
            )
        )
