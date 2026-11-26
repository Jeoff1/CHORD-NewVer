"""The Bible CHORD ships with (Phase 9C): book names, references and the
text of the World English Bible, which is in the public domain.

Used for the theme's Main scripture: suggestions while the pastor types,
a preview of the passage, and the passage's text, which song suggestions
read with the rest of the theme. The text is kept exactly as published
(``data/README.md``).

Which books are offered is church practice, never identity (decision
0001): the 66 books shared by every church's Bible always, and the
deuterocanonical books when the church's Bible settings include them.
"""

import functools
import gzip
import json
import re
from dataclasses import dataclass
from pathlib import Path

DATA = Path(__file__).parent / "data" / "web.json.gz"
SOURCE = "World English Bible"
MAX_VERSES = 80  # shown and read for one passage; a long one is cut here
SUGGESTIONS = 8


@dataclass(frozen=True)
class Book:
    code: str
    name: str
    aliases: tuple = ()
    deuterocanonical: bool = False


def _book(code, name, *aliases):
    return Book(code, name, aliases)


def _deutero(code, name, *aliases):
    return Book(code, name, aliases, deuterocanonical=True)


BOOKS = (
    _book("GEN", "Genesis", "gen", "ge", "gn"),
    _book("EXO", "Exodus", "exo", "ex", "exod"),
    _book("LEV", "Leviticus", "lev", "le", "lv"),
    _book("NUM", "Numbers", "num", "nu", "nm", "nb"),
    _book("DEU", "Deuteronomy", "deut", "deu", "dt"),
    _book("JOS", "Joshua", "josh", "jos", "jsh"),
    _book("JDG", "Judges", "judg", "jdg", "jg", "jdgs"),
    _book("RUT", "Ruth", "rut", "ru", "rth"),
    _book("1SA", "1 Samuel", "1 sam", "1 sa", "1 sm"),
    _book("2SA", "2 Samuel", "2 sam", "2 sa", "2 sm"),
    _book("1KI", "1 Kings", "1 kgs", "1 ki", "1 kin"),
    _book("2KI", "2 Kings", "2 kgs", "2 ki", "2 kin"),
    _book("1CH", "1 Chronicles", "1 chr", "1 chron", "1 ch"),
    _book("2CH", "2 Chronicles", "2 chr", "2 chron", "2 ch"),
    _book("EZR", "Ezra", "ezr"),
    _book("NEH", "Nehemiah", "neh", "ne"),
    _book("EST", "Esther", "esth", "est", "es"),
    _book("JOB", "Job", "jb"),
    _book("PSA", "Psalms", "psalm", "ps", "psa", "pss", "psm"),
    _book("PRO", "Proverbs", "prov", "pro", "prv", "pr"),
    _book("ECC", "Ecclesiastes", "eccl", "ecc", "ec", "qoh", "qoheleth"),
    _book(
        "SOL",
        "Song of Songs",
        "song",
        "sos",
        "so",
        "song of solomon",
        "canticles",
        "cant",
    ),
    _book("ISA", "Isaiah", "isa", "is"),
    _book("JER", "Jeremiah", "jer", "je", "jr"),
    _book("LAM", "Lamentations", "lam", "la"),
    _book("EZE", "Ezekiel", "ezek", "eze", "ezk"),
    _book("DAN", "Daniel", "dan", "da", "dn"),
    _book("HOS", "Hosea", "hos", "ho"),
    _book("JOE", "Joel", "joe", "jl"),
    _book("AMO", "Amos", "amo", "am"),
    _book("OBA", "Obadiah", "obad", "oba", "ob"),
    _book("JON", "Jonah", "jon", "jnh"),
    _book("MIC", "Micah", "mic", "mc"),
    _book("NAH", "Nahum", "nah", "na"),
    _book("HAB", "Habakkuk", "hab", "hb"),
    _book("ZEP", "Zephaniah", "zeph", "zep", "zp"),
    _book("HAG", "Haggai", "hag", "hg"),
    _book("ZEC", "Zechariah", "zech", "zec", "zc"),
    _book("MAL", "Malachi", "mal", "ml"),
    _deutero("TOB", "Tobit", "tob", "tb"),
    _deutero("JDT", "Judith", "jdt", "jdth"),
    _deutero("ESG", "Esther (Greek)", "esg", "greek esther", "additions to esther"),
    _deutero("WIS", "Wisdom of Solomon", "wisdom", "wis", "ws"),
    _deutero("SIR", "Sirach", "sir", "ecclesiasticus", "ecclus"),
    _deutero("BAR", "Baruch", "bar"),
    _deutero("1MA", "1 Maccabees", "1 macc", "1 mac", "1 ma"),
    _deutero("2MA", "2 Maccabees", "2 macc", "2 mac", "2 ma"),
    _deutero("1ES", "1 Esdras", "1 esd"),
    _deutero("PRM", "Prayer of Manasseh", "pr man", "prayer of manasses", "man"),
    _deutero("PSX", "Psalm 151", "ps151"),
    _deutero("3MA", "3 Maccabees", "3 macc", "3 mac", "3 ma"),
    _deutero("4ES", "2 Esdras", "2 esd", "4 ezra"),
    _deutero("4MA", "4 Maccabees", "4 macc", "4 mac", "4 ma"),
    _deutero("DNG", "Daniel (Greek)", "dng", "greek daniel"),
    _book("MAT", "Matthew", "matt", "mat", "mt"),
    _book("MAR", "Mark", "mrk", "mar", "mk", "mr"),
    _book("LUK", "Luke", "luk", "lk"),
    _book("JOH", "John", "jn", "jhn", "joh"),
    _book("ACT", "Acts", "act", "ac"),
    _book("ROM", "Romans", "rom", "ro", "rm"),
    _book("1CO", "1 Corinthians", "1 cor", "1 co"),
    _book("2CO", "2 Corinthians", "2 cor", "2 co"),
    _book("GAL", "Galatians", "gal", "ga"),
    _book("EPH", "Ephesians", "eph", "ephes"),
    _book("PHI", "Philippians", "phil", "php", "pp"),
    _book("COL", "Colossians", "col"),
    _book("1TH", "1 Thessalonians", "1 thess", "1 thes", "1 th"),
    _book("2TH", "2 Thessalonians", "2 thess", "2 thes", "2 th"),
    _book("1TI", "1 Timothy", "1 tim", "1 ti"),
    _book("2TI", "2 Timothy", "2 tim", "2 ti"),
    _book("TIT", "Titus", "tit"),
    _book("PHM", "Philemon", "philem", "phm", "phlm"),
    _book("HEB", "Hebrews", "heb"),
    _book("JAM", "James", "jas", "jam", "jm"),
    _book("1PE", "1 Peter", "1 pet", "1 pe", "1 pt"),
    _book("2PE", "2 Peter", "2 pet", "2 pe", "2 pt"),
    _book("1JO", "1 John", "1 jn", "1 jhn", "1 joh", "1 jo"),
    _book("2JO", "2 John", "2 jn", "2 jhn", "2 joh", "2 jo"),
    _book("3JO", "3 John", "3 jn", "3 jhn", "3 joh", "3 jo"),
    _book("JUD", "Jude", "jud", "jde"),
    _book("REV", "Revelation", "rev", "re", "apocalypse", "revelations"),
)

