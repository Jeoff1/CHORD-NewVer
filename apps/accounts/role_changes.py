"""What a change to a user's roles or active status takes away (Phase 9A, A2).

Changing roles never deletes what a person did before: their lineups,
marks, chord sheets, past assignments and Audit Trail entries all point to
the user, never to a role, and users are deactivated, never deleted.

Some Modules hold things a person may keep only while they hold a
permission, such as a place on a coming service's team. Accounts is core
and never imports the Modules built on it, so a Module registers a
**consequence finder** here in its ``AppConfig.ready()``: given the user
and the permissions they would lose, it returns the things affected. The
user form lists them, and the admin chooses to end them or keep them.
"""

from dataclasses import dataclass, field

from django.contrib.auth.models import Permission
from django.db.models import Q

_finders = []


@dataclass
class Consequence:
    """Things a person holds that depend on a permission they would lose.

    ``title`` heads the list, ``items`` describes each thing for the admin,
    and ``end(actor)`` ends them all when the admin chooses to.
    """

    title: str
    items: list = field(default_factory=list)
    end: callable = None


def register(finder):
    """Add ``finder(user, lost_permissions)``, which returns a Consequence
    or None. Called once per Module, from its AppConfig.ready()."""
    if finder not in _finders:
        _finders.append(finder)


def permissions_after(user, *, roles, is_active):
    """The "app_label.codename" permissions ``user`` would hold with
    ``roles`` (plus any plain groups and their own permissions) and
    ``is_active``, without changing anything."""
    if not is_active:
        return set()
    if user.is_superuser:
        return {
            f"{p.content_type.app_label}.{p.codename}"
            for p in Permission.objects.select_related("content_type")
        }
    other_groups = user.groups.filter(role__isnull=True)
    groups = [role.pk for role in roles] + [g.pk for g in other_groups]
    held = (
        Permission.objects.filter(Q(user=user) | Q(group__in=groups))
        .select_related("content_type")
        .distinct()
    )
    return {f"{p.content_type.app_label}.{p.codename}" for p in held}


def lost_permissions(user, *, roles, is_active):
    """Permissions ``user`` holds now but wouldn't hold after. "Now" is read
    from the database, because a ModelForm copies its data onto the
    instance while validating."""
    stored = type(user).objects.get(pk=user.pk)
    now = permissions_after(
        stored, roles=list(stored.roles), is_active=stored.is_active
    )
    return now - permissions_after(stored, roles=roles, is_active=is_active)


def consequences(user, *, roles, is_active):
    """What the change would take away, from every registered Module."""
    lost = lost_permissions(user, roles=roles, is_active=is_active)
    if not lost:
        return []
    found = (finder(type(user).objects.get(pk=user.pk), lost) for finder in _finders)
    return [consequence for consequence in found if consequence and consequence.items]
