"""Versions of one song (pipeline stage 7, after ranking).

Covers and live recordings of one song are different tracks in the pool,
and every version is kept there. Suggestions show one version per song:

- Two songs are versions of one song when their lyrics embeddings are at
  least ``SAME_TITLE_SIMILARITY`` alike and their titles begin the same way
  ("Silent Night" and "Silent Night, Holy Night"), or at least
  ``ANY_TITLE_SIMILARITY`` alike whatever their titles. Calibrated in the
  smoke test of 2026-11-18: versions of "Silent Night" scored 0.93 to 0.96
  and two recordings of "Good News" 0.91, against 0.61 for "Silent Night"
  and "Hark! the Herald Angels Sing".
- The version kept is the first of: one the team knows, one a person has
  reviewed, one by a Trusted Artist, then the best scored. Whether an
  artist is trusted is a church rule decided here, outside any model.
"""

import numpy as np

from apps.songs.analysis import is_trusted, trusted_names
from apps.songs.cleanup import base_title

SAME_TITLE_SIMILARITY = 0.90
ANY_TITLE_SIMILARITY = 0.95


def titles_match(first, second):
    """Whether two titles begin the same way, ignoring version notes."""
    a, b = base_title(first), base_title(second)
    if not (a and b):
        return False
    return a == b or a.startswith(f"{b} ") or b.startswith(f"{a} ")


def _groups(ranked):
    """Lists of indexes into ``ranked``, one per song, in rank order."""
    vectors = np.array([item.song.embedding for item in ranked], dtype=float)
    similar = np.triu(vectors @ vectors.T >= SAME_TITLE_SIMILARITY, k=1)
    parent = list(range(len(ranked)))

    def root(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for i, j in np.argwhere(similar):
        i, j = int(i), int(j)
        likeness = float(np.dot(vectors[i], vectors[j]))
        if likeness >= ANY_TITLE_SIMILARITY or titles_match(
            ranked[i].song.title, ranked[j].song.title
        ):
            parent[root(j)] = root(i)
    groups = {}
    for index in range(len(ranked)):
        groups.setdefault(root(index), []).append(index)
    return sorted(groups.values(), key=lambda members: members[0])


def _why_chosen(kept, best):
    """Why the kept version beat the best-scored one (the preference order
    decides the first way they differ)."""
    if kept is best:
        return ""
    if kept.song.team_knows and not best.song.team_knows:
        why = "the team knows it"
    elif kept.song.is_reviewed and not best.song.is_reviewed:
        why = "a person has reviewed it"
    else:
        why = "its artist is a Trusted Artist"
    return f"Chosen over the version by {best.song.artist} because {why}."


def group(ranked, trusted_artists=None):
    """``ranked`` with one version per song, in score order. The kept item
    lists the others in ``versions`` and says so in its reasons."""
    if len(ranked) < 2:
        return list(ranked)
    names = trusted_names() if trusted_artists is None else trusted_artists

    def preference(index):
        song = ranked[index].song
        return (
            not song.team_knows,
            not song.is_reviewed,
            not is_trusted(song.artist, names),
            index,  # ranked is best first
        )

    kept = []
    for members in _groups(ranked):
        choice = min(members, key=preference)
        item = ranked[choice]
        others = [ranked[i] for i in members if i != choice]
        if others:
            item.versions = [other.song for other in others]
            # "Title, Artist", separated by semicolons: an artist name may
            # already hold brackets, such as "Charles Wesley (1739)".
            listing = "; ".join(f"{s.title}, {s.artist}" for s in item.versions)
            item.reasons.append(f"Other versions in the pool: {listing}.")
            why = _why_chosen(item, ranked[members[0]])
            if why:
                item.reasons.append(why)
        kept.append((choice, item))
    return [item for _, item in sorted(kept, key=lambda pair: pair[0])]
