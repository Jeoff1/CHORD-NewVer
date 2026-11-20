"""Chord sheets in ChordPro: checking, converting and transposing them.

Everything here runs on the server, in plain Python, so the normal test
suite covers it (decision 0009):

- ``check()``: whether a text is valid ChordPro, with a message naming the
  first problem and its line;
- ``to_chordpro()``: converts a chords-over-words chart (as on Ultimate
  Guitar) to ChordPro; ChordPro passes through unchanged;
- ``render()``: the sheet as blocks of lines, transposed to a key, with a
  capo or as Nashville numbers.

Sharps or flats follow the key a chord is shown in, and a slash chord's
bass note moves with its root. Lyrics and chord sheets are copyrighted:
nothing here logs them.
"""

import re
from dataclasses import dataclass, field

from apps.core.music import MAJOR_KEYS, MINOR_KEYS

MAX_LENGTH = 20000

NOTE_INDEX = {
    "C": 0, "B#": 0, "C#": 1, "Db": 1, "D": 2, "D#": 3, "Eb": 3, "E": 4,
    "Fb": 4, "E#": 5, "F": 5, "F#": 6, "Gb": 6, "G": 7, "G#": 8, "Ab": 8,
    "A": 9, "A#": 10, "Bb": 10, "B": 11, "Cb": 11,
}  # fmt: skip
SHARP_NAMES = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")
FLAT_NAMES = ("C", "Db", "D", "Eb", "E", "F", "Gb", "G", "Ab", "A", "Bb", "B")
# Keys whose chords are spelled with flats. C major and A minor have no
# sharps or flats of their own; their borrowed chords (Bb, Eb, Ab) are far
# more common in worship songs than sharp ones, so they use flats too.
FLAT_KEYS = frozenset(
    ["C", "F", "Bb", "Eb", "Ab", "Db", "Gb"]
    + ["Am", "Dm", "Gm", "Cm", "Fm", "Bbm", "Ebm"]
)
# Nashville numbers by semitones above the key's tonic.
DEGREES = ("1", "b2", "2", "b3", "3", "4", "#4", "5", "b6", "6", "b7", "7")
# Capo positions offered, and the shapes most guitarists find easy.
CAPO_POSITIONS = range(0, 8)
EASY_SHAPES = frozenset(["C", "D", "E", "G", "A", "Am", "Dm", "Em"])

NOTE = r"[A-G](?:#|b)?"
CHORD = re.compile(rf"^(?P<root>{NOTE})(?P<quality>.*?)(?:/(?P<bass>{NOTE}))?$")
QUALITY = re.compile(r"^[A-Za-z0-9#+\-()°ø△Δº.^/]*$")
NO_CHORD = frozenset(["N.C.", "NC", "N.C", "x", "%", "-"])
DIRECTIVE = re.compile(
    r"^\{\s*(?P<name>[A-Za-z_][\w-]*)\s*(?:[:\s]\s*(?P<value>.*?))?\s*\}$"
)
INLINE_CHORD = re.compile(r"\[([^\[\]]*)\]")

SECTIONS = {
    "start_of_chorus": "chorus", "soc": "chorus",
    "start_of_verse": "verse", "sov": "verse",
    "start_of_bridge": "bridge", "sob": "bridge",
    "start_of_tab": "tab", "sot": "tab",
    "start_of_grid": "grid", "sog": "grid",
}  # fmt: skip
SECTION_ENDS = {
    "end_of_chorus": "chorus", "eoc": "chorus",
    "end_of_verse": "verse", "eov": "verse",
    "end_of_bridge": "bridge", "eob": "bridge",
    "end_of_tab": "tab", "eot": "tab",
    "end_of_grid": "grid", "eog": "grid",
}  # fmt: skip
SECTION_LABELS = {"chorus": "Chorus", "verse": "Verse", "bridge": "Bridge", "tab": "Tab", "grid": "Grid"}  # fmt: skip
COMMENTS = frozenset(["comment", "c", "comment_italic", "ci", "comment_box", "cb", "highlight"])  # fmt: skip


class ChordProError(ValueError):
    """The text isn't valid ChordPro; the message names the line."""


# --- Keys and chords -----------------------------------------------------------


