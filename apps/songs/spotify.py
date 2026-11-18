"""Spotify Web API client for finding songs (the app's own token).

Spotify decides which songs get checked and plays them; nothing it returns
is ever model input (see AGENTS.md). Credentials come from ``.env``.

- Search returns at most 10 tracks a page (Development Mode); the offset
  stops at 1000.
- A search with a genre filter that finds nothing is run again without it,
  because ``genre:`` filters often match nothing.

Safeguards (Design-Decisions, Phase 5). Spotify locks out apps for hours
when they keep calling after a 429, so:

1. Every call first checks the shared block (``current_block``), saved in
   the database so the worker and web requests all respect it.
2. A 429 is saved as a ``SpotifyLimit`` with its reason and Retry-After,
   and logged. Nothing calls Spotify again until it has passed.
3. A short wait (up to ``MAX_WAIT_SECONDS``) is waited out and the request
   tried once more; a second 429, or a longer wait, raises
   ``SpotifyRateLimited``.
4. ``QUOTA_EXCEEDED``, or a Retry-After over ``LONG_WAIT_SECONDS``, pauses
   Spotify (``SpotifyPaused``): until Retry-After when Spotify gives one,
   otherwise for ``QUOTA_PAUSE``.
"""

import base64
import datetime
import logging
import time
from dataclasses import dataclass, field

from django.conf import settings
from django.utils import formats, timezone

from apps.core import http

from .models import SpotifyLimit

logger = logging.getLogger(__name__)

API = "https://api.spotify.com/v1"
TOKEN_URL = "https://accounts.spotify.com/api/token"
PAGE_SIZE = 10
MAX_OFFSET = 1000
# The longest Retry-After the client waits out (once) before giving up.
MAX_WAIT_SECONDS = 30
# A Retry-After longer than this is treated like a quota lockout.
LONG_WAIT_SECONDS = 3600
# How long a quota lockout pauses Spotify when Spotify gives no Retry-After.
QUOTA_PAUSE = datetime.timedelta(hours=24)
# Assumed when a 429 has no usable Retry-After header.
DEFAULT_RETRY_AFTER = 5

Reason = SpotifyLimit.Reason


class SpotifyError(Exception):
    """Spotify couldn't be reached or refused the request."""


class SpotifyNotConfigured(SpotifyError):
    pass


class SpotifyRateLimited(SpotifyError):
    """Spotify asked CHORD to wait; nothing calls it until ``until``."""

    def __init__(self, message, until):
        super().__init__(message)
        self.until = until


class SpotifyPaused(SpotifyRateLimited):
    """A quota lockout (or a very long wait): Spotify is paused until
    ``until``, and suggestions rank the songs already in the pool."""


@dataclass(frozen=True)
class Track:
    spotify_id: str
    title: str
    artists: tuple
    album: str = ""
    duration_ms: int | None = None

    @property
    def artist(self):
        return ", ".join(self.artists)

    @property
    def length_seconds(self):
        return round(self.duration_ms / 1000) if self.duration_ms else None

    @classmethod
    def from_api(cls, item):
        return cls(
            spotify_id=item["id"],
            title=item.get("name") or "",
            artists=tuple(a["name"] for a in item.get("artists") or () if a),
            album=(item.get("album") or {}).get("name") or "",
            duration_ms=item.get("duration_ms"),
        )


@dataclass
class SearchResult:
    tracks: list = field(default_factory=list)
    pages_read: int = 0
    # The genre filter found nothing, so the search ran without it.
    genre_dropped: bool = False


def search_query(phrase, genre=""):
    if not genre:
        return phrase
    genre = f'"{genre}"' if " " in genre else genre
    return f"{phrase} genre:{genre}"


# --- The shared block ----------------------------------------------------------


def current_block(now=None):
    """The ``SpotifyLimit`` still in force, or None when Spotify may be
    called. When several overlap, the one lasting longest wins."""
    now = now or timezone.now()
    return (
        SpotifyLimit.objects.filter(blocked_until__gt=now)
        .order_by("-blocked_until", "-pk")
        .first()
    )


def block_message(limit):
    """What to tell people about a block, with its end in the current time
    zone (the church's, in requests and in the search worker)."""
    until = formats.date_format(timezone.localtime(limit.blocked_until), "M j, g:i A")
    if limit.reason == Reason.QUOTA:
        return (
            f"Spotify's limit for this app was reached, so CHORD has paused "
            f"Spotify until {until}. Suggestions rank the songs already in the "
            "pool until then."
        )
    if limit.reason == Reason.LONG_WAIT:
        return (
            f"Spotify asked CHORD to wait until {until}, so Spotify is paused "
            "until then. Suggestions rank the songs already in the pool."
        )
    return f"Spotify asked CHORD to wait until {until}. Try again after that."


def blocked_error(limit):
    error = SpotifyPaused if limit.is_pause else SpotifyRateLimited
    return error(block_message(limit), limit.blocked_until)


def _retry_after(headers):
    try:
        return max(int(headers.get("retry-after", "")), 0)
    except ValueError:
        return None


def _limit_reason(data):
    """The ``reason`` Spotify gives in a 429's JSON body, if any."""
    if not isinstance(data, dict):
        return ""
    error = data.get("error")
    nested = error.get("reason", "") if isinstance(error, dict) else ""
    return str(data.get("reason") or nested or "")


