"""Default roles, the permissions CHORD manages, and administrator rules.

Each church has its own roles (decision 0014). The first church's default
roles came from data migrations; every later church gets the same ones from
``seed_roles`` when it is created. A church may rename its roles, edit their
permissions, or delete them (except Administrator). The Administrator role
always holds every managed permission, so a church can't lock itself out.
"""

from django.apps import apps as django_apps
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.db.models import Q

ADMINISTRATOR = "administrator"

# key, title, description: what a new church starts with. Matches the
# first church's roles as the data migrations left them.
DEFAULT_ROLES = [
    (ADMINISTRATOR, "Administrator", "Full access to every part of CHORD."),
    (
        "office_staff",
        "Office Staff",
        "Day-to-day office work, such as keeping the member directory.",
    ),
    (
        "pastoral_staff",
        "Pastoral Staff",
        "Schedules worship services, posts each service's theme, and has the "
        "final say on its lineup.",
    ),
    (
        "worship_leader",
        "Worship Leader",
        "Builds and confirms lineups, and manages songs, chord sheets and teams.",
    ),
    (
        "team_member",
        "Team Member",
        "Sees confirmed lineups and song pages, and marks their own availability.",
    ),
    (
        "church_member",
        "Church Member",
        "Sees the schedule, announcements and their own member record. "
        "Doesn't see lineups, song pages or chord sheets.",
    ),
]

# Apps whose permissions appear in the permission matrix, besides the Modules.
CORE_PERMISSION_APPS = ("church", "accounts", "audit")

# "app_label.codename" permissions each default role receives once. Each
# later phase adds the permissions for its Module here.
DEFAULT_ROLE_PERMISSIONS = {
    "office_staff": [
        # Occasions (Phase 9A, A5): they see the bookings
        "occasions.view_occasion",
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
        # Reports (Phase 6)
        "worship.view_song_usage",
        # Chord sheets and lyrics (Phase 7); approving is a permission
        "songs.view_lyrics",
        "songs.view_chordsheet",
        "songs.add_chordsheet",
        "songs.approve_chordsheet",
        # Teams (Phase 8): sees the roster and each service's team; since
        # Phase 9C the pastor also assigns it (the planning steps' second step)
        "teams.view_teampart",
        "teams.view_teamprofile",
        "teams.view_assignment",
        "teams.add_assignment",
        "teams.delete_assignment",
        # Announcements (Phase 8)
        "announcements.add_announcement",
        # Occasions (Phase 9A, A5): they book occasions, keep the occasion
        # types and approve requests (a permission, never a role name)
        "occasions.view_occasion",
        "occasions.add_occasion",
        "occasions.change_occasion",
        "occasions.view_occasiontype",
        "occasions.add_occasiontype",
        "occasions.change_occasiontype",
        "occasions.request_occasion",
        "occasions.approve_occasion",
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
        # Reports (Phase 6)
        "worship.view_song_usage",
        # Chord sheets and lyrics (Phase 7); approving is a permission
        "songs.view_lyrics",
        "songs.view_chordsheet",
        "songs.add_chordsheet",
        "songs.approve_chordsheet",
        # Teams (Phase 8): the leader keeps the team parts and assigns people
        "teams.view_teampart",
        "teams.add_teampart",
        "teams.change_teampart",
        "teams.view_teamprofile",
        "teams.change_teamprofile",
        "teams.view_assignment",
        "teams.add_assignment",
        "teams.delete_assignment",
        # Announcements (Phase 8)
        "announcements.add_announcement",
        # Occasions (Phase 9A, A5): they see the bookings, and may ask
        "occasions.view_occasion",
        "occasions.request_occasion",
    ],
    "team_member": [
        # Worship schedule (Phase 3)
        "worship.view_worshipservice",
        # Lineups (Phase 6): confirmed lineups only
        "worship.view_lineup",
        # Chord sheets (Phase 7): their pastes wait for approval; the words
        # come through the sheet, not the full lyrics
        "songs.view_chordsheet",
        "songs.add_chordsheet",
        # Teams (Phase 8): sees each service's team; replies, Team Profile
        # and Blackout Dates are their own and need no permission
        "teams.view_assignment",
    ],
    "church_member": [
        # Phase 9A (A1): the schedule, with each service's theme title. The
        # service page shows lineups, the team, suggestions and theme notes
        # only to holders of their own permissions, so none of them shows.
        # Announcements to everyone and their own member record need no
        # permission.
        "worship.view_worshipservice",
        # Occasions (Phase 9A, A5): they ask; others' show only as "Booked"
        "occasions.request_occasion",
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


def seed_roles(church):
    """Give a new church its own default roles and their permissions."""
    from .models import Role

    for key, title, description in DEFAULT_ROLES:
        Role.objects.get_or_create(
            church=church,
            key=key,
            defaults={"title": title, "description": description},
        )
    sync_default_role_permissions(church)


def sync_default_role_permissions(church=None):
    """In each church (or only ``church``), give the Administrator every
    managed permission, and grant default permissions not yet granted to
    the other default roles."""
    from .models import Role

    roles = Role.objects.exclude(key=None)
    if church is not None:
        roles = roles.filter(church=church)
    managed = list(managed_permissions())
    for administrator in roles.filter(key=ADMINISTRATOR):
        administrator.permissions.add(*managed)

    for role in roles.filter(key__in=DEFAULT_ROLE_PERMISSIONS):
        perm_names = DEFAULT_ROLE_PERMISSIONS[role.key]
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


def _holders(church, roles_condition):
    """A condition on User: an active Membership in ``church`` with a role
    matching ``roles_condition`` (a Q on Role)."""
    from .models import Membership, Role

    return Q(
        memberships__in=Membership.objects.filter(
            church=church,
            is_active=True,
            roles__in=Role.objects.filter(roles_condition),
        )
    )


def users_with_perm(church, perm, *, include_superusers=False):
    """Active users holding ``perm`` ("app_label.codename") in ``church``,
    for code without a request (notifications, approvers, the worker)."""
    app_label, codename = perm.split(".")
    condition = _holders(
        church,
        Q(permissions__content_type__app_label=app_label)
        & Q(permissions__codename=codename),
    )
    if include_superusers:
        condition |= Q(is_superuser=True)
    return get_user_model().objects.filter(condition, is_active=True).distinct()


def administrators(church):
    """Active users with full access in ``church``: superusers and holders of
    its Administrator role."""
    condition = Q(is_superuser=True) | _holders(church, Q(key=ADMINISTRATOR))
    return get_user_model().objects.filter(condition, is_active=True).distinct()


def is_administrator(user, church):
    return administrators(church).filter(pk=user.pk).exists()
