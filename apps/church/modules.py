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
    # Django app label holding the Module's models and permissions.
    app_label: str
    # URL name of the Module's main page; None until the Module is built.
    url_name: str | None = None
    # Label key whose plural names the Module in the UI, if the church can
    # rename it (e.g. "ministry" -> "Ministries" or "Groups").
    label_key: str | None = None


MODULES = (
    Module(
        "members",
        "Members",
        "People and households in the church.",
        "members",
        url_name="members:list",
        label_key="member",
    ),
    Module(
        "ministries",
        "Ministries",
        "Groups that serve in the church, and who belongs to them.",
        "ministries",
        label_key="ministry",
    ),
    Module(
        "events",
        "Events",
        "The church calendar, venues and attendance.",
        "events",
    ),
    Module(
        "giving",
        "Giving",
        "Funds, contributions, receipts and giving statements.",
        "giving",
    ),
    Module(
        "records",
        "Records",
        "The church's official registers and certificates.",
        "records",
    ),
    Module(
        "services",
        "Services",
        "Services people request, such as weddings and burials.",
        "services",
        label_key="service",
    ),
    Module(
        "worship",
        "Worship",
        "Songs, worship plans, teams and rehearsals.",
        "worship",
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
    return code not in profile.disabled_modules


def enabled_modules(profile):
    return [m for m in MODULES if m.code not in profile.disabled_modules]


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
