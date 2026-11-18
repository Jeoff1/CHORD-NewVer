"""Sequencing: placing the top-ranked songs in a service's Song Slots by
feel (pipeline stage 8).

Songs are taken in rank order; each goes in the first empty slot whose feel
it matches (a slot without a feel takes any song). Slots still empty at the
end take the best songs left, whatever their feel, and say so.
"""

from dataclasses import dataclass


@dataclass
class Placement:
    slot: object
    index: int  # position of the song in the ranked list
    reason: str = ""


def place(ranked, slots):
    """Placements for ``slots`` (in service order) from ``ranked`` songs;
    a slot is left out when there are no songs left."""
    slots = list(slots)
    placed = {}
    used = set()
    for index, item in enumerate(ranked):
        if len(placed) == len(slots):
            break
        for slot in slots:
            if slot.pk in placed:
                continue
            if not slot.feel or item.song.feel == slot.feel:
                placed[slot.pk] = Placement(slot, index)
                used.add(index)
                break
    leftovers = (index for index in range(len(ranked)) if index not in used)
    for slot in slots:
        if slot.pk in placed:
            continue
        index = next(leftovers, None)
        if index is None:
            break
        placed[slot.pk] = Placement(
            slot,
            index,
            f"No {slot.get_feel_display().lower()} song ranked high enough, "
            "so the best song left fills this slot.",
        )
    return [placed[slot.pk] for slot in slots if slot.pk in placed]
