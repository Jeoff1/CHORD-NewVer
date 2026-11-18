"""Spotify Web API client for finding songs (the app's own token).

Spotify decides which songs get checked and plays them; nothing it returns
is ever model input (see AGENTS.md). Credentials come from ``.env``.

- Search returns at most 10 tracks a page (Development Mode); the offset
  stops at 1000.
- A search with a genre filter that finds nothing is run again without it,
  because ``genre:`` filters often match nothing.
"""

import base64
import time
from dataclasses import dataclass, field

from django.conf import settings

from apps.core import http

API = "https://api.spotify.com/v1"
TOKEN_URL = "https://accounts.spotify.com/api/token"
PAGE_SIZE = 10
MAX_OFFSET = 1000
# The longest Retry-After the client waits out before giving up.
MAX_WAIT_SECONDS = 30


class SpotifyError(Exception):
    """Spotify couldn't be reached or refused the request."""


class SpotifyNotConfigured(SpotifyError):
    pass


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


class SpotifyClient:
    def __init__(self, client_id, client_secret, *, sleep=time.sleep):
        if not (client_id and client_secret):
            raise SpotifyNotConfigured(
                "Spotify isn't set up: add SPOTIFY_CLIENT_ID and "
                "SPOTIFY_CLIENT_SECRET to .env."
            )
        self._credentials = (client_id, client_secret)
        self._sleep = sleep
        self._token = None
        self._token_expires = 0.0

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
        refreshed = waited = False
        while True:
            reply = self._send("GET", f"{API}{path}", params=params)
            if reply.status == 401 and not refreshed:
                self._token, refreshed = None, True
                continue
            if reply.status == 429 and not waited:
                wait = _retry_after(reply.headers)
                if wait <= MAX_WAIT_SECONDS:
                    self._sleep(wait)
                    waited = True
                    continue
            if not reply.ok:
                raise SpotifyError(_problem(reply))
            return reply.data

    def _send(self, method, url, **kwargs):
        headers = {"Authorization": f"Bearer {self._access_token()}"}
        try:
            return http.request(method, url, headers=headers, **kwargs)
        except http.HttpError as error:
            raise SpotifyError(f"Spotify couldn't be reached ({error}).") from error

    def _access_token(self):
        if self._token and time.monotonic() < self._token_expires:
            return self._token
        basic = base64.b64encode(":".join(self._credentials).encode()).decode()
        try:
            reply = http.request(
                "POST",
                TOKEN_URL,
                headers={"Authorization": f"Basic {basic}"},
                form={"grant_type": "client_credentials"},
            )
        except http.HttpError as error:
            raise SpotifyError(f"Spotify couldn't be reached ({error}).") from error
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


def _retry_after(headers):
    try:
        return max(int(headers.get("retry-after", "1")), 0)
    except ValueError:
        return 1


def _problem(reply):
    message = ""
    if isinstance(reply.data, dict):
        error = reply.data.get("error")
        message = error.get("message", "") if isinstance(error, dict) else ""
    if reply.status == 429:
        return "Spotify is limiting requests; try again in a few minutes."
    return f"Spotify answered {reply.status}" + (f": {message}" if message else ".")
