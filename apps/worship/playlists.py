"""Saving a confirmed lineup as its Lineup Playlist (Design-Decisions,
Phase 7; decisions 0010 and 0011).

- **Where it goes.** When the Church Spotify Account is connected, every
  Lineup Playlist is made and updated there, as a public playlist, whoever
  confirms or presses "Save to Spotify". Otherwise it goes to the account
  of the person who confirms (or presses the button), as a private
  playlist.
- **One playlist per lineup.** Each service's lineup has its own playlist,
  named with the service name and date. Saving again (confirming after a
  reopen, or "Save to Spotify") updates that lineup's own playlist when it
  is on the same account: the church's, or the same person's. Other
  services' playlists are never touched. The playlist ID is kept only to
  find and update the playlist (decision 0010).
- **Made again only when it's gone for this account** (Design-Decisions,
  Phase 8): on a 404, or on a 403 when the connected account doesn't own
  the stored playlist. Only then, CHORD asks Spotify for both account IDs,
  compares them and stores neither. Any other 403 is a refusal.
- **Never in the way.** Saving never stops a confirmation. With no
  connection, an unusable church account, a Spotify block or a 429, nothing
  waits (workflow review F10): the lineup stays confirmed and the page
  offers "Save to Spotify" to people who may save.
- Only songs with a Spotify track ID go in, in lineup order.
"""

from dataclasses import dataclass

from django.db import transaction
from django.utils import formats, timezone

from apps.songs import connections
from apps.songs.spotify import SpotifyClient, SpotifyError, SpotifyRateLimited

from .models import Lineup

FAILED = "The Spotify playlist wasn't saved"
CHURCH_LOST = "The church's Spotify account needs connecting again in church settings."
NOT_FOUND = 404
FORBIDDEN = 403


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


def needs_saving(lineup, tracks=None, *, church=None):
    """A confirmed lineup with Spotify tracks that no playlist holds yet,
    whose songs changed since it was saved, or whose playlist isn't on the
    Church Spotify Account now that one is connected."""
    if not lineup.is_confirmed:
        return False
    tracks = track_ids(lineup) if tracks is None else tracks
    if not tracks:
        return False
    if church is None:
        church = connections.church_account(lineup.service.church) is not None
    if church and not lineup.spotify_playlist_on_church_account:
        return True
    return lineup.spotify_playlist_tracks != tracks


def may_save(user):
    """The people who confirm lineups save them to Spotify."""
    from .lineups import CHANGE, FINAL_SAY

    return user.has_perm(CHANGE) or user.has_perm(FINAL_SAY)


def playlist_name(lineup):
    """The service name and date, such as "Sunday Church – Nov 29"."""
    service = lineup.service
    return f"{service.name} – {formats.date_format(service.local_date, 'M j')}"


def _description(lineup):
    word = lineup.service.church.label_set.get("lineup")
    return f"{word} saved from CHORD."


def save(lineup, user, *, client=None):
    """Save the lineup as its Lineup Playlist: on the Church Spotify Account
    when it is connected, otherwise on ``user``'s own account. Never raises
    for Spotify's sake; the outcome says what happened, for the person."""
    if not lineup.is_confirmed or not connections.is_configured():
        return Outcome(False)
    church = connections.church_account(lineup.service.church)
    connection = church or connections.connection_for(user)
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
    on_church = church is not None
    try:
        client = client or SpotifyClient.from_settings()
        connections.call_with_token(
            connection,
            client,
            lambda token: _write(lineup, user, tracks, token, client, on_church),
        )
    except connections.SpotifyNotConnected as lost:
        return Outcome(False, f"{FAILED}. {CHURCH_LOST if on_church else lost}")
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
    where = "the church's Spotify account" if on_church else "your Spotify"
    return Outcome(True, f'Saved to {where} as "{playlist_name(lineup)}".{note}')


def _is_own_playlist(lineup, user, on_church):
    """Whether the lineup's stored playlist is on the account saving now."""
    if not lineup.spotify_playlist_id:
        return False
    if on_church:
        return lineup.spotify_playlist_on_church_account
    return (
        not lineup.spotify_playlist_on_church_account
        and lineup.spotify_playlist_owner_id == user.pk
    )


def _write(lineup, user, tracks, token, client, on_church):
    if _is_own_playlist(lineup, user, on_church):
        try:
            client.replace_playlist_items(token, lineup.spotify_playlist_id, tracks)
        except SpotifyRateLimited:
            raise
        except SpotifyError as error:
            if not _is_gone(error, client, token, lineup.spotify_playlist_id):
                raise
        else:
            _record(lineup, tracks=tracks)
            return
    playlist_id = client.create_playlist(
        token, playlist_name(lineup), _description(lineup), public=on_church
    )
    # Kept at once, so a 429 on the next call doesn't leave a playlist that
    # saving again would make a second time.
    _record(
        lineup,
        playlist_id=playlist_id,
        owner=None if on_church else user,
        on_church=on_church,
        tracks=[],
    )
    client.replace_playlist_items(token, playlist_id, tracks)
    _record(lineup, tracks=tracks)


def _is_gone(error, client, token, playlist_id):
    """Whether Spotify's refusal to update the stored playlist means it is
    gone for this account, so a new one should be made: a 404, or a 403 on
    a playlist the connected account doesn't own. Any other answer is a
    refusal. A 429 on a lookup raises ``SpotifyRateLimited`` (fail fast)."""
    if error.status == NOT_FOUND:
        return True
    if error.status != FORBIDDEN:
        return False
    # Both IDs are only compared here, never stored (decision 0010).
    try:
        owner = client.playlist_owner_id(token, playlist_id)
        if not owner:
            return False
        return owner != client.current_user_id(token)
    except SpotifyRateLimited:
        raise
    except SpotifyError as lookup:
        return lookup.status == NOT_FOUND


def _record(lineup, **fields):
    updates = {
        "spotify_playlist_saved_at": timezone.now(),
        "spotify_playlist_tracks": fields["tracks"],
    }
    if "playlist_id" in fields:
        updates["spotify_playlist_id"] = fields["playlist_id"]
        updates["spotify_playlist_owner"] = fields["owner"]
        updates["spotify_playlist_on_church_account"] = fields["on_church"]
    with transaction.atomic():
        Lineup.objects.filter(pk=lineup.pk).update(**updates)
    for name, value in updates.items():
        setattr(lineup, name, value)
