"""Each user's own Spotify account (Design-Decisions, Phase 7).

- People connect with Spotify's Authorization Code flow. The ``state``
  sent to Spotify is kept in the session and checked when Spotify sends
  the person back, so nobody can attach their account to someone else's.
- The access and refresh tokens are stored **encrypted** with Fernet; the
  key is ``SPOTIFY_TOKEN_KEY`` in ``.env``. They are never shown, logged
  or put in the audit trail. The playback page's own script receives the
  user's short-lived access token, because Spotify's Web Playback SDK
  runs in the browser; the refresh token never leaves the server.
- An access token is refreshed when it has under a minute left, or when
  Spotify refuses it once. A refresh Spotify no longer accepts, or a key
  that can't read the stored tokens, removes the connection: the person
  connects again.
- Every call goes through ``SpotifyClient``, so its safeguards apply, and
  in a web request a 429 fails fast (workflow review F10).
"""

import datetime
import secrets

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.debug import sensitive_variables

from .models import SpotifyConnection
from .spotify import SpotifyConnectionLost, SpotifyError, SpotifyUnauthorized

# What CHORD asks for: playback in the browser (the Web Playback SDK needs
# the first three; starting a track needs the fourth) and private playlists.
SCOPES = (
    "streaming",
    "user-read-email",
    "user-read-private",
    "user-modify-playback-state",
    "playlist-modify-private",
)
SESSION_KEY = "spotify_connect"
# Refresh an access token this long before it runs out.
REFRESH_MARGIN = datetime.timedelta(seconds=60)


class SpotifyNotConnected(SpotifyError):
    """The user has no usable Spotify connection."""


def is_configured():
    """Connecting needs the app's credentials and the token key."""
    return bool(
        settings.SPOTIFY_CLIENT_ID
        and settings.SPOTIFY_CLIENT_SECRET
        and settings.SPOTIFY_TOKEN_KEY
    )


# --- Encryption ------------------------------------------------------------------


def _fernet():
    return Fernet(settings.SPOTIFY_TOKEN_KEY.encode())


@sensitive_variables("token")
def encrypt(token):
    return _fernet().encrypt(token.encode()).decode()


@sensitive_variables("token")
def decrypt(stored):
    """The plain token; ``InvalidToken`` when the key can't read it."""
    return _fernet().decrypt(stored.encode()).decode()


# --- Connecting -----------------------------------------------------------------


def connection_for(user):
    if not getattr(user, "is_authenticated", False):
        return None
    return SpotifyConnection.objects.filter(user=user).first()


def is_connected(user):
    return is_configured() and connection_for(user) is not None


def redirect_uri(request):
    return settings.SPOTIFY_REDIRECT_URI or request.build_absolute_uri(
        reverse("songs:spotify_callback")
    )


def start(request, client, next_url):
    """Remember a new ``state`` (and where to go afterwards) in the session,
    and return the Spotify page where the person agrees."""
    state = secrets.token_urlsafe(32)
    request.session[SESSION_KEY] = {"state": state, "next": next_url}
    return client.authorize_url(redirect_uri(request), state, SCOPES)


def take_pending(request, state):
    """Where to go after connecting, if ``state`` is the one this session
    sent to Spotify; None when it isn't (or nothing was sent). Either way
    the state can't be used again."""
    pending = request.session.pop(SESSION_KEY, None) or {}
    expected = pending.get("state") or ""
    if not (state and expected and secrets.compare_digest(state, expected)):
        return None
    return pending.get("next") or ""


@sensitive_variables("tokens")
def _store(connection, tokens, now):
    connection.access_token_encrypted = encrypt(tokens.access_token)
    connection.refresh_token_encrypted = encrypt(tokens.refresh_token)
    connection.expires_at = now + datetime.timedelta(seconds=tokens.expires_in)
    if tokens.scope:
        connection.scope = tokens.scope


@sensitive_variables("tokens", "code")
def finish(user, code, uri, client):
    """Swap Spotify's code for tokens and save them, encrypted, as the
    user's connection (replacing any earlier one)."""
    tokens = client.exchange_code(code, uri)
    if not tokens.refresh_token:
        raise SpotifyError("Spotify sent no refresh token; try connecting again.")
    connection = connection_for(user) or SpotifyConnection(user=user)
    _store(connection, tokens, timezone.now())
    connection.save()
    return connection


def disconnect(user):
    """Forget the user's connection; True when there was one."""
    deleted, _ = SpotifyConnection.objects.filter(user=user).delete()
    return bool(deleted)


# --- Using the connection --------------------------------------------------------


@sensitive_variables("tokens")
def access_token(connection, client, *, force_refresh=False):
    """A usable access token, refreshed (and saved) when it is about to run
    out. Raises ``SpotifyNotConnected`` when the connection can't be used
    any more (it is then removed)."""
    try:
        if (
            not force_refresh
            and timezone.now() + REFRESH_MARGIN < connection.expires_at
        ):
            return decrypt(connection.access_token_encrypted)
        refresh = decrypt(connection.refresh_token_encrypted)
    except InvalidToken:
        connection.delete()
        raise SpotifyNotConnected(
            "Your Spotify connection can't be read any more. Connect Spotify again."
        ) from None
    try:
        tokens = client.refresh_user_token(refresh)
    except SpotifyConnectionLost as lost:
        connection.delete()
        raise SpotifyNotConnected(str(lost)) from None
    _store(connection, tokens, timezone.now())
    connection.save()
    return tokens.access_token


def call_with_token(connection, client, call):
    """Run ``call(access_token)``. When Spotify refuses the token, refresh
    it and try once more."""
    try:
        return call(access_token(connection, client))
    except SpotifyUnauthorized:
        return call(access_token(connection, client, force_refresh=True))