_ORDINALS = {
    "i": "1",
    "ii": "2",
    "iii": "3",
    "iv": "4",
    "first": "1",
    "second": "2",
    "third": "3",
    "fourth": "4",
    "1st": "1",
    "2nd": "2",
    "3rd": "3",
    "4th": "4",
}


def normalise(text):
    """Lower case, "John 3.16" as "john 3:16", "I Cor"/"1cor" as "1 cor",
    no dots or brackets, single spaces, en dashes as hyphens."""
    text = re.sub(r"(\d)\.(\d)", r"\1:\2", text.lower())
    text = re.sub(r"[.()]", " ", text)
    text = re.sub(r"[–—]", "-", text)
    text = re.sub(r"\s+", " ", text).strip()
    first, _, rest = text.partition(" ")
    if first in _ORDINALS and rest and rest[0].isalpha():
        text = f"{_ORDINALS[first]} {rest}"
    return re.sub(r"^([1-4])(?=[a-z])", r"\1 ", text)


def _keys(book):
    return [normalise(book.name), *(normalise(alias) for alias in book.aliases)]


def books(deuterocanon=False):
    """The books offered, in order."""
    return [b for b in BOOKS if deuterocanon or not b.deuterocanonical]


@functools.cache
def _index(deuterocanon):
    return {key: book for book in books(deuterocanon) for key in _keys(book)}


