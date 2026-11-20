"""Chord sheet rules: who may add one, approval, and Find chords
(Design-Decisions, Phase 7).

- A sheet may be added at any time, for any song in the pool, by someone
  who may approve sheets (``songs.approve_chordsheet``, a permission, never a
  role name): theirs is approved at once.
- Someone who may only add sheets (``songs.add_chordsheet``, team members by
  default) may paste one for a song in a confirmed lineup that has no
  approved sheet. It waits as **pending**: other team members can't see it
  until someone who may approve sheets approves it.
- A song has at most one approved sheet. A sheet is required once its song
  is in a confirmed lineup: the lineup shows which songs still lack one.
- The text is checked as ChordPro on the server; a chords-over-words chart
  is converted first (``chords.py``).
- Find chords links to searches on free sources, opened in the browser.
  Nothing is fetched or scraped.
"""

from urllib.parse import quote_plus

from django.db import transaction
from django.utils import timezone

from . import chords
from .models import ChordSheet

ADD = "songs.add_chordsheet"
APPROVE = "songs.approve_chordsheet"
VIEW = "songs.view_chordsheet"
Status = ChordSheet.Status


class SheetRefused(Exception):
    """The action isn't allowed, or the text isn't a chord sheet; the
    message says why."""


def may_approve(user):
    return user.has_perm(APPROVE)


def approved_sheet(song):
    return song.chord_sheets.approved().first()


def in_confirmed_lineup(song):
    """Whether the song is in the confirmed lineup of a service that isn't
    cancelled: once it is, it needs a chord sheet."""
    from apps.worship.models import Lineup, LineupItem

    return LineupItem.objects.filter(
        song=song,
        lineup__status=Lineup.Status.CONFIRMED,
        lineup__service__is_cancelled=False,
    ).exists()


def may_add(user, song):
    """Whether ``user`` may add (or replace) a sheet for ``song`` now."""
    if not user.has_perm(ADD):
        return False
    if may_approve(user):
        return True
    return in_confirmed_lineup(song) and approved_sheet(song) is None


def pending_for(song, user):
    """The pending sheets ``user`` may see: all of them for someone who may
    approve; otherwise only their own."""
    pending = song.chord_sheets.pending().select_related("added_by")
    if may_approve(user):
        return list(pending)
    return list(pending.filter(added_by=user)) if user.is_authenticated else []


def convert(text):
    """``(chordpro, kept)``: the text as ChordPro, with every bracket that
    isn't a chord or a chart mark kept as written ([*text]); ``kept``
    lists ``(line, text)`` for those."""
    return chords.keep_unread(chords.to_chordpro(text or ""))


def kept_message(kept):
    """The warning for marks kept as written, or ""."""
    if not kept:
        return ""
    listed = ", ".join(f"line {number} “{text}”" for number, text in kept)
    return f"These marks were kept as written and won't transpose: {listed}."


def prepare(text, key=""):
    """``(chordpro, key name, kept)`` from a pasted text and the chosen key:
    converted to ChordPro when needed, unknown marks kept as written, then
    checked. Only what breaks the ChordPro itself (an unclosed bracket or
    directive) is refused. The key comes from the form, or else from the
    sheet's own {key: …}."""
    chordpro, kept = convert(text)
    try:
        chords.check(chordpro)
    except chords.ChordProError as error:
        raise SheetRefused(str(error)) from error
    named = chords.key_directive(chordpro)
    key = key or named
    if not key:
        raise SheetRefused("Choose the key the sheet is written in.")
    try:
        chosen = chords.Key.parse(key)
    except ValueError as error:
        raise SheetRefused(f"“{key}” isn't a key.") from error
    if named:
        try:
            written = chords.Key.parse(named)
        except ValueError:
            written = None
        if written is not None and written != chosen:
            raise SheetRefused(
                f"The sheet says it is in {written.name}, but {chosen.name} was "
                "chosen. Choose the key it is written in."
            )
    return chordpro, chosen.name, kept


IMPORT_EXTENSIONS = (".cho", ".chopro", ".chordpro", ".pro", ".txt")
IMPORT_MAX_BYTES = 200 * 1024


