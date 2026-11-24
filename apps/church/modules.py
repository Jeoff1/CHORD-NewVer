"""The Module registry and module switching.

Every Module ships in every installation (decision 0001). The church switches
Modules off in the Church Profile; a switched-off Module is hidden and its
pages return 404, while its data stays in the database.
"""

from dataclasses import dataclass

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
    # The permission the Module's main page needs; None when anyone signed
    # in may open it. The navigation and the dashboard list a Module only
    # for people who can open it (Phase 9A, A1).
    view_permission: str | None = None

    def can_open(self, user):
        return self.view_permission is None or user.has_perm(self.view_permission)


MODULES = (
    Module(
        "members",
        "Members",
        "People and households in the church.",
        ("members",),
        url_name="members:list",
        label_key="member",
        view_permission="members.view_member",
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
        # My schedule is for the team; anyone else reaches their
        # Notifications from the navigation's own link.
        view_permission="teams.view_assignment",
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


def is_enabled(code, profile=None):
    """Whether the Module ``code`` is switched on for this church."""
    if code not in MODULES_BY_CODE:
        raise ValueError(f"Unknown module: {code}")
    if profile is None:
        from .models import ChurchProfile

        profile = ChurchProfile.load()
    switched_off = set(profile.disabled_modules)
    module = MODULES_BY_CODE[code]
    return code not in switched_off and not switched_off.intersection(module.requires)


def enabled_modules(profile):
    return [m for m in MODULES if is_enabled(m.code, profile)]


class ModuleRequiredMixin:
    """View mixin: return 404 when ``module`` is switched off.

    Put it first in the bases, before the login and permission mixins, so a
    switched-off Module looks absent to everyone.
    """

    module = None

    def dispatch(self, request, *args, **kwargs):
        if not is_enabled(self.module, getattr(request, "church", None)):
            raise Http404("This module is switched off.")
        return super().dispatch(request, *args, **kwargs)
