from django.apps import AppConfig
from django.db import connections
from django.db.models.signals import post_migrate


def _sync_roles(sender, using="default", **kwargs):
    # Permissions are created after migrations run, so default roles get
    # theirs here rather than in a migration.
    if "accounts_role" not in connections[using].introspection.table_names():
        return
    from .roles import sync_default_role_permissions

    sync_default_role_permissions()


class AccountsConfig(AppConfig):
    """Users, roles and permissions."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.accounts"
    verbose_name = "Users and Roles"

    def ready(self):
        from apps.church import seeding

        from .roles import seed_roles

        # What a new church starts with (Phase 9B).
        seeding.register(seed_roles)
        from apps.core.settings_menu import SettingsPage, register

        post_migrate.connect(_sync_roles, dispatch_uid="chord_sync_default_roles")
        register(
            # Everyone's own light or dark mode (Phase 9A, A7). Users and
            # Roles and permissions are pages of their own, under Members in
            # the sidebar (apps/church/navigation.py), not settings.
            SettingsPage("personal", "Appearance", "accounts:appearance", None),
        )
