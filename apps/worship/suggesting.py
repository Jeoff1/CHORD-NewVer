"""Song suggestions: from a service's theme to ranked songs placed in its
song slots (pipeline stages 2 to 9).

A Search Run is queued from the service page and carried out by the search
worker (``manage.py run_worker``, decision 0007), never in a web request:
it calls Spotify and LRCLIB one request at a time and runs the ML models.

Stages, with the progress shown on the service page:

1. read the theme: its embedding and the Theme Tags it is about;
2. search phrases from the theme (``phrases.py``);
3. Spotify search for each phrase in each of the church's genres, retried
   without the genre when it finds nothing;
4. cleanup (``apps/songs/cleanup.py``), then new songs join the pool;
5. lyrics for the new songs from LRCLIB;
6. analysis of every pool song with lyrics but no current analysis;
7. ranking of every song that passed the Worship Check (``ranking.py``),
   keeping one version of each song (``versions.py``);
8. sequencing into the template's Song Slots, with feel as a preference
   (``sequencing.py``);
9. explanations, kept with each Suggestion.

``place_again`` places a run's songs again after a person corrects a
song's feel or Worship Check from the suggestions panel.

A run with ``use_spotify`` off skips stages 2 to 5 and ranks the pool.

Spotify's safeguards (``apps/songs/spotify.py``): a 429 stops the run with
a clear message; a quota lockout pauses Spotify, and the run goes on to
rank the songs already in the pool (``fell_back``). Every Spotify call and
429 is recorded on the run. Any other failed outside call ends the run with
a clear message.
"""

import datetime
import logging

from django.db import transaction
from django.utils import timezone

from apps.songs.analysis import MAX_TAGS, TAG_THRESHOLD, analyse_song, tag_label
from apps.songs.cleanup import clean_tracks
from apps.songs.lyrics import LrclibClient
from apps.songs.ml import EngineUnavailable, get_engine
from apps.songs.models import Song, ThemeTag
from apps.songs.pool import add_from_spotify, fetch_lyrics
from apps.songs.spotify import SpotifyClient, SpotifyError, SpotifyPaused

from . import ranking, scheduling, sequencing, versions
from .models import SearchRun, Season, Suggestion, SuggestionSettings
from .phrases import search_phrases

logger = logging.getLogger(__name__)
Status = SearchRun.Status
# A run waiting longer than this suggests the search worker isn't running.
QUEUE_WARNING = datetime.timedelta(minutes=2)


class RunRefused(Exception):
    """A run can't be started; the message says why."""


class RunFailed(Exception):
    """A run stopped; the message is shown on the service page."""


# --- Queue -------------------------------------------------------------------


def planning_closed(service):
    """Why songs can't be planned for ``service`` any more, or "" when they
    can: a cancelled or past service gets no suggestions and no new lineup
    (workflow review F7)."""
    from apps.church.models import ChurchProfile

    if not (service.is_cancelled or service.has_started):
        return ""
    word = ChurchProfile.load().label_set.get("worship_service").lower()
    if service.is_cancelled:
        return f"This {word} is cancelled, so no songs are planned for it."
    return f"This {word} has already taken place, so no songs are planned for it."


def request_run(service, user, *, use_spotify=True):
    """Queue a Search Run for ``service``. Refused for a cancelled or past
    service, without a theme, or while another run for the service is
    waiting or running."""
    closed = planning_closed(service)
    if closed:
        raise RunRefused(closed)
    if service.posted_theme is None:
        raise RunRefused("Post the service's theme first: suggestions start from it.")
    with transaction.atomic():
        busy = (
            SearchRun.objects.select_for_update()
            .filter(service=service, status__in=[Status.QUEUED, Status.RUNNING])
            .exists()
        )
        if busy:
            raise RunRefused("Songs are already being found for this service.")
        return SearchRun.objects.create(
            service=service,
            requested_by=user,
            use_spotify=use_spotify,
            stage="Waiting for the search worker",
        )


def claim_next_run():
    """The oldest waiting run, now marked running; None when none waits.
    Rows are locked with SKIP LOCKED, so two workers never take one run."""
    with transaction.atomic():
        run = (
            SearchRun.objects.select_for_update(skip_locked=True)
            .filter(status=Status.QUEUED)
            .order_by("created_at", "pk")
            .first()
        )
        if run is None:
            return None
        run.status = Status.RUNNING
        run.started_at = timezone.now()
        run.stage = "Starting"
        run.save(update_fields=["status", "started_at", "stage"])
        return run


def fail_stale_runs():
    """Runs left "running" by a worker that stopped. Call when a worker
    starts, before it claims anything."""
    return SearchRun.objects.filter(status=Status.RUNNING).update(
        status=Status.FAILED,
        finished_at=timezone.now(),
        message="The search worker stopped during this run. Start it again "
        "and ask for suggestions again.",
    )


# --- Carrying out a run ------------------------------------------------------


