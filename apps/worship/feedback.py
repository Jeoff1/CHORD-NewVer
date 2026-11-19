"""Suggestion Feedback: what people did with the suggestions in a lineup
(pipeline stage 11; Design-Decisions, Phases 6 and 9).

While a lineup is reviewed, ``Lineup.suggestion_outcomes`` follows every
suggestion placed in it (``apps/worship/lineups.py``):

- placed in the lineup (made, regenerated, or chosen in a swap): **kept**;
- replaced by a swap: **swapped**;
- taken out: **removed**.

Regenerating starts over for the songs it replaces: they were neither kept
nor turned down by a person. Confirming the lineup records the outcomes as
``SuggestionFeedback`` rows, replacing those of an earlier confirmation, so
the data always matches the lineup as last confirmed. Songs added from the
pool weren't suggested, so they leave no feedback.
"""

from django.utils import timezone

from .models import Suggestion, SuggestionFeedback

KEPT = SuggestionFeedback.Label.KEPT
SWAPPED = SuggestionFeedback.Label.SWAPPED
REMOVED = SuggestionFeedback.Label.REMOVED


# --- Following outcomes during review ------------------------------------------


def placed(lineup, suggestions):
    """Suggestions put in the lineup: kept, unless a person changes that."""
    for suggestion in suggestions:
        lineup.suggestion_outcomes[str(suggestion.pk)] = KEPT


def _key_for(lineup, song_id):
    """The outcome key of the suggestion that put ``song_id`` in the
    lineup, or None when the song came from the pool."""
    keys = [int(key) for key in lineup.suggestion_outcomes]
    found = (
        Suggestion.objects.filter(pk__in=keys, song_id=song_id)
        .order_by("-pk")
        .values_list("pk", flat=True)
        .first()
    )
    return None if found is None else str(found)


def turned_down(lineup, song_id, outcome):
    """A person swapped out or removed the song a suggestion placed."""
    key = _key_for(lineup, song_id)
    if key is not None and lineup.suggestion_outcomes[key] == KEPT:
        lineup.suggestion_outcomes[key] = outcome


def forget(lineup, song_ids):
    """Regenerating replaced these songs: their suggestions leave no
    feedback."""
    for song_id in song_ids:
        key = _key_for(lineup, song_id)
        if key is not None:
            del lineup.suggestion_outcomes[key]


# --- Recording on confirmation -----------------------------------------------------


def record(lineup):
    """Save the lineup's feedback, replacing any from an earlier
    confirmation. Returns the rows."""
    SuggestionFeedback.objects.filter(lineup=lineup).delete()
    outcomes = lineup.suggestion_outcomes or {}
    suggestions = Suggestion.objects.filter(
        pk__in=[int(key) for key in outcomes]
    ).select_related("song", "slot")
    # The slot each song is in now; a song no longer in the lineup can't
    # count as kept.
    slot_feels = {
        item.song_id: item.slot.feel if item.slot else ""
        for item in lineup.items.select_related("slot")
    }
    now = timezone.now()
    rows, seen = [], set()
    for suggestion in sorted(suggestions, key=lambda s: (-s.run_id, s.rank)):
        if suggestion.song_id in seen:  # the same song from two runs: latest
            continue
        seen.add(suggestion.song_id)
        song = suggestion.song
        label = outcomes[str(suggestion.pk)]
        if label == KEPT and song.pk not in slot_feels:
            label = REMOVED
        if label == KEPT:
            slot_feel = slot_feels[song.pk]
        else:
            slot_feel = suggestion.slot.feel if suggestion.slot else ""
        rows.append(
            SuggestionFeedback(
                lineup=lineup,
                run_id=suggestion.run_id,
                song=song,
                label=label,
                recorded_at=now,
                rank=suggestion.rank,
                relevance=suggestion.relevance,
                match=suggestion.match,
                worship_model_score=song.worship_model_score,
                familiarity=suggestion.familiarity,
                season=suggestion.season,
                recency=suggestion.recency,
                team_knows=song.team_knows,
                slot_feel=slot_feel,
            )
        )
    return SuggestionFeedback.objects.bulk_create(rows)
