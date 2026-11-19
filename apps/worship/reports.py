"""Reports: song usage and attendance (Design-Decisions, Phase 6).

- **Song usage**: every song in the confirmed lineups of services already
  held (not cancelled), with how often and when it was sung. Songs sung
  again within the church's repeat window (Suggestion Settings) are
  highlighted: used more often than the recent-use window allows. It reads
  the same ``usage.uses()`` that ranking does.
- **Attendance**: the headcount of each service that has one. A church that
  never records a headcount gets no attendance report.
"""

import csv
import io
from dataclasses import dataclass

from django.utils import timezone

from apps.songs.models import Song

from .models import SuggestionSettings, WorshipService
from .usage import by_song, uses


@dataclass
class UsageRow:
    song: Song
    days: list
    sung_again: bool

    @property
    def times(self):
        return len(self.days)

    @property
    def last_used(self):
        return self.days[-1]


def song_usage(start=None, end=None, window_weeks=None):
    """Rows for the song usage report, most used first. ``start`` and
    ``end`` are dates (both included); ``window_weeks`` defaults to the
    church's repeat window."""
    if window_weeks is None:
        window_weeks = SuggestionSettings.load().repeat_window_weeks
    found = by_song(uses(until=timezone.now(), start=start, end=end))
    songs = Song.objects.in_bulk(list(found))
    rows = [
        UsageRow(songs[pk], usage.days, usage.sung_again_within(window_weeks))
        for pk, usage in found.items()
    ]
    rows.sort(key=lambda r: (-r.times, -r.last_used.toordinal(), r.song.title.lower()))
    return rows


def song_usage_csv(rows, window_weeks):
    """The report as CSV text. Lyrics are never included."""
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(
        [
            "Song",
            "Artist",
            "Times used",
            "Last used",
            "Dates used",
            f"Sung again within {window_weeks} weeks",
        ]
    )
    for row in rows:
        writer.writerow(
            [
                row.song.title,
                row.song.artist,
                row.times,
                row.last_used.isoformat(),
                "; ".join(day.isoformat() for day in row.days),
                "Yes" if row.sung_again else "No",
            ]
        )
    return out.getvalue()


def has_attendance():
    """Whether any headcount was ever recorded: without one, the attendance
    report doesn't exist."""
    return WorshipService.objects.exclude(attendance=None).exists()


def attendance(start=None, end=None):
    """Services held with a headcount, newest first, between two dates."""
    services = (
        WorshipService.objects.held()
        .exclude(attendance=None)
        .select_related("template")
        .order_by("-starts_at")
    )
    return [
        service
        for service in services
        if (start is None or service.local_date >= start)
        and (end is None or service.local_date <= end)
    ]
