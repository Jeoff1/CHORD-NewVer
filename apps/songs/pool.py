"""Rules for the song pool: adding songs found on Spotify, fetching their
lyrics, and working through the songs that still need lyrics or analysis.

Fetching and analysing run outside web requests (``manage.py
process_songs`` now, the search worker from Phase 5), because LRCLIB wants
one request at a time and web requests never load a model.
"""

from dataclasses import dataclass

from django.utils import timezone

from .analysis import analyse_song
from .lyrics import LyricsError
from .models import Song

SONG_AUDIT_FIELDS = {
    "Title": "title",
    "Artist": "artist",
    "Album": "album",
    "Spotify track ID": "spotify_id",
    "Lyrics": lambda song: song.get_lyrics_status_display(),
    "Worship check": lambda song: song.get_worship_check_display(),
    "Feel": lambda song: song.get_feel_display(),
    "Theme tags": lambda song: [tag.name for tag in song.tags.all()],
    "The team knows it": "team_knows",
}


def add_from_spotify(track, church):
    """The church's song for a Spotify track, added to its pool if new.
    Returns ``(song, created)``."""
    return Song.objects.get_or_create(
        church=church,
        spotify_id=track.spotify_id,
        defaults={
            "title": track.title[:300],
            "artist": track.artist[:300],
            "album": track.album[:300],
            "length_seconds": track.length_seconds,
        },
    )


def primary_artist(artist):
    return artist.split(",")[0].strip()


# Lookups whose answer another church may reuse (decision 0014, question 1).
SETTLED_LOOKUPS = (
    Song.LyricsStatus.FOUND,
    Song.LyricsStatus.MISSING,
    Song.LyricsStatus.INSTRUMENTAL,
)


def earlier_lookup(song):
    """Another church's settled LRCLIB lookup of the same Spotify track, or
    None. LRCLIB asks for every result to be cached, so CHORD asks it once
    per track across the platform (decision 0014): the copy stays inside
    the installation, and is never shown to the other church."""
    if not song.spotify_id:
        return None
    return (
        Song.objects.exclude(church_id=song.church_id)
        .filter(spotify_id=song.spotify_id, lyrics_status__in=SETTLED_LOOKUPS)
        .exclude(lyrics_checked_at=None)
        .order_by("-lyrics_checked_at")
        .first()
    )


def fetch_lyrics(song, client):
    """Look up the song's lyrics and save what was found. A track another
    church already looked up reuses that answer instead of asking LRCLIB
    again. A song whose lyrics change is analysed again."""
    earlier = earlier_lookup(song)
    if earlier is not None:
        status, lyrics = earlier.lyrics_status, earlier.lyrics
    else:
        try:
            result = client.lookup(
                song.title,
                primary_artist(song.artist),
                song.album,
                song.length_seconds,
            )
            status, lyrics = result.status, result.lyrics
        except LyricsError:
            status, lyrics = Song.LyricsStatus.FAILED, song.lyrics
    if lyrics != song.lyrics:
        song.analysed_at = None
    song.lyrics, song.lyrics_status = lyrics, status
    song.lyrics_checked_at = timezone.now()
    song.save(
        update_fields=[
            "lyrics",
            "lyrics_status",
            "lyrics_checked_at",
            "analysed_at",
            "updated_at",
        ]
    )
    return song


def check_again(song):
    """Queue the song for a fresh lyrics lookup and analysis."""
    song.lyrics_status = Song.LyricsStatus.PENDING
    song.analysed_at = None
    song.save(update_fields=["lyrics_status", "analysed_at", "updated_at"])


@dataclass
class ProcessResult:
    lyrics_found: int = 0
    lyrics_missing: int = 0
    lyrics_failed: int = 0
    analysed: int = 0


def process_pending(*, lyrics_client, engine=None, limit=None, report=None):
    """Fetch lyrics for songs that need them, then analyse songs whose
    lyrics are new. ``engine`` may be a callable returning the engine, so
    it is loaded only when there is something to analyse."""
    report = report or (lambda message: None)
    result = ProcessResult()
    for song in _batch(Song.objects.needs_lyrics(), limit):
        fetch_lyrics(song, lyrics_client)
        if song.lyrics_status == Song.LyricsStatus.FOUND:
            result.lyrics_found += 1
        elif song.lyrics_status == Song.LyricsStatus.FAILED:
            result.lyrics_failed += 1
        else:
            result.lyrics_missing += 1
        report(f"Lyrics: {song} - {song.get_lyrics_status_display()}")

    pending = _batch(Song.objects.needs_analysis(), limit)
    if pending and callable(engine):
        engine = engine()
    for song in pending:
        analyse_song(song, engine)
        result.analysed += 1
        report(f"Analysed: {song} - {song.get_worship_check_display()}")
    return result


def _batch(queryset, limit):
    queryset = queryset.order_by("created_at", "pk")
    return list(queryset[:limit] if limit else queryset)