@functools.cache
def _chapters():
    with gzip.open(DATA, "rt", encoding="utf-8") as data:
        return json.load(data)["books"]


def chapter_name(book, single=True):
    """The book's name before one chapter's number: "Psalm 23", not
    "Psalms 23"."""
    return "Psalm" if book.code == "PSA" and single else book.name


def chapters(book):
    """The book's chapters, each a list of its verses' text ("" for a verse
    number the source skips)."""
    return _chapters()[book.code]


@dataclass(frozen=True)
class Passage:
    book: Book
    chapter: int
    verse: int | None = None  # None: whole chapters
    end_chapter: int | None = None
    end_verse: int | None = None

    def reference(self):
        single = self.end_chapter in (None, self.chapter)
        start = f"{chapter_name(self.book, single)} {self.chapter}"
        if self.verse is None:
            if self.end_chapter and self.end_chapter != self.chapter:
                return f"{start}-{self.end_chapter}"
            return start
        start += f":{self.verse}"
        if self.end_verse is None:
            return start
        if self.end_chapter and self.end_chapter != self.chapter:
            return f"{start}-{self.end_chapter}:{self.end_verse}"
        return f"{start}-{self.end_verse}" if self.end_verse != self.verse else start

    def verses(self):
        """(chapter, verse, text) for each verse, at most ``MAX_VERSES``."""
        found = []
        all_chapters = chapters(self.book)
        last_chapter = self.end_chapter or self.chapter
        for chapter in range(self.chapter, last_chapter + 1):
            texts = all_chapters[chapter - 1]
            first = self.verse if (self.verse and chapter == self.chapter) else 1
            last = len(texts)
            if chapter == last_chapter and self.end_verse:
                last = self.end_verse
            elif chapter == self.chapter and self.verse and self.end_verse is None:
                last = self.verse
            for number in range(first, last + 1):
                text = texts[number - 1]
                if text:
                    found.append((chapter, number, text))
                if len(found) >= MAX_VERSES:
                    return found
        return found

    def is_cut(self):
        return len(self.verses()) >= MAX_VERSES

    def text(self):
        return " ".join(text for _, _, text in self.verses())


_SPLIT = re.compile(r"^(?P<book>(?:[1-4] ?)?[a-z][a-z ]*?) ?(?P<rest>\d[\d: -]*)?$")
_FULL = re.compile(
    r"^(?P<c1>\d+)(?: ?: ?(?P<v1>\d+))?"
    r"(?: ?- ?(?:(?P<c2>\d+) ?: ?(?P<v2>\d+)|(?P<n2>\d+)))?$"
)


def _valid(passage):
    """``passage`` when its numbers exist in the book, otherwise None."""
    all_chapters = chapters(passage.book)

    def has(chapter, verse=None):
        if not 1 <= chapter <= len(all_chapters):
            return False
        return verse is None or 1 <= verse <= len(all_chapters[chapter - 1])

    end_chapter = passage.end_chapter or passage.chapter
    if not has(passage.chapter, passage.verse) or not has(
        end_chapter, passage.end_verse
    ):
        return None
    start = (passage.chapter, passage.verse or 0)
    if (end_chapter, passage.end_verse or start[1]) < start:
        return None
    return passage


