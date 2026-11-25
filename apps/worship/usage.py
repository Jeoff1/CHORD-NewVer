"""Song usage: which songs were in confirmed lineups, and when.

Usage is computed from confirmed lineups when needed; it isn't stored
(Design-Decisions, Phase 6; workflow review F8). A lineup counts once it is
confirmed, for a service that isn't cancelled. Ranking reads the usage
before a service (``ranking.song_usage``); the song usage report reads the
services already held. Both come from ``uses()``, so they always agree.
"""

import datetime
from dataclasses import dataclass, field

from django.utils import timezone

from . import scheduling
from .models import Lineup, LineupItem


@dataclass(frozen=True)
class Use:
    song_id: int
    service_id: int
    day: datetime.date  # the service's date, in the church's time zone


def uses(church, *, before=None, until=None, start=None, end=None):
    """Every song in a confirmed lineup of a service of ``church`` that
    isn't cancelled, oldest first. ``before`` and ``until`` are moments:
    services starting before ``before``, or at or before ``until``.
    ``start`` and ``end`` are dates in the church's time zone, both
    included."""
    items = LineupItem.objects.for_church(church).filter(
        lineup__status=Lineup.Status.CONFIRMED,
        lineup__service__is_cancelled=False,
    )
    if before is not None:
        items = items.filter(lineup__service__starts_at__lt=before)
    if until is not None:
        items = items.filter(lineup__service__starts_at__lte=until)
    rows = items.values_list(
        "song_id", "lineup__service_id", "lineup__service__starts_at"
    ).order_by("lineup__service__starts_at", "lineup__service_id", "position")
    zone = scheduling.church_time_zone(church)
    found = [
        Use(song_id, service_id, timezone.localtime(starts_at, zone).date())
        for song_id, service_id, starts_at in rows
    ]
    return [
        use
        for use in found
        if (start is None or use.day >= start) and (end is None or use.day <= end)
    ]


@dataclass
class SongUsage:
    """One song's uses, oldest first."""

    song_id: int
    days: list = field(default_factory=list)

    @property
    def times(self):
        return len(self.days)

    @property
    def last_used(self):
        return self.days[-1] if self.days else None

    def sung_again_within(self, window_weeks):
        """Whether two uses came closer together than the repeat window:
        the song was used more often than the recent-use window allows."""
        if not window_weeks:
            return False
        window = datetime.timedelta(weeks=window_weeks)
        return any(b - a < window for a, b in zip(self.days, self.days[1:]))


def by_song(found):
    """``{song_id: SongUsage}`` from ``uses()``; one use per service."""
    usage, seen = {}, set()
    for use in found:
        if (use.song_id, use.service_id) in seen:
            continue
        seen.add((use.song_id, use.service_id))
        usage.setdefault(use.song_id, SongUsage(use.song_id)).days.append(use.day)
    return usage
