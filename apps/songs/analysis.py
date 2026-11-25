"""Song analysis: what a song's lyrics say about it.

From the lyrics alone, the ML engine gives:

- the **model's worship score**: how strongly the lyrics read as a
  Christian worship song. It depends on the lyrics alone;
- **theme tag** scores against the church's Theme Tags;
- a **feel** guess (upbeat, mid-tempo or slow), left blank when the engine
  isn't sure;
- the lyrics **embedding**, which ranking compares with a theme.

Then the church's rules, applied after the model (``decide_check``), turn
the model's score into the **worship score** and the **Worship Check**: the
Trusted Artist bonus, the pass mark, and the optional rule for artists not
on the Trusted Artists list (``WorshipCheckSettings``). The artist name is
compared here, never given to an engine, and never a training feature
(Design-Decisions, Phase 5 and its follow-up). Songs that don't pass get no
theme tags.

A song a person has reviewed keeps their worship check, tags and feel; one
whose feel a person set keeps that feel. Analysing again only renews the
scores and the embedding.
"""

from dataclasses import dataclass

from django.db import transaction
from django.utils import timezone

from apps.core.music import Feel

from .ml import Label, get_engine
from .models import Song, ThemeTag, TrustedArtist, WorshipCheckSettings

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

TRUSTED_ARTIST_BONUS = 0.25
TAG_THRESHOLD = 0.5
MAX_TAGS = 4
# A feel is guessed only when one clearly wins: its score reaches
# FEEL_MIN_SCORE and beats the next by FEEL_MARGIN. Otherwise it stays blank
# for a person to set (smoke test, 2026-11-18: near ties and tiny scores
# were guessed wrongly).
FEEL_MIN_SCORE = 0.5
FEEL_MARGIN = 0.2

Check = Song.WorshipCheck
UnlistedRule = WorshipCheckSettings.UnlistedRule


@dataclass(frozen=True)
class CheckRules:
    """The church's Worship Check rules (``WorshipCheckSettings``)."""

    pass_mark: float = 0.5
    unlisted_rule: str = UnlistedRule.OFF
    unlisted_pass_mark: float = 0.9

    @classmethod
    def load(cls, church):
        row = WorshipCheckSettings.load(church)
        return cls(row.pass_mark, row.unlisted_rule, row.unlisted_pass_mark)


@dataclass
class Analysis:
    engine: str
    model_score: float  # the engine's score, from the lyrics alone
    worship_score: float  # model_score plus any Trusted Artist bonus
    check: str  # a Song.WorshipCheck value, from the church's rules
    tag_scores: dict  # ThemeTag pk -> score
    suggested_tags: list  # ThemeTag pks, best first
    feel: str  # "" when the engine wasn't sure
    embedding: list

    @property
    def accepted(self):
        return self.check == Check.ACCEPTED


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


def decide_check(model_score, *, trusted, rules):
    """``(worship_score, check)`` from the model's score, by the church's
    rules. Church rules after the model: whether the artist is trusted is
    decided here and never reaches an engine or a training set."""
    score = trusted_artist_bonus(model_score, trusted)
    if score < rules.pass_mark:
        return score, Check.REJECTED
    if trusted or rules.unlisted_rule == UnlistedRule.OFF:
        return score, Check.ACCEPTED
    if rules.unlisted_rule == UnlistedRule.STRICTER:
        passed = score >= rules.unlisted_pass_mark
        return score, Check.ACCEPTED if passed else Check.REJECTED
    return score, Check.UNCHECKED  # waits for a person's review


def suggested_tags(tag_scores, check):
    """Up to four best tags scoring at least the threshold, for songs that
    pass (or wait for review); none for songs that don't."""
    if check == Check.REJECTED:
        return []
    fitting = [pk for pk, score in tag_scores.items() if score >= TAG_THRESHOLD]
    return sorted(fitting, key=lambda pk: -tag_scores[pk])[:MAX_TAGS]