@dataclass(frozen=True)
class Key:
    tonic: int  # 0 (C) to 11 (B)
    minor: bool = False

    @classmethod
    def parse(cls, name):
        """``Key`` from a name such as "G", "F#m" or "Bb"."""
        name = (name or "").strip()
        minor = name.endswith("m") and len(name) > 1
        note = name[:-1] if minor else name
        if note not in NOTE_INDEX:
            raise ValueError(f"{name!r} isn't a key.")
        return cls(NOTE_INDEX[note], minor)

    @property
    def name(self):
        return (MINOR_KEYS if self.minor else MAJOR_KEYS)[self.tonic]

    @property
    def long_name(self):
        """The key in words: "A minor", "Bb major"."""
        tonic = self.name[:-1] if self.minor else self.name
        return f"{tonic} {'minor' if self.minor else 'major'}"

    @property
    def flats(self):
        return self.name in FLAT_KEYS

    def shifted(self, steps):
        return Key((self.tonic + steps) % 12, self.minor)

    def steps_to(self, other):
        """Semitones up from this key's tonic to ``other``'s (0 to 11)."""
        return (other.tonic - self.tonic) % 12


def note_name(index, flats):
    return (FLAT_NAMES if flats else SHARP_NAMES)[index % 12]


@dataclass(frozen=True)
class Chord:
    root: str
    quality: str = ""
    bass: str = ""

    @classmethod
    def parse(cls, text):
        """A ``Chord``, or None when ``text`` isn't one."""
        match = CHORD.match(text.strip())
        if not match or not QUALITY.match(match["quality"]):
            return None
        return cls(match["root"], match["quality"], match["bass"] or "")

    @property
    def is_minor(self):
        quality = self.quality
        return quality.startswith(("m", "min", "-")) and not quality.startswith("maj")

    def transposed(self, steps, flats):
        """The chord moved by ``steps`` semitones, spelled with flats or
        sharps; a slash chord's bass note moves with it."""
        root = note_name(NOTE_INDEX[self.root] + steps, flats)
        bass = note_name(NOTE_INDEX[self.bass] + steps, flats) if self.bass else ""
        return Chord(root, self.quality, bass)

    def nashville(self, key):
        """The chord as a Nashville number in ``key``: "Am7" in C is "6m7",
        "G/B" is "5/7". In a minor key, 1 is the minor tonic."""
        root = DEGREES[(NOTE_INDEX[self.root] - key.tonic) % 12]
        bass = DEGREES[(NOTE_INDEX[self.bass] - key.tonic) % 12] if self.bass else ""
        return f"{root}{self.quality}" + (f"/{bass}" if bass else "")

    def __str__(self):
        return f"{self.root}{self.quality}" + (f"/{self.bass}" if self.bass else "")


def is_chord_token(text):
    text = text.strip()
    return text in NO_CHORD or text.startswith("*") or Chord.parse(text) is not None


def transpose_chord(text, steps, flats):
    """A chord's text moved by ``steps``; markers such as N.C. stay."""
    chord = Chord.parse(text)
    return str(chord.transposed(steps, flats)) if chord else text


# --- Checking ChordPro ---------------------------------------------------------------


def directive(line):
    """``(name, value)`` for a directive line such as ``{c: Chorus}``, or
    None for any other line."""
    match = DIRECTIVE.match(line.strip())
    if not match:
        return None
    return match["name"].lower(), (match["value"] or "").strip()