class _Progress:
    def __init__(self, run):
        self.run = run

    def __call__(self, percent, stage, **counts):
        run = self.run
        run.progress, run.stage = percent, stage[:200]
        for name, value in counts.items():
            setattr(run, name, value)
        run.save(update_fields=["progress", "stage", *counts])


def execute(run, *, spotify=None, lyrics_client=None, engine=None):
    """Carry out a claimed run to the end; it finishes done or failed.
    Times in its messages are in the church's time zone."""
    with timezone.override(scheduling.church_time_zone()):
        try:
            _execute(run, spotify, lyrics_client, engine)
        except (RunFailed, SpotifyError, EngineUnavailable) as error:
            _finish(run, Status.FAILED, str(error))
        except Exception:
            logger.exception("Search run %s failed", run.pk)
            _finish(
                run,
                Status.FAILED,
                "Something unexpected went wrong; the search worker's log has the "
                "details.",
            )
    return run


def _finish(run, status, message):
    run.status = status
    run.message = message
    run.finished_at = timezone.now()
    if status == Status.DONE:
        run.progress, run.stage = 100, "Done"
    run.save(update_fields=["status", "message", "finished_at", "progress", "stage"])


def _execute(run, spotify, lyrics_client, engine):
    progress = _Progress(run)
    service = run.service
    theme = service.posted_theme
    if theme is None:
        raise RunFailed(
            "The service's theme was removed, so there is nothing to match."
        )
    options = SuggestionSettings.load()
    run.weights = options.weights()
    run.save(update_fields=["weights"])

    progress(2, "Reading the theme")
    engine = engine or get_engine()
    text = theme.text()
    theme_vector = engine.embed([text])[0]
    progress(5, "Reading the theme", theme_tags=theme_tag_ids(text, engine))

    note = ""
    if run.use_spotify:
        spotify = spotify or SpotifyClient.from_settings()
        try:
            new_songs = _find_on_spotify(run, theme, options, spotify, engine, progress)
        except SpotifyPaused as pause:
            # Rule 5: a quota lockout must not stop suggestions.
            new_songs, note = [], str(pause)
            run.fell_back = True
            run.save(update_fields=["fell_back"])
        finally:
            _record_spotify_usage(run, spotify)
        _fetch_lyrics(new_songs, lyrics_client or LrclibClient(), progress)

    _analyse_pool(engine, progress)

    progress(92, "Ranking the songs")
    suggestions = _rank(run, theme_vector, options, engine)
    if not suggestions:
        raise RunFailed(
            " ".join(
                part
                for part in (
                    note,
                    "No songs could be ranked: no song in the pool has passed "
                    "the worship check yet.",
                    "Try searching Spotify." if not run.use_spotify else "",
                )
                if part
            )
        )
    _finish(run, Status.DONE, " ".join(part for part in (note, _summary(run)) if part))


def _record_spotify_usage(run, spotify):
    run.spotify_calls = spotify.calls
    run.spotify_limits = [
        {
            "at": limit.occurred_at.isoformat(),
            "reason": limit.reason,
            "retry_after": limit.retry_after,
        }
        for limit in spotify.limits
    ]
    run.save(update_fields=["spotify_calls", "spotify_limits"])


def theme_tag_ids(text, engine):
    """The Theme Tags a theme is about, best first."""
    tags = list(ThemeTag.objects.active())
    if not tags:
        return []
    scores = engine.score(text, [tag_label(tag) for tag in tags])
    fitting = [(s, t.pk) for s, t in zip(scores, tags) if s >= TAG_THRESHOLD]
    return [pk for _, pk in sorted(fitting, reverse=True)[:MAX_TAGS]]


def _find_on_spotify(run, theme, options, spotify, engine, progress):
    progress(8, "Choosing search phrases")
    phrases = search_phrases(
        theme.title, theme.text(), options.phrases_per_theme, engine
    )
    if not phrases:
        raise RunFailed("The theme has no words to search for; add a title or notes.")
    progress(10, "Searching Spotify", phrases=phrases)

    genres = options.genres() or [""]
    searches = [(phrase, genre) for phrase in phrases for genre in genres]
    tracks, pages, record = [], 0, []
    for done, (phrase, genre) in enumerate(searches):
        progress(
            10 + 30 * done // len(searches),
            f'Searching Spotify for "{phrase}"' + (f" in {genre}" if genre else ""),
            pages_read=pages,
        )
        result = spotify.search_tracks(
            phrase, genre=genre, pages=options.pages_per_phrase, market=options.market
        )
        pages += result.pages_read
        tracks.extend(result.tracks)
        # Information only: never used to decide anything about a song.
        record.append(
            {
                "phrase": phrase,
                "genre": genre,
                "pages": result.pages_read,
                "found": len(result.tracks),
                "genre_dropped": result.genre_dropped,
            }
        )
        run.searches = record
        run.save(update_fields=["searches"])

    cleaned = clean_tracks(tracks)
    added, new_songs = 0, []
    for track in cleaned:
        song, created = add_from_spotify(track)
        added += created
        if song.lyrics_status == Song.LyricsStatus.PENDING:
            new_songs.append(song)
    progress(
        40,
        "Adding songs",
        pages_read=pages,
        songs_found=len(cleaned),
        songs_added=added,
    )
    return new_songs


