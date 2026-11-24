"""What the dashboard shows (Phase 9A, A7, part 3): "what needs you now".

Church Setup is core, so it never imports a Module. Each Module registers
what it adds in its ``AppConfig.ready()``, as functions of the request:

- ``register_attention(source)``: ``source(request)`` returns
  ``Attention`` items, only for people who may act on them;
- ``register_coming_up(source)``: ``source(request)`` returns
  ``ComingUp`` rows for the next services and occasions;
- ``register_panel(source, order)``: ``source(request)`` returns a
  ``Panel`` for the side column, or None.

A Module that is switched off adds nothing: each source checks it.
"""

import datetime
from dataclasses import dataclass, field

from django.utils import timezone

_attention = []
_coming_up = []
_panels = []

COMING_UP_SHOWN = 5


@dataclass
class Attention:
    """One thing someone should act on: a sentence, a detail, one button."""

    text: str
    detail: str
    url: str
    button: str
    # Earlier first; soonest services before the rest.
    sort_key: tuple = ()


@dataclass
class ComingUp:
    """One coming service or occasion. ``lineup`` is a status pill key, or
    None where the person may not see lineups; ``team`` is text, or None
    where they may not see teams."""

    starts_at: datetime.datetime
    title: str
    url: str
    is_occasion: bool = False
    is_cancelled: bool = False
    theme: str = ""
    passage: str = ""
    lineup: str | None = None
    team: str | None = None


@dataclass
class Panel:
    """A card in the side column: lines of (text, detail, status pill)."""

    title: str
    link_label: str = ""
    link_url: str = ""
    lines: list = field(default_factory=list)
    empty: str = "Nothing yet."


def register_attention(source):
    if source not in _attention:
        _attention.append(source)


def register_coming_up(source):
    if source not in _coming_up:
        _coming_up.append(source)


def register_panel(source, order=0):
    if all(existing is not source for _, existing in _panels):
        _panels.append((order, source))
        _panels.sort(key=lambda pair: pair[0])


def attention(request):
    items = [item for source in _attention for item in source(request)]
    return sorted(items, key=lambda item: item.sort_key)


def coming_up(request):
    rows = [row for source in _coming_up for row in source(request)]
    return sorted(rows, key=lambda row: row.starts_at)[:COMING_UP_SHOWN]


def panels(request):
    found = (source(request) for _, source in _panels)
    return [panel for panel in found if panel is not None]


def greeting(now=None):
    hour = timezone.localtime(now).hour
    if hour < 12:
        return "Good morning"
    if hour < 18:
        return "Good afternoon"
    return "Good evening"
