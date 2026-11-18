"""Ranking songs for a theme (pipeline stage 7).

    score = w1·relevance + w2·familiarity + w3·season − w4·recency

Each part runs from 0 to 1:

- **relevance**: how close the song's lyrics are to the theme (cosine of
  their embeddings), scaled so the closest candidate is 1 and the farthest
  0, so the weights compare like with like;
- **familiarity**: 0.6 when the team knows the song, plus up to 0.4 for how
  often it has been used (five times or more counts fully);
- **season**: 1 when the service falls in one of the church's Seasons and
  the song has one of that Season's Theme Tags;
- **recency**: 1 for a song used on the service's day, falling evenly to 0
  at the end of the repeat window.

The church sets the weights (Suggestion Settings). Each ranked song keeps
its parts and the reasons shown beside it.
"""

import datetime
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Usage:
    times: int = 0
    last_used: datetime.date | None = None


@dataclass
class Ranked:
    song: object
    score: float
    relevance: float
    familiarity: float
    season: float
    recency: float
    match: float  # the raw cosine
    reasons: list = field(default_factory=list)


def song_usage(service):
    """How often, and when last, each song was used before ``service``.

    Usage comes from confirmed lineups, which Phase 6 adds; until then no
    song has been used.
    """
    return {}


def cosine(a, b):
    """Embeddings are unit length, so the dot product is the cosine."""
    return sum(x * y for x, y in zip(a, b))


def familiarity(song, usage):
    known = 0.6 if song.team_knows else 0.0
    return known + 0.4 * min(usage.times / 5, 1.0)


def recency(usage, day, window_weeks):
    if not usage.last_used or not window_weeks:
        return 0.0
    days = (day - usage.last_used).days
    if days < 0:
        return 0.0
    return max(0.0, 1 - days / (7 * window_weeks))


def match_words(match_share):
    if match_share >= 0.75:
        return "closely"
    if match_share >= 0.4:
        return "fairly well"
    return "a little"


def rank(
    songs,
    *,
    theme_vector,
    day,
    weights,
    theme_tags=(),
    seasons=(),
    usage=None,
    window_weeks=0,
):
    """Score and sort ``songs`` (each with an embedding) for one theme.

    ``theme_tags`` are the Theme Tag IDs the theme is about; ``seasons`` the
    church's Seasons that contain ``day``; ``usage`` maps song IDs to Usage.
    """
    usage = usage or {}
    songs = [song for song in songs if song.embedding]
    matches = [cosine(theme_vector, song.embedding) for song in songs]
    low, high = (min(matches), max(matches)) if matches else (0, 0)
    season_tags = {tag.pk: season for season in seasons for tag in season.tags.all()}
    theme_tags = set(theme_tags)
    ranked = []
    for song, match in zip(songs, matches):
        used = usage.get(song.pk, Usage())
        tags = {tag.pk: tag for tag in song.tags.all()}
        parts = {
            "relevance": (match - low) / (high - low) if high > low else 1.0,
            "familiarity": familiarity(song, used),
            "season": 1.0 if season_tags.keys() & tags.keys() else 0.0,
            "recency": recency(used, day, window_weeks),
        }
        score = (
            weights["relevance"] * parts["relevance"]
            + weights["familiarity"] * parts["familiarity"]
            + weights["season"] * parts["season"]
            - weights["recency"] * parts["recency"]
        )
        reasons = [f"Its lyrics match the theme {match_words(parts['relevance'])}."]
        shared = sorted(tags[pk].name for pk in theme_tags & tags.keys())
        if shared:
            reasons.append(f"About {_listing(shared)}, like the theme.")
        if song.team_knows:
            reasons.append("The team knows it.")
        if used.times:
            reasons.append(
                f"Used {used.times} time{'s' if used.times != 1 else ''} before."
            )
        if parts["season"]:
            names = sorted({season_tags[pk].name for pk in season_tags.keys() & tags})
            reasons.append(f"Suits the season: {_listing(names)}.")
        if parts["recency"]:
            last = used.last_used
            reasons.append(f"Held back: sung on {last:%b} {last.day}.")
        rounded = {name: round(value, 4) for name, value in parts.items()}
        ranked.append(
            Ranked(
                song,
                round(score, 4),
                match=round(match, 4),
                reasons=reasons,
                **rounded,
            )
        )
    ranked.sort(key=lambda item: (-item.score, item.song.title.lower(), item.song.pk))
    return ranked


def _listing(names):
    if len(names) <= 2:
        return " and ".join(names)
    return ", ".join(names[:-1]) + " and " + names[-1]
