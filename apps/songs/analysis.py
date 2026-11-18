"""Song analysis: what a song's lyrics say about it.

From the lyrics alone, the ML engine gives:

- the **model's worship score**: how strongly the lyrics read as a
  Christian worship song. It depends on the lyrics alone;
- the **worship check**, decided from the worship score: the model's score
  plus the Trusted Artist bonus, a church rule applied after the model
  (see ``trusted_artist_bonus``);
- **theme tag** suggestions, scored against the church's Theme Tags (up
  to four, and only for songs that pass the worship check);
- a **feel** guess (upbeat, mid-tempo or slow);
- the lyrics **embedding**, which ranking compares with a theme.

A song a person has reviewed keeps their worship check, tags and feel;
analysing it again only renews the scores and the embedding.
"""

from dataclasses import dataclass

from django.db import transaction
from django.utils import timezone

from apps.core.music import Feel

from .ml import Label, get_engine
from .models import Song, ThemeTag, TrustedArtist

WORSHIP_WORDS = frozenset(
    """god jesus lord christ savior saviour spirit holy praise worship
    hallelujah alleluia glory hosanna amen lamb redeemer almighty messiah
    emmanuel immanuel cross heaven grace mercy salvation gospel risen
    resurrection throne majesty father""".split()
)
# The worship score is the best of these. Zero-shot models judge what a
# text says, not what kind of text it is: "This is a Christian worship song"
# scored public-domain hymns near 0 (decision 0006), so the hypotheses
# describe the words. The second covers prayers and laments.
WORSHIP = (
    Label("This text praises God.", WORSHIP_WORDS),
    Label("This text is about God.", WORSHIP_WORDS),
)
FEELS = {
    Feel.UPBEAT: Label(
        "This text is joyful and celebratory.",
        frozenset(
            """shout dance clap sing celebrate rejoice joy loud jump alive
            victory fire""".split()
        ),
    ),
    Feel.MID: Label(
        "This text is steady and thoughtful.",
        frozenset("walk follow trust faithful journey story road".split()),
    ),
    Feel.SLOW: Label(
        "This text is quiet and reflective.",
        frozenset(
            """still quiet kneel rest surrender near tears whisper humble
            bow gently peace""".split()
        ),
    ),
}

WORSHIP_THRESHOLD = 0.5
TRUSTED_ARTIST_BONUS = 0.25
TAG_THRESHOLD = 0.5
MAX_TAGS = 4


@dataclass
class Analysis:
    engine: str
    model_score: float  # the engine's score, from the lyrics alone
    worship_score: float  # model_score plus any Trusted Artist bonus
    accepted: bool
    tag_scores: dict  # ThemeTag pk -> score
    suggested_tags: list  # ThemeTag pks, best first
    feel: str
    embedding: list


def lyrics_text(lyrics):
    """The lyrics with repeated lines dropped, so a chorus sung five times
    counts once and long songs fit the models' input."""
    seen, lines = set(), []
    for line in lyrics.splitlines():
        key = line.strip().lower()
        if key and key not in seen:
            seen.add(key)
            lines.append(line.strip())
    return "\n".join(lines)


def tag_label(tag):
    return Label(f"This text is about {tag.name}.", frozenset(tag.keyword_set()))


def trusted_artist_bonus(model_score, trusted):
    """The worship score: the model's score plus the Trusted Artist bonus.

    This is a church rule applied after the model, not model input: the
    artist name (Spotify data) never reaches an engine. Neither the bonus
    nor any score that includes it may ever be a training feature; training
    uses ``Song.worship_model_score`` (Design-Decisions, Phases 5 and 9).
    """
    if not trusted:
        return model_score
    return min(1.0, model_score + TRUSTED_ARTIST_BONUS)


def analyse(lyrics, *, tags, trusted=False, engine=None):
    """Analyse lyrics against ``tags`` (Theme Tags). Changes nothing.

    ``trusted`` says whether the song's artist is a Trusted Artist; it only
    adjusts the worship score after the engine has run."""
    engine = engine or get_engine()
    text = lyrics_text(lyrics)
    tags = list(tags)

    model_score = max(engine.score(text, list(WORSHIP)))
    worship_score = trusted_artist_bonus(model_score, trusted)

    accepted = worship_score >= WORSHIP_THRESHOLD

    scores = engine.score(text, [tag_label(tag) for tag in tags]) if tags else []
    tag_scores = {tag.pk: round(score, 4) for tag, score in zip(tags, scores)}
    # Theme tags describe worship songs, so other songs get none.
    suggested = sorted(
        (pk for pk, score in tag_scores.items() if accepted and score >= TAG_THRESHOLD),
        key=lambda pk: -tag_scores[pk],
    )[:MAX_TAGS]

    feel_scores = engine.score(text, list(FEELS.values()))
    best = max(range(len(FEELS)), key=feel_scores.__getitem__)
    feel = list(FEELS)[best] if feel_scores[best] > 0 else Feel.MID

    return Analysis(
        engine=engine.name,
        model_score=round(model_score, 4),
        worship_score=round(worship_score, 4),
        accepted=accepted,
        tag_scores=tag_scores,
        suggested_tags=suggested,
        feel=feel,
        embedding=engine.embed([text])[0],
    )


def is_trusted(artist):
    """Whether any of the song's artists is on the church's active list."""
    names = {name.strip().lower() for name in artist.split(",") if name.strip()}
    trusted = {
        name.strip().lower()
        for name in TrustedArtist.objects.active().values_list("name", flat=True)
    }
    return bool(names & trusted)


def analyse_song(song, engine=None):
    """Analyse a song's lyrics and save the result. Returns the Analysis,
    or None when the song has no lyrics to read."""
    if song.lyrics_status != Song.LyricsStatus.FOUND or not song.lyrics.strip():
        return None
    result = analyse(
        song.lyrics,
        tags=ThemeTag.objects.active(),
        trusted=is_trusted(song.artist),
        engine=engine,
    )
    # The analysis took a while: lock the row and re-read whether a person
    # reviewed the song meanwhile, and save only the analysis fields, so a
    # correction saved in the meantime is never overwritten.
    with transaction.atomic():
        fresh = Song.objects.select_for_update().get(pk=song.pk)
        song.worship_model_score = result.model_score
        song.worship_score = result.worship_score
        song.tag_scores = {str(pk): score for pk, score in result.tag_scores.items()}
        song.embedding = result.embedding
        song.analysed_with = result.engine
        song.analysed_at = timezone.now()
        fields = [
            "worship_model_score",
            "worship_score",
            "tag_scores",
            "embedding",
            "analysed_with",
            "analysed_at",
            "updated_at",
        ]
        if not fresh.is_reviewed:
            song.worship_check = (
                Song.WorshipCheck.ACCEPTED
                if result.accepted
                else Song.WorshipCheck.REJECTED
            )
            song.feel = result.feel
            fields += ["worship_check", "feel"]
            song.tags.set(result.suggested_tags)
        song.save(update_fields=fields)
    return result
