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
        post_migrate.connect(_sync_roles, dispatch_uid="chord_sync_default_roles")
