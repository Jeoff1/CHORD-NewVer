"""Default roles, the permissions CHORD manages, and administrator rules.

The default roles are created once by a data migration; the church may
rename them, edit their permissions, or delete them (except Administrator).
The Administrator role always holds every managed permission, so the church
can't lock itself out.
"""

from django.apps import apps as django_apps
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.db.models import Q

ADMINISTRATOR = "administrator"

# Apps whose permissions appear in the permission matrix, besides the Modules.
CORE_PERMISSION_APPS = ("church", "accounts", "audit")

# "app_label.codename" permissions each default role receives once. Each
# later phase adds the permissions for its Module here.
DEFAULT_ROLE_PERMISSIONS = {
    "office_staff": [],
    "finance": [],
    "records_keeper": [],
    "worship_leader": [],
    "ministry_leader": [],
}


def managed_permission_apps():
    from apps.church.modules import MODULES

    module_apps = [m.app_label for m in MODULES]
    return [
        label
        for label in (*CORE_PERMISSION_APPS, *module_apps)
        if django_apps.is_installed(f"apps.{label}")
    ]


def managed_permissions():
    """Permissions CHORD's models declare, in matrix order.

    Only declared permissions count, so a stale row left in the database
    (e.g. a permission a model no longer declares) never shows.
    """
    wanted = Q(pk__in=[])
    for label in managed_permission_apps():
        for model in django_apps.get_app_config(label).get_models():
            opts = model._meta
            codenames = [
                f"{action}_{opts.model_name}" for action in opts.default_permissions
            ]
            codenames += [codename for codename, _ in opts.permissions]
            wanted |= Q(
                content_type__app_label=opts.app_label,
                content_type__model=opts.model_name,
                codename__in=codenames,
            )
    return (
        Permission.objects.filter(wanted)
        .select_related("content_type")
        .order_by("content_type__app_label", "content_type__model", "codename")
    )


def sync_default_role_permissions():
    """Give the Administrator every managed permission, and grant default
    permissions not yet granted to the other default roles."""
    from .models import Role

    administrator = Role.objects.filter(key=ADMINISTRATOR).first()
    if administrator:
        administrator.permissions.add(*managed_permissions())

    for key, perm_names in DEFAULT_ROLE_PERMISSIONS.items():
        role = Role.objects.filter(key=key).first()
        if role is None:
            continue
        pending = [name for name in perm_names if name not in role.granted_defaults]
        for name in pending:
            app_label, codename = name.split(".")
            permission = Permission.objects.filter(
                content_type__app_label=app_label, codename=codename
            ).first()
            if permission:
                role.permissions.add(permission)
                role.granted_defaults.append(name)
        role.save(update_fields=["granted_defaults"])


def administrators():
    """Active users with full access: superusers and Administrator role holders."""
    return (
        get_user_model()
        .objects.filter(is_active=True)
        .filter(Q(is_superuser=True) | Q(groups__role__key=ADMINISTRATOR))
        .distinct()
    )


def is_administrator(user):
    return administrators().filter(pk=user.pk).exists()
