"""What a church's public homepage shows (Phase 9B, decision 0014).

Church Setup is core and never imports a Module, so each Module registers a
**section** here in its ``AppConfig.ready()``: ``section(church, request)``
returns a ``Section`` or None. A section shows only what the church chose
to publish, and never lyrics, chord sheets, songs, lineups, members or
teams. A Module that is switched off adds nothing: each section checks it.
"""

from dataclasses import dataclass, field

_sections = []


@dataclass
class Section:
    """One part of the homepage: a template and what it needs, and where it
    goes on the profile (redesign, 27 Nov 2026): ``"tab"`` is a tab beside
    the others in the main area, with its ``label``, ``count`` and ``icon``
    (an icon name from ``templates/includes/icons/``); ``"side"`` sits in the
    information sidebar."""

    template: str
    context: dict = field(default_factory=dict)
    order: int = 0
    slot: str = "tab"
    label: str = ""
    count: int | None = None
    icon: str = ""


def register(section):
    if section not in _sections:
        _sections.append(section)


def sections(church, request):
    found = [section(church, request) for section in _sections]
    return sorted((s for s in found if s is not None), key=lambda s: s.order)