def record_limit(reply, now):
    """Save a 429 as a ``SpotifyLimit`` (the new block), log it, and
    return it."""
    retry_after = _retry_after(reply.headers)
    wait = DEFAULT_RETRY_AFTER if retry_after is None else retry_after
    if _limit_reason(reply.data).upper() == "QUOTA_EXCEEDED":
        reason = Reason.QUOTA
        pause = datetime.timedelta(seconds=retry_after) if retry_after else QUOTA_PAUSE
    elif wait > LONG_WAIT_SECONDS:
        reason, pause = Reason.LONG_WAIT, datetime.timedelta(seconds=wait)
    else:
        reason, pause = Reason.RATE_LIMIT, datetime.timedelta(seconds=wait)
    limit = SpotifyLimit.objects.create(
        occurred_at=now,
        reason=reason,
        retry_after=retry_after,
        blocked_until=now + pause,
    )
    logger.warning(
        "Spotify answered 429 (%s), Retry-After %s; Spotify is blocked until %s.",
        limit.get_reason_display(),
        "not given" if retry_after is None else f"{retry_after} s",
        limit.blocked_until.isoformat(),
    )
    return limit


# --- The client ----------------------------------------------------------------


class SpotifyClient:
    """Calls Spotify under the safeguards above. ``calls`` counts the
    requests sent and ``limits`` keeps every 429 met, for the Search Run."""

    def __init__(
        self, client_id, client_secret, *, sleep=time.sleep, clock=timezone.now
    ):
        if not (client_id and client_secret):
            raise SpotifyNotConfigured(
                "Spotify isn't set up: add SPOTIFY_CLIENT_ID and "
                "SPOTIFY_CLIENT_SECRET to .env."
            )
        self._credentials = (client_id, client_secret)
        self._sleep = sleep
        self._clock = clock
        self._token = None
        self._token_expires = 0.0
        self.calls = 0
        self.limits = []

    @classmethod
    def from_settings(cls, **kwargs):
        return cls(settings.SPOTIFY_CLIENT_ID, settings.SPOTIFY_CLIENT_SECRET, **kwargs)

    # --- Requests --------------------------------------------------------

    def search_tracks(self, phrase, *, genre="", pages=1, market=""):
        """Up to ``pages`` pages of tracks matching ``phrase``."""
        result = SearchResult()
        self._search_pages(search_query(phrase, genre), pages, market, result)
        if genre and not result.tracks:
            result.genre_dropped = True
            self._search_pages(phrase, pages, market, result)
        return result

    def get_track(self, spotify_id):
        return Track.from_api(self._get(f"/tracks/{spotify_id}"))

    def _search_pages(self, query, pages, market, result):
        for page in range(pages):
            offset = page * PAGE_SIZE
            if offset > MAX_OFFSET:
                break
            data = self._get(
                "/search",
                {
                    "q": query,
                    "type": "track",
                    "limit": PAGE_SIZE,
                    "offset": offset,
                    "market": market,
                },
            )
            result.pages_read += 1
            tracks = (data or {}).get("tracks") or {}
            items = [item for item in tracks.get("items") or () if item]
            result.tracks.extend(Track.from_api(item) for item in items)
            if len(items) < PAGE_SIZE or not tracks.get("next"):
                break

    def _get(self, path, params=None):
        refreshed = False
        while True:
            reply = self._call(
                "GET",
                f"{API}{path}",
                headers=lambda: {"Authorization": f"Bearer {self._access_token()}"},
                params=params,
            )
            if reply.status == 401 and not refreshed:
                self._token, refreshed = None, True
                continue
            if not reply.ok:
                raise SpotifyError(_problem(reply))
            return reply.data

    def _call(self, method, url, *, headers, **kwargs):
        """Send one request under the safeguards and return the reply (any
        status but 429). ``headers`` is a function, so a token fetched while
        waiting is used."""
        retried = False
        while True:
            block = current_block(self._clock())
            if block is not None:
                raise blocked_error(block)
            sent_headers = headers()
            try:
                reply = http.request(method, url, headers=sent_headers, **kwargs)
            except http.HttpError as error:
                raise SpotifyError(f"Spotify couldn't be reached ({error}).") from error
            finally:
                self.calls += 1
            if reply.status != 429:
                return reply
            limit = record_limit(reply, self._clock())
            self.limits.append(limit)
            if limit.is_pause or retried or limit.retry_after is None:
                raise blocked_error(limit)
            if limit.retry_after > MAX_WAIT_SECONDS:
                raise blocked_error(limit)
            self._sleep(limit.retry_after)
            retried = True

    def _access_token(self):
        if self._token and time.monotonic() < self._token_expires:
            return self._token
        basic = base64.b64encode(":".join(self._credentials).encode()).decode()
        reply = self._call(
            "POST",
            TOKEN_URL,
            headers=lambda: {"Authorization": f"Basic {basic}"},
            form={"grant_type": "client_credentials"},
        )
        if not reply.ok or not isinstance(reply.data, dict):
            raise SpotifyError(
                "Spotify refused the app's credentials; check SPOTIFY_CLIENT_ID "
                "and SPOTIFY_CLIENT_SECRET in .env."
            )
        self._token = reply.data["access_token"]
        # Renew a minute early so a token never expires mid-request.
        lifetime = int(reply.data.get("expires_in", 3600))
        self._token_expires = time.monotonic() + max(lifetime - 60, 0)
        return self._token


def _problem(reply):
    message = ""
    if isinstance(reply.data, dict):
        error = reply.data.get("error")
        message = error.get("message", "") if isinstance(error, dict) else ""
    return f"Spotify answered {reply.status}" + (f": {message}" if message else ".")
