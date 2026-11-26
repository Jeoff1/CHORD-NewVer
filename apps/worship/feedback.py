"""Suggestion Feedback: what people did with the suggestions in a lineup
(pipeline stage 11; Design-Decisions, Phases 6 and 9).

While a lineup is reviewed, ``Lineup.suggestion_outcomes`` follows every
suggestion placed in it (``apps/worship/lineups.py``):

- placed in the lineup by making or regenerating it: **kept**;
- an alternative chosen in a swap: **swapped in** (a positive, like kept,
  told apart from a top pick that stayed);
- added on its own by a person from the suggestions: **picked** (a
  positive; decision 0015);
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
SWAPPED_IN = SuggestionFeedback.Label.SWAPPED_IN
PICKED = SuggestionFeedback.Label.PICKED
SWAPPED = SuggestionFeedback.Label.SWAPPED
REMOVED = SuggestionFeedback.Label.REMOVED


# --- Following outcomes during review ------------------------------------------


# The outcomes of a suggestion still in the lineup.
IN_LINEUP = (KEPT, SWAPPED_IN, PICKED)


def placed(lineup, suggestions, outcome=KEPT):
    """Suggestions put in the lineup: ``outcome`` (kept, or swapped in for
    an alternative chosen in a swap), unless a person changes that."""
    for suggestion in suggestions:
        lineup.suggestion_outcomes[str(suggestion.pk)] = outcome


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
    if key is not None and lineup.suggestion_outcomes[key] in IN_LINEUP:
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
    # count as kept or swapped in.
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
        if label in IN_LINEUP and song.pk not in slot_feels:
            label = REMOVED
        if label in IN_LINEUP:
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
