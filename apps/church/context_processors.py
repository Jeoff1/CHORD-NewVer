from dataclasses import dataclass

from django.urls import reverse

from .models import ChurchProfile
from .modules import enabled_modules


@dataclass(frozen=True)
class ModuleEntry:
    """A switched-on Module as the UI shows it, named in the church's words."""

    code: str
    name: str
    description: str
    url: str | None


def module_entries(profile):
    labels = profile.label_set
    return [
        ModuleEntry(
            code=module.code,
            name=(
                labels.get(module.label_key, plural=True)
                if module.label_key
                else module.name
            ),
            description=module.description,
            url=reverse(module.url_name) if module.url_name else None,
        )
        for module in enabled_modules(profile)
    ]


def church(request):
    """Template context: the Church Profile, its Labels and the module nav."""
    profile = getattr(request, "church", None) or ChurchProfile.load()
    entries = module_entries(profile)
    return {
        "church": profile,
        "labels": profile.label_set,
        "module_entries": entries,
        "enabled_modules": {entry.code for entry in entries},
    }