def check(text):
    """Raise ``ChordProError`` naming the first problem, or return the
    number of chords. Valid ChordPro here means: directives alone on their
    line and in braces, every ``[chord]`` closed and a real chord, sections
    opened and closed in order, and at least one chord."""
    if not text.strip():
        raise ChordProError("The chord sheet is empty.")
    if len(text) > MAX_LENGTH:
        raise ChordProError(
            f"The chord sheet is too long ({len(text)} characters; the most is "
            f"{MAX_LENGTH})."
        )
    chords, section = 0, None
    for number, line in enumerate(text.splitlines(), 1):
        stripped = line.strip()
        if stripped.startswith("#"):
            continue  # a ChordPro comment, not shown
        if section == "tab" and not stripped.startswith("{"):
            continue  # tablature is shown as it is
        if stripped.startswith("{") or stripped.endswith("}"):
            found = directive(stripped)
            if found is None:
                raise ChordProError(
                    f"Line {number}: a directive must be on its own line, in "
                    "braces, such as {title: Amazing Grace} or {soc}."
                )
            name, _ = found
            if name in SECTIONS:
                if section is not None:
                    raise ChordProError(
                        f"Line {number}: a {SECTIONS[name]} starts before the "
                        f"{section} above it ends."
                    )
                section = SECTIONS[name]
            elif name in SECTION_ENDS:
                if section != SECTION_ENDS[name]:
                    raise ChordProError(
                        f"Line {number}: this ends a {SECTION_ENDS[name]} that "
                        "wasn't started."
                    )
                section = None
            continue
        if "{" in line or "}" in line:
            raise ChordProError(
                f"Line {number}: braces belong only around a directive on its own line."
            )
        chords += _check_chords(line, number)
    if section is not None:
        raise ChordProError(f"The {section} at the end is never closed.")
    if not chords:
        raise ChordProError(
            "There are no chords. In ChordPro each chord goes in square "
            "brackets before its syllable, such as [G]Amazing [C]grace."
        )
    return chords


def _check_chords(line, number):
    depth, count = 0, 0
    for char in line:
        if char == "[":
            depth += 1
            if depth > 1:
                raise ChordProError(f"Line {number}: a [ opens inside another chord.")
        elif char == "]":
            depth -= 1
            if depth < 0:
                raise ChordProError(f"Line {number}: a ] closes a chord never opened.")
    if depth:
        raise ChordProError(f"Line {number}: a chord's [ is never closed.")
    for chord in INLINE_CHORD.findall(line):
        if not chord.strip():
            raise ChordProError(f"Line {number}: [] holds no chord.")
        if not is_chord_token(chord):
            raise ChordProError(f"Line {number}: “{chord}” isn't a chord.")
        count += 1
    return count


def key_directive(text):
    """The key a ChordPro text names with ``{key: …}``, or ""."""
    for line in text.splitlines():
        found = directive(line)
        if found and found[0] == "key":
            return found[1]
    return ""


# --- Converting chords over words --------------------------------------------------

UG_TAGS = re.compile(r"\[/?(?:ch|tab)\]")
SECTION_HEADER = re.compile(r"^\s*\[(?P<name>[^\[\]]+)\]\s*:?\s*$")
IGNORABLE = re.compile(r"^(?:\||/|-+|\(?x\d+\)?|\(|\))$", re.I)


def looks_like_chordpro(text):
    """Whether the text is already ChordPro: a directive, or a [chord]
    inside a line of words."""
    for line in text.splitlines():
        if directive(line):
            return True
        if any(is_chord_token(c) for c in INLINE_CHORD.findall(line)):
            rest = INLINE_CHORD.sub("", line).strip()
            if rest:
                return True
    return False


def is_chord_line(line):
    """A line holding only chords (and bar marks or repeat counts)."""
    tokens = line.split()
    if not tokens:
        return False
    chords = [t for t in tokens if not IGNORABLE.match(t)]
    return bool(chords) and all(Chord.parse(t) or t in NO_CHORD for t in chords)


def _merge(chord_line, lyric):
    """Put each chord of ``chord_line`` into ``lyric`` at its column."""
    lyric = lyric.rstrip()
    positions = [(m.start(), m.group()) for m in re.finditer(r"\S+", chord_line)]
    for column, token in reversed(positions):
        if IGNORABLE.match(token):
            continue
        if column > len(lyric):
            lyric = lyric + " " * (column - len(lyric))
        lyric = f"{lyric[:column]}[{token}]{lyric[column:]}"
    return lyric


def _chords_only(chord_line):
    return re.sub(
        r"\S+",
        lambda m: m.group() if IGNORABLE.match(m.group()) else f"[{m.group()}]",
        chord_line.rstrip(),
    )


