"""LRCLIB client: lyrics by title, artist, album and length.

LRCLIB asks clients to send one request at a time and to name themselves,
so the client waits between requests, sends ``settings.LRCLIB_USER_AGENT``,
and waits out a 429's Retry-After. A lookup that misses falls back to a
search by title and artist.

Lyrics are copyrighted: they are stored only on the song, never logged.
"""

import re
import time
from dataclasses import dataclass

from django.conf import settings

from apps.core import http

from .models import Song

API = "https://lrclib.net/api"
# LRCLIB matches a length within 2 seconds.
LENGTH_TOLERANCE = 2
MAX_WAIT_SECONDS = 60
TIMESTAMP = re.compile(r"\[\d+:\d+(?:[.:]\d+)?\]\s?")

Status = Song.LyricsStatus


class LyricsError(Exception):
    """LRCLIB couldn't be reached or answered with an error."""


@dataclass(frozen=True)
class LyricsResult:
    status: str
    lyrics: str = ""


def plain_lyrics(record):
    """The lyrics in one LRCLIB record, as a LyricsResult."""
    if record.get("instrumental"):
        return LyricsResult(Status.INSTRUMENTAL)
    text = record.get("plainLyrics") or TIMESTAMP.sub(
        "", record.get("syncedLyrics") or ""
    )
    text = text.strip()
    return LyricsResult(Status.FOUND, text) if text else LyricsResult(Status.MISSING)


def best_match(records, length_seconds=None):
    """The search result most likely to be the song: one with lyrics, with
    the closest length."""

    def has_lyrics(record):
        return bool(record.get("plainLyrics") or record.get("syncedLyrics"))

    def distance(record):
        duration = record.get("duration")
        if length_seconds is None or duration is None:
            return 0
        return abs(float(duration) - length_seconds)

    usable = [r for r in records if isinstance(r, dict) and has_lyrics(r)]
    return min(usable, key=distance) if usable else None


class LrclibClient:
    def __init__(
        self,
        user_agent=None,
        *,
        delay=0.35,
        max_retries=2,
        sleep=time.sleep,
        clock=time.monotonic,
    ):
        self.user_agent = user_agent or settings.LRCLIB_USER_AGENT
        self.delay = delay
        self.max_retries = max_retries
        self._sleep = sleep
        self._clock = clock
        self._last_request = None

    def lookup(self, title, artist, album="", length_seconds=None):
        """Lyrics for one song; ``LyricsResult`` with a ``Song.LyricsStatus``."""
        reply = self._get(
            "/get",
            {
                "track_name": title,
                "artist_name": artist,
                "album_name": album,
                "duration": length_seconds,
            },
        )
        if reply.status == 200 and isinstance(reply.data, dict):
            return plain_lyrics(reply.data)
        if reply.status != 404:
            raise LyricsError(f"LRCLIB answered {reply.status}.")
        reply = self._get("/search", {"track_name": title, "artist_name": artist})
        if not reply.ok:
            raise LyricsError(f"LRCLIB answered {reply.status}.")
        records = reply.data if isinstance(reply.data, list) else []
        match = best_match(records, length_seconds)
        if match is None:
            instrumental = any(
                isinstance(r, dict) and r.get("instrumental") for r in records
            )
            return LyricsResult(Status.INSTRUMENTAL if instrumental else Status.MISSING)
        return plain_lyrics(match)

    def _get(self, path, params):
        for attempt in range(self.max_retries + 1):
            self._wait_turn()
            try:
                reply = http.request(
                    "GET",
                    f"{API}{path}",
                    params=params,
                    headers={"User-Agent": self.user_agent},
                )
            except http.HttpError as error:
                raise LyricsError(f"LRCLIB couldn't be reached ({error}).") from error
            finally:
                self._last_request = self._clock()
            if reply.status != 429 or attempt == self.max_retries:
                return reply
            self._sleep(min(_retry_after(reply.headers), MAX_WAIT_SECONDS))
        raise AssertionError("unreachable")  # pragma: no cover

    def _wait_turn(self):
        """Keep ``delay`` seconds between requests."""
        if self._last_request is None:
            return
        remaining = self.delay - (self._clock() - self._last_request)
        if remaining > 0:
            self._sleep(remaining)


def _retry_after(headers):
    try:
        return max(float(headers.get("retry-after", "5")), 0)
    except ValueError:
        return 5
