"""Other bookings on the Worship calendar (Phase 9A, A5; decision 0013).

Worship services book the calendar themselves. A Module built on Worship,
such as Occasions, books it too, but Worship never imports it: the Module
registers a **source** here in its ``AppConfig.ready()``. A source is
``source(start, end, church, user)`` and returns the church's ``Booking``s
that start in that window, as ``user`` may see them: a booking without a
``url`` shows only as "Booked".
"""

import datetime
from dataclasses import dataclass

_sources = []


@dataclass
class Booking:
    starts_at: datetime.datetime
    ends_at: datetime.datetime
    # What the person may see; empty, with no url, for "Booked".
    label: str = ""
    url: str = ""
    is_cancelled: bool = False


def register(source):
    if source not in _sources:
        _sources.append(source)


def calendar_bookings(start, end, church, user):
    """Every registered source's bookings in ``church`` starting between
    ``start`` and ``end``, for ``user``."""
    found = []
    for source in _sources:
        found.extend(source(start, end, church, user))
    return found
