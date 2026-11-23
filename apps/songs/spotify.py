"""Spotify Web API client: finding songs with the app's own token, and a
user's own account (Authorization Code flow) for playlists and playback.

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
3. No web request waits (workflow review F10): by default a 429 raises
   ``SpotifyRateLimited`` at once, after recording the block. Only the
   search worker passes ``may_wait=True``: a short wait (up to
   ``MAX_WAIT_SECONDS``) is waited out and the request tried once more; a
   second 429, or a longer wait, raises ``SpotifyRateLimited``.
4. ``QUOTA_EXCEEDED``, or a Retry-After over ``LONG_WAIT_SECONDS``, pauses
   Spotify (``SpotifyPaused``): until Retry-After when Spotify gives one,
   otherwise for ``QUOTA_PAUSE``.

A user's tokens pass through this client but are never stored or logged
here; ``apps/songs/connections.py`` keeps them, encrypted.
"""

import base64
import datetime
import logging
import time
import urllib.parse
from dataclasses import dataclass, field

from django.conf import settings
from django.utils import formats, timezone

from apps.core import http

from .models import SpotifyLimit

logger = logging.getLogger(__name__)

API = "https://api.spotify.com/v1"
TOKEN_URL = "https://accounts.spotify.com/api/token"
AUTHORIZE_URL = "https://accounts.spotify.com/authorize"
# Spotify accepts at most this many items in one playlist request.
PLAYLIST_LIMIT = 100
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
    """Spotify couldn't be reached or refused the request. ``status`` is
    Spotify's HTTP status when it answered with an error."""

    def __init__(self, message="", status=None):
        super().__init__(message)
        self.status = status


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


class SpotifyUnauthorized(SpotifyError):
    """Spotify refused a user's access token (401); a refreshed one may work."""


class SpotifyConnectionLost(SpotifyError):
    """Spotify no longer accepts a user's connection (a revoked or unknown
    refresh token, or a refused sign-in code): they must connect again."""


@dataclass(frozen=True)
class UserTokens:
    """Tokens for a user's own account, as Spotify gave them. ``repr``
    leaves the tokens out, so they never reach a log or an error page."""

    access_token: str = field(repr=False)
    refresh_token: str = field(repr=False)
    expires_in: int = 3600
    scope: str = ""

    @classmethod
    def from_api(cls, data, *, refresh_token=""):
        # A refresh may not send a new refresh token; the old one stays good.
        return cls(
            access_token=data["access_token"],
            refresh_token=data.get("refresh_token") or refresh_token,
            expires_in=int(data.get("expires_in", 3600)),
            scope=data.get("scope", ""),
        )


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
        self,
        client_id,
        client_secret,
        *,
        may_wait=False,
        sleep=None,
        clock=timezone.now,
    ):
        if not (client_id and client_secret):
            raise SpotifyNotConfigured(
                "Spotify isn't set up: add SPOTIFY_CLIENT_ID and "
                "SPOTIFY_CLIENT_SECRET to .env."
            )
        self._credentials = (client_id, client_secret)
        # Only the search worker may wait out a short Retry-After (F10).
        self._may_wait = may_wait
        self._sleep = sleep or time.sleep
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
            if not self._may_wait or limit.is_pause or retried:
                raise blocked_error(limit)
            if limit.retry_after is None:
                raise blocked_error(limit)
            if limit.retry_after > MAX_WAIT_SECONDS:
                raise blocked_error(limit)
            self._sleep(limit.retry_after)
            retried = True

    def _basic_auth(self):
        basic = base64.b64encode(":".join(self._credentials).encode()).decode()
        return {"Authorization": f"Basic {basic}"}

    def _access_token(self):
        if self._token and time.monotonic() < self._token_expires:
            return self._token
        reply = self._call(
            "POST",
            TOKEN_URL,
            headers=self._basic_auth,
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

    # --- A user's own account (Authorization Code flow) -------------------

    def authorize_url(self, redirect_uri, state, scopes):
        """Where to send a person to connect their account (no request)."""
        query = urllib.parse.urlencode(
            {
                "client_id": self._credentials[0],
                "response_type": "code",
                "redirect_uri": redirect_uri,
                "scope": " ".join(scopes),
                "state": state,
            }
        )
        return f"{AUTHORIZE_URL}?{query}"

    def exchange_code(self, code, redirect_uri):
        """The tokens for the code Spotify sent back after a person agreed."""
        return self._user_tokens(
            {
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": redirect_uri,
            }
        )

    def refresh_user_token(self, refresh_token):
        """A new access token for a connected account."""
        return self._user_tokens(
            {"grant_type": "refresh_token", "refresh_token": refresh_token},
            refresh_token=refresh_token,
        )

    def create_playlist(self, access_token, name, description="", *, public=False):
        """A new playlist on the account the token belongs to (private
        unless ``public``); returns its ID."""
        data = self._user_api(
            "POST",
            "/me/playlists",
            access_token,
            {"name": name, "description": description, "public": public},
        )
        if not data.get("id"):
            raise SpotifyError("Spotify didn't say which playlist it made.")
        return data["id"]

    def replace_playlist_items(self, access_token, playlist_id, track_ids):
        """Make the playlist hold exactly these tracks, in order."""
        uris = [f"spotify:track:{track_id}" for track_id in track_ids]
        self._user_api(
            "PUT",
            f"/playlists/{playlist_id}/items",
            access_token,
            {"uris": uris[:PLAYLIST_LIMIT]},
        )

    def current_user_id(self, access_token):
        """The Spotify ID of the account the token belongs to. Callers only
        compare it and never store it (AGENTS.md: stored Spotify fields)."""
        return str(self._user_api("GET", "/me", access_token).get("id") or "")

    def playlist_owner_id(self, access_token, playlist_id):
        """The Spotify ID of the playlist's owner, only to compare, never
        stored."""
        data = self._user_api(
            "GET", f"/playlists/{playlist_id}?fields=owner(id)", access_token
        )
        owner = data.get("owner")
        return str(owner.get("id") or "") if isinstance(owner, dict) else ""

    def _user_tokens(self, form, *, refresh_token=""):
        reply = self._call("POST", TOKEN_URL, headers=self._basic_auth, form=form)
        if reply.status in (400, 401) and _token_error(reply) == "invalid_grant":
            raise SpotifyConnectionLost(
                "Spotify no longer accepts this connection. Connect Spotify again."
            )
        if not reply.ok or not isinstance(reply.data, dict):
            raise SpotifyError(_problem(reply))
        if not reply.data.get("access_token"):
            raise SpotifyError("Spotify sent no access token.")
        return UserTokens.from_api(reply.data, refresh_token=refresh_token)

    def _user_api(self, method, path, access_token, json_body=None):
        reply = self._call(
            method,
            f"{API}{path}",
            headers=lambda: {"Authorization": f"Bearer {access_token}"},
            json_body=json_body,
        )
        if reply.status == 401:
            raise SpotifyUnauthorized("Spotify refused the access token.", status=401)
        if not reply.ok:
            raise SpotifyError(_problem(reply), status=reply.status)
        return reply.data if isinstance(reply.data, dict) else {}


def _problem(reply):
    message = ""
    if isinstance(reply.data, dict):
        error = reply.data.get("error")
        message = error.get("message", "") if isinstance(error, dict) else ""
    return f"Spotify answered {reply.status}" + (f": {message}" if message else ".")


def _token_error(reply):
    """The ``error`` code of a token endpoint reply, such as invalid_grant."""
    if isinstance(reply.data, dict) and isinstance(reply.data.get("error"), str):
        return reply.data["error"]
    return ""