def _passage(book, rest):
    match = _FULL.match(rest.strip())
    if not match:
        return None
    c1, v1 = int(match["c1"]), match["v1"] and int(match["v1"])
    # "Psalm 151" is its own book where it is offered.
    if book.code == "PSA" and c1 == 151:
        book, c1 = next(b for b in BOOKS if b.code == "PSX"), 1
    if match["c2"]:
        if not v1:
            return None
        passage = Passage(book, c1, v1, int(match["c2"]), int(match["v2"]))
    elif match["n2"]:
        n2 = int(match["n2"])
        passage = Passage(book, c1, v1, c1, n2) if v1 else Passage(book, c1, None, n2)
    else:
        passage = Passage(book, c1, v1 or None)
    return _valid(passage)


def parse(reference, *, deuterocanon=False):
    """The passage ``reference`` names, or None when it isn't one ("John
    3:16", "Jn 3:16-18", "1 Cor 13", "Psalm 23", "Rom 8:28-9:2")."""
    match = _SPLIT.match(normalise(reference or ""))
    if not match or not match["rest"]:
        return None
    book = _index(deuterocanon).get(match["book"].strip())
    if book is None:
        return None
    passage = _passage(book, match["rest"])
    if passage and passage.book.deuterocanonical and not deuterocanon:
        return None
    return passage


def passage_text(reference, *, deuterocanon=False):
    """The text of the passage ``reference`` names ("" when it names none)."""
    passage = parse(reference, deuterocanon=deuterocanon)
    return passage.text() if passage else ""


def _snippet(text, length=70):
    return text if len(text) <= length else text[: length - 1].rstrip() + "…"


def _completions(book, rest):
    """Suggestions within ``book`` for the numbers typed so far."""
    rest = rest.strip()
    if "-" in rest:
        passage = _passage(book, rest)
        return [(passage.reference(), _snippet(passage.text()))] if passage else []
    chapter_text, colon, verse_text = rest.partition(":")
    chapter_text, verse_text = chapter_text.strip(), verse_text.strip()
    all_chapters = chapters(book)
    if not colon:
        numbers = [
            n
            for n in range(1, len(all_chapters) + 1)
            if str(n).startswith(chapter_text)
        ]
        return [
            (f"{chapter_name(book)} {n}", f"{len(all_chapters[n - 1])} verses")
            for n in numbers
        ][:SUGGESTIONS]
    chapter = int(chapter_text)
    if not 1 <= chapter <= len(all_chapters):
        return []
    texts = all_chapters[chapter - 1]
    return [
        (f"{chapter_name(book)} {chapter}:{n}", _snippet(texts[n - 1]))
        for n in range(1, len(texts) + 1)
        if str(n).startswith(verse_text) and texts[n - 1]
    ][:SUGGESTIONS]


def suggest(query, *, deuterocanon=False):
    """Up to ``SUGGESTIONS`` (value, description) pairs for what the pastor
    has typed: books by name or abbreviation, then chapters and verses."""
    match = _SPLIT.match(normalise(query or ""))
    if not match:
        return []
    typed, rest = match["book"].strip(), match["rest"]
    exact = _index(deuterocanon).get(typed)
    starting = [
        book
        for book in books(deuterocanon)
        if book != exact and any(key.startswith(typed) for key in _keys(book))
    ]
    if not rest:
        # "phil": Philippians (its abbreviation) first, then Philemon.
        candidates = [exact, *starting] if exact else starting
        return [
            (f"{book.name} ", f"{len(chapters(book))} chapters")
            for book in candidates[:SUGGESTIONS]
        ]
    # With numbers, an exact book name means that book alone. Otherwise each
    # book's best match first ("jo 3": Joshua 3, Job 3, Joel 3, John 3 ...),
    # then the rest of each book's.
    candidates = [exact] if exact else starting
    each = [_completions(book, rest) for book in candidates[:SUGGESTIONS]]
    found = []
    for rank in range(SUGGESTIONS):
        found.extend(options[rank] for options in each if rank < len(options))
    return found[:SUGGESTIONS]
