"""The Module registry and module switching.

Every Module ships in every installation (decision 0001). The church switches
Modules off in the Church Profile; a switched-off Module is hidden and its
pages return 404, while its data stays in the database.
"""

from dataclasses import dataclass

from django.conf import settings
from django.http import Http404


@dataclass(frozen=True)
class Module:
    code: str
    name: str
    description: str
    # Django app labels holding the Module's models and permissions.
    app_labels: tuple[str, ...]
    # URL name of the Module's main page; None until the Module is built.
    url_name: str | None = None
    # Label key whose plural names the Module in the UI, if the church can
    # rename it (e.g. "member" -> "Members" or "Parishioners").
    label_key: str | None = None
    # Modules this one builds on: it counts as switched off while any of
    # them is switched off.
    requires: tuple[str, ...] = ()
    # The permission the Module's main page needs, or a tuple of which any
    # one will do; None when anyone signed in may open it. The navigation
    # and the dashboard list a Module only for people who can open it
    # (Phase 9A, A1).
    view_permission: str | tuple[str, ...] | None = None
    # False while the Module's records aren't kept apart per church yet
    # (Phase 9B, decision 0014): only a church with
    # ``members_teams_unlocked`` may switch it on.
    platform_ready: bool = True
    # The Module it is shown under on the Modules page, with a switch of
    # its own (Teams, the Praise Team, sits under Worship).
    parent: str | None = None

    def can_open(self, user):
        if self.view_permission is None:
            return True
        if isinstance(self.view_permission, tuple):
            return any(user.has_perm(p) for p in self.view_permission)
        return user.has_perm(self.view_permission)


MODULES = (
    Module(
        "members",
        "Members",
        "People and households in the church.",
        ("members",),
        url_name="members:list",
        label_key="member",
        view_permission="members.view_member",
        platform_ready=False,
    ),
    Module(
        "worship",
        "Worship",
        "Worship services, their themes and song lineups, and the song library.",
        ("worship", "songs"),
        url_name="worship:home",
        view_permission="worship.view_worshipservice",
    ),
    Module(
        "teams",
        "Teams",
        "Who serves at each worship service, and when people are available.",
        ("teams",),
        url_name="teams:my_schedule",
        requires=("worship",),
        parent="worship",
        # My schedule is for the team. Notifications are core and have
        # their own link in the navigation.
        view_permission="teams.view_assignment",
        # Kept apart per church since 28 Nov 2026, so every church may use it.
    ),
    Module(
        "occasions",
        "Occasions",
        "Weddings, baptisms, funerals and other special services: requests, "
        "approval and booked times on the calendar.",
        ("occasions",),
        url_name="occasions:home",
        # Booked times are shared with worship services on Worship's calendar.
        requires=("worship",),
        # People who see occasions, and people who may only ask for one.
        view_permission=("occasions.view_occasion", "occasions.request_occasion"),
    ),
    Module(
        "announcements",
        "Announcements",
        "Notes to everyone, or to the team of one worship service.",
        ("announcements",),
        url_name="announcements:list",
    ),
)

MODULES_BY_CODE = {module.code: module for module in MODULES}
MODULE_CHOICES = [(module.code, module.name) for module in MODULES]


def is_retired(module):
    """Whether no church may use ``module`` (``settings.RETIRED_MODULES``)."""
    return module.code in getattr(settings, "RETIRED_MODULES", ())


def is_available(module, profile):
    """Whether ``profile``'s church may use ``module`` at all."""
    if is_retired(module):
        return False
    return module.platform_ready or profile.members_teams_unlocked


def is_enabled(code, profile):
    """Whether the Module ``code`` is switched on for the church
    ``profile``. Without a church, no Module is."""
    if code not in MODULES_BY_CODE:
        raise ValueError(f"Unknown module: {code}")
    if profile is None:
        return False
    switched_off = set(profile.disabled_modules)
    switched_off.update(m.code for m in MODULES if not is_available(m, profile))
    module = MODULES_BY_CODE[code]
    return code not in switched_off and not switched_off.intersection(module.requires)


def enabled_modules(profile):
    """The Modules switched on for ``profile``. Without a church (the public
    landing page), every Module, to show what CHORD offers."""
    if profile is None:
        return list(MODULES)
    return [m for m in MODULES if is_enabled(m.code, profile)]


class ModuleRequiredMixin:
    """View mixin: return 404 when ``module`` is switched off.

    Put it first in the bases, before the login and permission mixins, so a
    switched-off Module looks absent to everyone.
    """

    module = None

    def dispatch(self, request, *args, **kwargs):
        church = getattr(request, "church", None)
        signing_in_first = church is None and not request.user.is_authenticated
        if not signing_in_first and not is_enabled(self.module, church):
            raise Http404("This module is switched off.")
        return super().dispatch(request, *args, **kwargs)