def _fetch_lyrics(songs, client, progress):
    for done, song in enumerate(songs):
        progress(40 + 30 * done // len(songs), f"Looking up lyrics: {song.title}")
        fetch_lyrics(song, client)


def _analyse_pool(engine, progress):
    """Analyse every song with lyrics whose analysis is missing or from
    another engine (embeddings from different engines don't compare)."""
    stale = list(
        Song.objects.filter(lyrics_status=Song.LyricsStatus.FOUND)
        .exclude(analysed_with=engine.name, analysed_at__isnull=False)
        .order_by("pk")
    )
    for done, song in enumerate(stale):
        progress(70 + 20 * done // len(stale), f"Analysing lyrics: {song.title}")
        analyse_song(song, engine)
    progress(90, "Lyrics analysed", songs_analysed=len(stale))


def _rank(run, theme_vector, options, engine):
    service = run.service
    day = service.local_date
    songs = (
        Song.objects.accepted()
        .filter(analysed_with=engine.name)
        .exclude(embedding=[])
        .prefetch_related("tags")
    )
    seasons = [
        season
        for season in Season.objects.active().prefetch_related("tags")
        if season.contains(day)
    ]
    ranked = ranking.rank(
        songs,
        theme_vector=theme_vector,
        day=day,
        weights=run.weights,
        theme_tags=run.theme_tags,
        seasons=seasons,
        usage=ranking.song_usage(service),
        window_weeks=options.repeat_window_weeks,
        similarity_range=getattr(engine, "similarity_range", (0.0, 1.0)),
    )
    distinct = versions.group(ranked)
    kept = distinct[: options.suggestions_kept]
    placements = {
        p.index: p
        for p in sequencing.place(
            kept, service.template.slots.all(), feel_weight=feel_weight(run)
        )
    }
    rows = []
    for index, item in enumerate(kept):
        placement = placements.get(index)
        rows.append(
            Suggestion(
                run=run,
                song=item.song,
                rank=index + 1,
                score=item.score,
                relevance=item.relevance,
                familiarity=item.familiarity,
                season=item.season,
                recency=item.recency,
                match=item.match,
                slot=placement.slot if placement else None,
                slot_reason=placement.reason if placement else "",
                reasons=list(item.reasons),
            )
        )
    with transaction.atomic():
        Suggestion.objects.bulk_create(rows)
        run.songs_ranked = len(distinct)
        run.save(update_fields=["songs_ranked"])
    return kept


def feel_weight(run):
    """The feel weight the run used (runs before it existed had none)."""
    return (run.weights or {}).get("feel", SuggestionSettings().weight_feel)


def place_again(run):
    """Place the run's songs in the slots again, after a person corrected a
    song's feel or its Worship Check. Songs that no longer pass the check
    are left out; the ranking stays as it was."""
    suggestions = list(run.suggestions.select_related("song").order_by("rank"))
    candidates = [
        s for s in suggestions if s.song.worship_check == Song.WorshipCheck.ACCEPTED
    ]
    placements = {
        p.index: p
        for p in sequencing.place(
            candidates, run.service.template.slots.all(), feel_weight=feel_weight(run)
        )
    }
    for suggestion in suggestions:
        suggestion.slot, suggestion.slot_reason = None, ""
    for index, placement in placements.items():
        candidates[index].slot = placement.slot
        candidates[index].slot_reason = placement.reason
    Suggestion.objects.bulk_update(suggestions, ["slot", "slot_reason"])


def _summary(run):
    parts = []
    if run.use_spotify and not run.fell_back:
        parts.append(
            f"Searched {len(run.phrases)} phrase{'s' if len(run.phrases) != 1 else ''} "
            f"({run.pages_read} pages): {run.songs_found} songs found, "
            f"{run.songs_added} new."
        )
    parts.append(f"Ranked {run.songs_ranked} worship songs from the pool.")
    return " ".join(parts)


# --- Reading results ---------------------------------------------------------


def latest_run(service):
    return service.search_runs.order_by("-created_at", "-pk").first()


def results(run):
    """(placed, others): Suggestions placed in slots, in slot order, and the
    other ranked songs. Songs a person has since marked as not worship songs
    are left out."""
    suggestions = list(
        run.suggestions.select_related("song", "slot")
        .prefetch_related("song__tags")
        .filter(song__worship_check=Song.WorshipCheck.ACCEPTED)
    )
    placed = sorted(
        (s for s in suggestions if s.slot_id),
        key=lambda s: (s.slot.position, s.slot.pk),
    )
    others = [s for s in suggestions if not s.slot_id]
    return placed, others


def worker_seems_stopped(run, now=None):
    """Whether a run has waited so long that the search worker is probably
    not running (the page then says how to start it)."""
    now = now or timezone.now()
    return run.status == Status.QUEUED and now - run.created_at > QUEUE_WARNING
