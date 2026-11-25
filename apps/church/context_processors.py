from dataclasses import dataclass

from django.urls import reverse

from .labels import Labels
from .models import ChurchProfile
from .modules import MODULES_BY_CODE, enabled_modules


@dataclass(frozen=True)
class ModuleEntry:
    """A switched-on Module as the UI shows it, named in the church's words."""

    code: str
    name: str
    description: str
    url: str | None
    # Names of the Modules this one needs switched on.
    requires: tuple = ()


def module_name(module, labels):
    if module.label_key:
        return labels.get(module.label_key, plural=True)
    return module.name


def module_entries(profile):
    labels = profile.label_set if profile is not None else Labels({})
    return [
        ModuleEntry(
            code=module.code,
            name=module_name(module, labels),
            description=module.description,
            url=reverse(module.url_name) if module.url_name else None,
            requires=tuple(
                module_name(MODULES_BY_CODE[code], labels) for code in module.requires
            ),
        )
        for module in enabled_modules(profile)
    ]


def church(request):
    """Template context: the Church Profile, its Labels and the module nav.

    ``module_entries`` holds only the switched-on Modules the user can open;
    ``enabled_modules`` names every switched-on Module, for templates that
    link to a Module's other pages.
    """
    profile = getattr(request, "church", None)
    entries = module_entries(profile)
    user = getattr(request, "user", None)
    return {
        "church": profile,
        "labels": profile.label_set if profile is not None else Labels({}),
        "module_entries": [
            entry
            for entry in entries
            if user is not None and MODULES_BY_CODE[entry.code].can_open(user)
        ],
        "modules_switched_on": bool(entries),
        "enabled_modules": {entry.code for entry in entries},
        "my_churches": my_churches(user),
    }


def my_churches(user):
    """The churches the church switcher offers: the person's active
    memberships (every church for a superuser, for support)."""
    if user is None or not user.is_authenticated:
        return []
    churches = ChurchProfile.objects.all()
    if not user.is_superuser:
        churches = churches.filter(memberships__user=user, memberships__is_active=True)
    return list(churches.distinct().order_by("name"))
