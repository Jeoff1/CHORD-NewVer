"""Sequencing: placing the ranked songs in a service's Song Slots
(pipeline stage 8).

Feel is a preference, not a rule (smoke test, 2026-11-18): a song placed in
a slot of another feel loses ``feel_weight`` from its score for each step
between the feels (upbeat, mid-tempo, slow), so upbeat in a slow slot costs
two steps. A song whose feel isn't known yet costs half a step in a slot
that asks for a feel, so it never beats a song of a known, matching feel
with the same score (decision of 2026-11-18). A slot without a feel costs
nothing. Placements are made best first: the highest adjusted score of any
song in any empty slot, then the next.

A lineup never holds two songs with the same title (versions of one song
are already grouped, ``versions.py``).
"""

from dataclasses import dataclass

from apps.core.music import Feel
from apps.songs.cleanup import base_title

FEEL_STEPS = {Feel.UPBEAT: 0, Feel.MID: 1, Feel.SLOW: 2}
# An unknown feel counts as this many steps from any feel a slot asks for.
UNKNOWN_FEEL_STEPS = 0.5


@dataclass
class Placement:
    slot: object
    index: int  # position of the song in the ranked list
    reason: str = ""


def feel_distance(song_feel, slot_feel):
    """Steps between a song's feel and a slot's: 0 when the slot takes any
    feel, half a step when the song's feel isn't known."""
    if slot_feel not in FEEL_STEPS:
        return 0
    if song_feel not in FEEL_STEPS:
        return UNKNOWN_FEEL_STEPS
    return abs(FEEL_STEPS[song_feel] - FEEL_STEPS[slot_feel])


def slot_reason(song, slot):
    """Why ``song`` is in ``slot`` when its feel needs explaining (unknown,
    or not the slot's), or "". It depends on the slot, so a lineup works it
    out for the slot a song is in now, never from where it was suggested."""
    if slot is None:
        return ""
    return _reason(song, slot, feel_distance(song.feel, slot.feel))


def _reason(song, slot, distance):
    if not slot.feel:
        return ""
    wanted = slot.get_feel_display().lower()
    if not song.feel:
        return f"Its feel isn't known yet; this slot asks for {wanted}."
    if distance:
        return (
            f"Its feel ({song.get_feel_display().lower()}) isn't the {wanted} "
            "this slot asks for, but it fit best."
        )
    return ""


def place(ranked, slots, *, feel_weight=0.15):
    """Placements for ``slots`` from ``ranked`` songs (best first); a slot
    is left out when no song is left for it."""
    slots = list(slots)
    open_slots = list(range(len(slots)))
    free = list(range(len(ranked)))
    titles = set()
    placed = {}
    while open_slots:
        best = None
        for index in free:
            item = ranked[index]
            title = base_title(item.song.title)
            if title in titles:
                continue
            for slot_index in open_slots:
                slot = slots[slot_index]
                distance = feel_distance(item.song.feel, slot.feel)
                value = item.score - feel_weight * distance
                key = (value, -index, -slot_index)
                if best is None or key > best[0]:
                    best = (key, index, slot_index, distance)
        if best is None:
            break
        _, index, slot_index, distance = best
        song, slot = ranked[index].song, slots[slot_index]
        placed[slot_index] = Placement(slot, index, _reason(song, slot, distance))
        open_slots.remove(slot_index)
        free.remove(index)
        titles.add(base_title(song.title))
    return [placed[i] for i in sorted(placed)]
