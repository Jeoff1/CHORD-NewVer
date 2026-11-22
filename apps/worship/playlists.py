"""Saving a confirmed lineup as a Spotify playlist (Design-Decisions,
Phase 7).

- Confirming a lineup saves it at once on the Spotify account of the person
  who confirmed it. The "Save to Spotify" button does the same later, on
  the account of the person who presses it.
- Saving never stops a confirmation. With no connection, during a Spotify
  block, or on a 429, nothing waits (workflow review F10): the lineup stays
  confirmed and the page offers "Save to Spotify".
- A person saving again updates their own playlist instead of making
  another; anyone else gets a new playlist on their own account.
- Only songs with a Spotify track ID go in, in lineup order. The playlist
  is private.
"""

from dataclasses import dataclass

from django.db import transaction
from django.utils import formats, timezone

from apps.church.models import ChurchProfile
from apps.songs import connections
from apps.songs.spotify import SpotifyClient, SpotifyError, SpotifyRateLimited

from .models import Lineup

FAILED = "The Spotify playlist wasn't saved"


@dataclass(frozen=True)
class Outcome:
    saved: bool
    message: str = ""


def track_ids(lineup):
    """The lineup's Spotify tracks in order; songs not on Spotify are left out."""
    return [
        item.song.spotify_id
        for item in lineup.items.select_related("song").order_by("position", "pk")
        if item.song.spotify_id
    ]


def needs_saving(lineup, tracks=None):
    """A confirmed lineup with Spotify tracks that no playlist holds yet, or
    whose songs changed since it was saved."""
    if not lineup.is_confirmed:
        return False
    tracks = track_ids(lineup) if tracks is None else tracks
    return bool(tracks) and lineup.spotify_playlist_tracks != tracks


def may_save(user):
    """The people who confirm lineups save them to Spotify."""
    from .lineups import CHANGE, FINAL_SAY

    return user.has_perm(CHANGE) or user.has_perm(FINAL_SAY)


def playlist_name(lineup):
    service = lineup.service
    return f"{service.name}, {formats.date_format(service.local_date, 'M j, Y')}"


def _description(lineup):
    word = ChurchProfile.load().label_set.get("lineup")
    return f"{word} saved from CHORD."


def save(lineup, user, *, client=None):
    """Save the lineup to ``user``'s Spotify account. Never raises for
    Spotify's sake; the outcome says what happened, for the person."""
    if not lineup.is_confirmed or not connections.is_configured():
        return Outcome(False)
    connection = connections.connection_for(user)
    if connection is None:
        return Outcome(
            False,
            "Connect your Spotify account, then use Save to Spotify to save "
            "it as a playlist.",
        )
    tracks = track_ids(lineup)
    if not tracks:
        return Outcome(
            False, "None of its songs are on Spotify, so no playlist was made."
        )
    try:
        client = client or SpotifyClient.from_settings()
        connections.call_with_token(
            connection,
            client,
            lambda token: _write(lineup, user, tracks, token, client),
        )
    except connections.SpotifyNotConnected as lost:
        return Outcome(False, f"{FAILED}. {lost}")
    except SpotifyRateLimited as limit:
        return Outcome(False, f"{FAILED}. {limit}")
    except SpotifyError as error:
        return Outcome(False, f"{FAILED}: {error} Use Save to Spotify to try again.")
    skipped = lineup.items.count() - len(tracks)
    note = (
        f" {skipped} song{'s' if skipped != 1 else ''} not on Spotify "
        f"{'were' if skipped != 1 else 'was'} left out."
        if skipped
        else ""
    )
    return Outcome(True, f'Saved to your Spotify as "{playlist_name(lineup)}".{note}')


def _write(lineup, user, tracks, token, client):
    playlist_id = lineup.spotify_playlist_id
    if not playlist_id or lineup.spotify_playlist_owner_id != user.pk:
        playlist_id = client.create_playlist(
            token, playlist_name(lineup), _description(lineup)
        )
        # Kept at once, so a 429 on the next call doesn't leave a playlist
        # that saving again would make a second time.
        _record(lineup, playlist_id=playlist_id, owner=user, tracks=[])
    client.replace_playlist_items(token, playlist_id, tracks)
    _record(lineup, tracks=tracks)


def _record(lineup, **fields):
    updates = {"spotify_playlist_saved_at": timezone.now()}
    if "playlist_id" in fields:
        updates["spotify_playlist_id"] = fields["playlist_id"]
        updates["spotify_playlist_owner"] = fields["owner"]
    updates["spotify_playlist_tracks"] = fields["tracks"]
    with transaction.atomic():
        Lineup.objects.filter(pk=lineup.pk).update(**updates)
    for name, value in updates.items():
        setattr(lineup, name, value)
