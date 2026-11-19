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
    "office_staff": [
        # Members (Phase 2)
        "members.view_member",
        "members.add_member",
        "members.change_member",
        "members.view_private_details",
        "members.import_member",
        "members.export_member",
        "members.view_household",
        "members.add_household",
        "members.change_household",
        "members.view_membershipstatus",
        "members.view_relationshiptype",
        "members.view_memberfield",
        # Worship schedule (Phase 3)
        "worship.view_worshipservice",
        "worship.record_attendance",
    ],
    "pastoral_staff": [
        "members.view_member",
        # Worship schedule (Phase 3)
        "worship.view_worshipservice",
        "worship.add_worshipservice",
        "worship.change_worshipservice",
        "worship.change_theme",
        "worship.record_attendance",
        "worship.view_servicetemplate",
        "worship.add_servicetemplate",
        "worship.change_servicetemplate",
        "worship.view_sermonseries",
        "worship.add_sermonseries",
        "worship.change_sermonseries",
        # Song pool (Phase 4)
        "songs.view_song",
        "songs.view_themetag",
        # Song suggestions (Phase 5); never for team members
        "worship.suggest_songs",
        "worship.view_searchrun",
        "worship.view_season",
        # Lineups (Phase 6): the final say is a permission, never a role
        # name (decision 0008)
        "worship.view_lineup",
        "worship.add_lineup",
        "worship.change_lineup",
        "worship.finalize_lineup",
    ],
    "worship_leader": [
        "members.view_member",
        # Worship schedule (Phase 3)
        "worship.view_worshipservice",
        "worship.view_servicetemplate",
        "worship.view_sermonseries",
        # Song pool (Phase 4)
        "songs.view_song",
        "songs.add_song",
        "songs.change_song",
        "songs.view_themetag",
        "songs.add_themetag",
        "songs.change_themetag",
        "songs.view_trustedartist",
        "songs.add_trustedartist",
        "songs.change_trustedartist",
        # Song suggestions (Phase 5); never for team members
        "worship.suggest_songs",
        "worship.view_searchrun",
        "worship.view_season",
        "worship.add_season",
        "worship.change_season",
        "worship.view_suggestionsettings",
        "worship.change_suggestionsettings",
        # Phase 5 smoke-test fixes
        "songs.view_worshipchecksettings",
        "songs.change_worshipchecksettings",
        # Lineups (Phase 6)
        "worship.view_lineup",
        "worship.add_lineup",
        "worship.change_lineup",
    ],
    "team_member": [
        # Worship schedule (Phase 3)
        "worship.view_worshipservice",
        # Lineups (Phase 6): confirmed lineups only
        "worship.view_lineup",
    ],
}


def managed_permission_apps():
    from apps.church.modules import MODULES

    module_apps = [label for m in MODULES for label in m.app_labels]
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