def to_chordpro(text):
    """ChordPro from a chords-over-words chart, such as one copied from
    Ultimate Guitar: each line of chords goes into the line of words under
    it, and section names such as "[Chorus]" become comments. Text that is
    already ChordPro comes back unchanged."""
    text = UG_TAGS.sub("", text.replace("\r\n", "\n")).expandtabs(4)
    if looks_like_chordpro(text):
        return text.strip("\n") + "\n"
    lines, out, i = text.split("\n"), [], 0
    while i < len(lines):
        line = lines[i]
        header = SECTION_HEADER.match(line)
        if header and not is_chord_token(header["name"]):
            out.append(f"{{comment: {header['name'].strip()}}}")
        elif is_chord_line(line):
            following = lines[i + 1] if i + 1 < len(lines) else ""
            if (
                following.strip()
                and not is_chord_line(following)
                and not (SECTION_HEADER.match(following))
            ):
                out.append(_merge(line, following))
                i += 1
            else:
                out.append(_chords_only(line))
        else:
            out.append(line.rstrip())
        i += 1
    return "\n".join(out).strip("\n") + "\n"


# --- Rendering ------------------------------------------------------------------------


@dataclass
class Segment:
    chord: str  # "" when the words have no chord over them
    text: str


@dataclass
class Line:
    kind: str  # "lyrics", "comment", "tab" or "blank"
    segments: list = field(default_factory=list)
    text: str = ""


@dataclass
class Block:
    label: str = ""
    kind: str = ""  # "chorus", "verse", "bridge", "tab", or "" outside a section
    lines: list = field(default_factory=list)


@dataclass
class Rendered:
    title: str
    subtitle: str
    blocks: list
    key: Key  # the key the song is heard in
    shape_key: Key  # the key of the shapes played (differs with a capo)
    capo: int
    numbers: bool


def _segments(line, show):
    parts = INLINE_CHORD.split(line)
    # parts: text, chord, text, chord, text ...
    segments = [Segment("", parts[0])] if parts[0] else []
    for index in range(1, len(parts), 2):
        segments.append(Segment(show(parts[index].strip()), parts[index + 1]))
    return segments


def render(text, original, target=None, *, capo=0, numbers=False):
    """The sheet as blocks of lines, with every chord shown for ``target``
    (a ``Key``; the original when None). With a capo, chords are the shapes
    played: the sounding key moved down by the capo. With ``numbers``, chords
    are Nashville numbers in the sounding key. Call ``check()`` first."""
    target = target or original
    capo = capo if capo in CAPO_POSITIONS and not numbers else 0
    shape_key = target.shifted(-capo)
    steps = original.steps_to(shape_key)

    def show(chord_text):
        chord = Chord.parse(chord_text)
        if chord is None:
            return chord_text
        if numbers:
            return chord.transposed(original.steps_to(target), target.flats).nashville(
                target
            )
        return str(chord.transposed(steps, shape_key.flats))

    title = subtitle = ""
    blocks = [Block()]
    for raw in text.splitlines():
        stripped = raw.strip()
        if stripped.startswith("#"):
            continue
        found = directive(stripped)
        current = blocks[-1]
        if current.kind == "tab" and not (found and found[0] in SECTION_ENDS):
            current.lines.append(Line("tab", text=raw.rstrip()))
            continue
        if found:
            name, value = found
            if name in ("title", "t"):
                title = value
            elif name in ("subtitle", "st", "artist"):
                subtitle = subtitle or value
            elif name in SECTIONS:
                kind = SECTIONS[name]
                blocks.append(Block(value or SECTION_LABELS[kind], kind))
            elif name in SECTION_ENDS:
                blocks.append(Block())
            elif name in COMMENTS:
                current.lines.append(Line("comment", text=value))
            elif name == "chorus":
                current.lines.append(Line("comment", text=value or "Chorus"))
            continue
        if not stripped:
            current.lines.append(Line("blank"))
        else:
            current.lines.append(Line("lyrics", segments=_segments(raw.rstrip(), show)))
    blocks = [block for block in blocks if block.lines or block.label]
    return Rendered(title, subtitle, blocks, target, shape_key, capo, numbers)


def capo_options(target):
    """``(position, shape key, easy)`` for each capo position offered."""
    return [
        (position, (shape := target.shifted(-position)), shape.name in EASY_SHAPES)
        for position in CAPO_POSITIONS
    ]