def guess_feel(scores):
    """The feel whose score clearly wins, or "" when none does."""
    ranked = sorted(zip(scores, FEELS), reverse=True)
    (best, feel), (second, _) = ranked[0], ranked[1]
    if best >= FEEL_MIN_SCORE and best - second >= FEEL_MARGIN:
        return feel
    return ""


def analyse(lyrics, *, tags, trusted=False, engine=None, rules=None):
    """Analyse lyrics against ``tags`` (Theme Tags). Changes nothing.

    ``trusted`` says whether the song's artist is a Trusted Artist, and
    ``rules`` are the church's check rules; both apply only after the
    engine has run."""
    engine = engine or get_engine()
    rules = rules or CheckRules()
    text = lyrics_text(lyrics)
    tags = list(tags)

    model_score = max(engine.score(text, list(WORSHIP)))
    worship_score, check = decide_check(model_score, trusted=trusted, rules=rules)

    scores = engine.score(text, [tag_label(tag) for tag in tags]) if tags else []
    tag_scores = {tag.pk: round(score, 4) for tag, score in zip(tags, scores)}

    return Analysis(
        engine=engine.name,
        model_score=round(model_score, 4),
        worship_score=round(worship_score, 4),
        check=check,
        tag_scores=tag_scores,
        suggested_tags=suggested_tags(tag_scores, check),
        feel=guess_feel(engine.score(text, list(FEELS.values()))),
        embedding=engine.embed([text])[0],
    )


def trusted_names(church):
    return {
        name.strip().lower()
        for name in TrustedArtist.objects.for_church(church)
        .active()
        .values_list("name", flat=True)
    }


def is_trusted(artist, names):
    """Whether any of the song's artists is in ``names``, the church's
    active list (``trusted_names``)."""
    credited = {name.strip().lower() for name in artist.split(",") if name.strip()}
    return bool(credited & names)


def analyse_song(song, engine=None):
    """Analyse a song's lyrics with its own church's Theme Tags, Trusted
    Artists and check rules, and save the result. Returns the Analysis, or
    None when the song has no lyrics to read."""
    if song.lyrics_status != Song.LyricsStatus.FOUND or not song.lyrics.strip():
        return None
    church = song.church
    result = analyse(
        song.lyrics,
        tags=ThemeTag.objects.for_church(church).active(),
        trusted=is_trusted(song.artist, trusted_names(church)),
        engine=engine,
        rules=CheckRules.load(church),
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
            song.worship_check = result.check
            fields.append("worship_check")
            song.tags.set(result.suggested_tags)
            if not fresh.feel_reviewed:
                song.feel = result.feel
                fields.append("feel")
        song.save(update_fields=fields)
    return result


def apply_check_rules(church):
    """Decide the Worship Check again for every analysed song of ``church``
    nobody has reviewed, from its stored model score, after the church
    changes its rules or its Trusted Artists. No model runs. Returns how
    many songs changed."""
    rules = CheckRules.load(church)
    names = trusted_names(church)
    active_tags = set(
        ThemeTag.objects.for_church(church).active().values_list("pk", flat=True)
    )
    changed = 0
    songs = (
        Song.objects.for_church(church)
        .filter(reviewed_at=None)
        .exclude(worship_model_score=None)
        .exclude(analysed_at=None)
    )
    for song in songs:
        score, check = decide_check(
            song.worship_model_score,
            trusted=is_trusted(song.artist, names),
            rules=rules,
        )
        score = round(score, 4)
        if score == song.worship_score and check == song.worship_check:
            continue
        tag_scores = {
            int(pk): value
            for pk, value in (song.tag_scores or {}).items()
            if int(pk) in active_tags
        }
        song.worship_score, song.worship_check = score, check
        song.save(update_fields=["worship_score", "worship_check", "updated_at"])
        song.tags.set(suggested_tags(tag_scores, check))
        changed += 1
    return changed