def read_import(uploaded):
    """``(text, key name)`` from an uploaded ChordPro file, for the person
    to check in the form before saving. The file itself is never stored.
    The key comes from its {key: …} or {k: …} line, or is "" when it has
    none (or names no real key). Other directives stay in the text."""
    name = uploaded.name or ""
    if not name.lower().endswith(IMPORT_EXTENSIONS):
        raise SheetRefused(
            "Choose a ChordPro file: .cho, .chopro, .chordpro, .pro or .txt."
        )
    if uploaded.size > IMPORT_MAX_BYTES:
        raise SheetRefused(
            f"The file is too large ({uploaded.size // 1024} KB; the most is "
            f"{IMPORT_MAX_BYTES // 1024} KB)."
        )
    raw = uploaded.read(IMPORT_MAX_BYTES + 1)
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise SheetRefused(
            "The file isn't UTF-8 text. Save it as UTF-8 (in most editors: Save "
            "as, then Encoding: UTF-8) and import it again."
        ) from error
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    if not text.strip():
        raise SheetRefused("The file is empty.")
    if len(text) > chords.MAX_LENGTH:
        raise SheetRefused(
            f"The chord sheet in the file is too long ({len(text)} characters; "
            f"the most is {chords.MAX_LENGTH})."
        )
    try:
        key = chords.Key.parse(chords.key_directive(text)).name
    except ValueError:
        key = ""
    return text, key


def save(song, user, text, key=""):
    """Add or replace ``song``'s sheet from ``user``. Returns the sheet:
    approved at once for someone who may approve, pending otherwise. Its
    ``kept`` lists the marks kept as written (not stored)."""
    if not may_add(user, song):
        raise SheetRefused(
            "You can add a chord sheet only for a song in a confirmed lineup "
            "that doesn't have one yet."
        )
    chordpro, key, kept = prepare(text, key)
    with transaction.atomic():
        if may_approve(user):
            sheet = approved_sheet(song) or ChordSheet(song=song, added_by=user)
            sheet.status = Status.APPROVED
            sheet.approved_by, sheet.approved_at = user, timezone.now()
        else:
            sheet = song.chord_sheets.pending().filter(added_by=user).first()
            sheet = sheet or ChordSheet(song=song, added_by=user)
        sheet.chordpro, sheet.key = chordpro, key
        sheet.save()
    sheet.kept = kept
    return sheet


def approve(sheet, user):
    """Approve a pending sheet; the team can see it from now on."""
    if not may_approve(user):
        raise SheetRefused("Only people who may approve chord sheets can do this.")
    with transaction.atomic():
        sheet = ChordSheet.objects.select_for_update().get(pk=sheet.pk)
        if sheet.is_approved:
            raise SheetRefused("This chord sheet is already approved.")
        if approved_sheet(sheet.song) is not None:
            raise SheetRefused(
                "This song already has an approved chord sheet. Edit that one, "
                "or discard this one."
            )
        sheet.status = Status.APPROVED
        sheet.approved_by, sheet.approved_at = user, timezone.now()
        sheet.save()
    return sheet


def discard(sheet, user):
    """Delete a pending sheet."""
    if not may_approve(user):
        raise SheetRefused("Only people who may approve chord sheets can do this.")
    if sheet.is_approved:
        raise SheetRefused("An approved chord sheet can be edited, not discarded.")
    sheet.delete()


def find_chords_links(song):
    """``(label, URL)`` searches for the song's chords on free sources, for
    the browser to open in a new tab. The server fetches nothing."""
    words = f"{song.title} {song.artist}".strip()
    return [
        (
            "Ultimate Guitar",
            "https://www.ultimate-guitar.com/search.php?search_type=title&value="
            + quote_plus(song.title),
        ),
        (
            "Worship Together",
            "https://duckduckgo.com/?q="
            + quote_plus(f"site:worshiptogether.com {song.title} chords"),
        ),
        ("The web", "https://duckduckgo.com/?q=" + quote_plus(f"{words} chords")),
    ]


SHEET_AUDIT_FIELDS = {
    # Never the ChordPro text: chord sheets are copyrighted.
    "Song": lambda sheet: sheet.song.title,
    "Status": lambda sheet: sheet.get_status_display(),
    "Original key": "key",
}
