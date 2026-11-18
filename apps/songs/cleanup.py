"""Cleaning up Spotify search results before songs are checked.

- Karaoke, instrumental and backing-track versions are dropped.
- Repeats are dropped: the same track, or the same song by the same artist
  in another version (live, acoustic, remastered, an edit). The plain
  version is kept when there is one.
"""

import re

JUNK = re.compile(
    r"\b(karaoke|instrumental|backing track|in the style of|originally "
    r"performed|made famous by|tribute to)\b",
    re.IGNORECASE,
)
VERSION_WORDS = (
    r"live|acoustic|remaster(?:ed)?|edit|version|mix|demo|session|mono|stereo"
    r"|feat\.?|featuring|with|reprise|unplugged"
)
BRACKETED = re.compile(rf"[(\[][^)\]]*\b(?:{VERSION_WORDS})\b[^)\]]*[)\]]", re.I)
DASHED = re.compile(rf"\s[-–]\s.*\b(?:{VERSION_WORDS})\b.*$", re.I)


def base_title(title):
    """The title without version notes, lower-cased: "Holy (Live)" and
    "Holy - 2011 Remaster" both give "holy"."""
    plain = DASHED.sub("", BRACKETED.sub("", title))
    return " ".join(re.findall(r"[\w']+", plain.lower()))


def is_version(title):
    return base_title(title) != " ".join(re.findall(r"[\w']+", title.lower()))


def is_junk(track):
    return bool(JUNK.search(track.title) or JUNK.search(track.album))


def clean_tracks(tracks):
    """The tracks worth checking, in their first-seen order."""
    kept = {}  # (base title, first artist) -> track
    order = []
    for track in tracks:
        if is_junk(track):
            continue
        first_artist = track.artists[0].lower() if track.artists else ""
        key = (base_title(track.title), first_artist)
        current = kept.get(key)
        if current is None:
            kept[key] = track
            order.append(key)
        elif is_version(current.title) and not is_version(track.title):
            kept[key] = track
    return [kept[key] for key in order]
