"""Lineup rules: making a lineup from suggestions, reviewing it, and the
pastor's final say (Design-Decisions, Phase 6; decision 0008).

- A Lineup is a stored copy of a Search Run's placed suggestions. Later
  corrections to the run never change it (workflow review F4).
- Review: swap a song for a ranked alternative, lock a song in place,
  reorder, remove, add a song from the pool, and regenerate around locked
  songs. A lineup never holds two songs with the same title.
- The worship leader (``change_lineup``) or anyone with the final say
  (``finalize_lineup``) confirms. The rules call the final-say holders "the
  pastor", and check only the permission, never a role name.
- The **pastor's lock** starts when the pastor confirms a lineup, or edits
  one that is already confirmed; it stops everyone without the final say
  until the pastor reopens it. The pastor's edits to a draft don't lock
  anyone out.
- An edit to a confirmed lineup keeps it confirmed and marks it with the
  time: "Edited by <pastor Label> (<name>)" for the pastor, "Changed by
  <name>" for anyone else (who may edit only while there is no pastor's
  lock). Only the latest mark shows. Locking or unlocking a song isn't an
  edit.
- Reopening makes the lineup a draft again and lifts the lock and the mark.
  Sending back is the same with a note for the leader, and only the pastor
  may do it. Confirming again clears the note.
- Any pool song can be added except one a person marked "Not a worship
  song"; a song that failed the Worship Check or was never checked gets a
  warning in the review instead (the person's choice wins over the model).
- A cancelled or past service gets no new lineup (F7).

Every function raises ``LineupRefused`` with a message for people when the
action isn't allowed. Views record the audit trail.
"""

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.church.models import ChurchProfile
from apps.songs.cleanup import base_title
from apps.songs.models import Song

from . import sequencing, suggesting
from .models import Lineup, LineupItem, SearchRun

CHANGE = "worship.change_lineup"
FINAL_SAY = "worship.finalize_lineup"
ADDED_FROM_POOL = "Added from the song pool."


class LineupRefused(Exception):
    """The action isn't allowed; the message says why."""


def _labels():
    return ChurchProfile.load().label_set


# --- Who may do what ---------------------------------------------------------


def has_final_say(user):
    return user.has_perm(FINAL_SAY)


def sees_drafts(user):
    """People who plan lineups see them before they are confirmed."""
    return user.has_perm(CHANGE) or has_final_say(user)


def visible_to(lineup, user):
    """Whether ``user`` may see the lineup's songs. Team members see only a
    confirmed lineup (Design-Decisions, Phase 6)."""
    return lineup.is_confirmed or sees_drafts(user)


def may_change(lineup, user):
    """Whether ``user`` may change the lineup's songs now."""
    if not user.has_perm(CHANGE):
        return False
    return not lineup.pastor_locked or has_final_say(user)


def may_confirm(lineup, user):
    return not lineup.is_confirmed and (user.has_perm(CHANGE) or has_final_say(user))


def check_change(lineup, user):
    if may_change(lineup, user):
        return
    labels = _labels()
    if lineup.pastor_locked:
        raise LineupRefused(
            f"The {labels.get('pastor').lower()} has the final say on this "
            f"{labels.get('lineup').lower()}: only people with the final say can "
            "change it until it is reopened."
        )
    raise LineupRefused(
        f"You may not change this {labels.get('lineup').lower()}."
    )  # pragma: no cover (views check the permission first)


def _check_final_say(user):
    if not has_final_say(user):
        raise LineupRefused("Only people with the final say can do this.")


def _edited(lineup, user):
    """After a change to the songs. An edit to a confirmed lineup keeps it
    confirmed and replaces its mark with this one; the pastor's edit also
    puts on the pastor's lock. Edits to a draft leave no mark."""
    if lineup.is_confirmed:
        final_say = has_final_say(user)
        lineup.edited_at, lineup.edited_by = timezone.now(), user
        lineup.edited_with_final_say = final_say
        if final_say:
            lineup.pastor_locked = True
    lineup.save()


def _clear_mark(lineup):
    lineup.edited_at, lineup.edited_by = None, None
    lineup.edited_with_final_say = False


# --- The Worship Check, in the review ----------------------------------------


def marked_not_worship(song):
    """A person marked the song "Not a worship song": it can't be added."""
    return song.is_reviewed and song.worship_check == Song.WorshipCheck.REJECTED


def check_warning(song):
    """The warning a song shows in the review when it hasn't passed the
    Worship Check, or "" when it has. A person's choice wins over the
    model, so these songs may still be added."""
    if song.worship_check == Song.WorshipCheck.ACCEPTED:
        return ""
    if marked_not_worship(song):
        return "Marked as not a worship song."
    if song.worship_check == Song.WorshipCheck.REJECTED:
        return "Didn't pass the worship check."
    return "Not checked as a worship song yet."


def _locked_lineup(lineup):
    """The lineup's row, locked for this transaction, so two people's
    changes never interleave."""
    return Lineup.objects.select_for_update().get(pk=lineup.pk)


# --- Suggestions the lineup draws on ------------------------------------------


def source_run(service):
    """The service's latest finished Search Run, or None."""
    return (
        service.search_runs.filter(status=SearchRun.Status.DONE)
        .order_by("-created_at", "-pk")
        .first()
    )


def _reasons(suggestion, slot_reason=""):
    reasons = list(suggestion.reasons)
    extra = slot_reason or suggestion.slot_reason
    if extra:
        reasons.append(extra)
    return reasons


def _ranked(run):
    """The run's suggestions that still pass the Worship Check, best first."""
    placed, others = suggesting.results(run)
    return sorted([*placed, *others], key=lambda s: s.rank)


def _items(lineup):
    return list(lineup.items.select_related("song", "slot").order_by("position", "pk"))


def _titles(items, exclude=None):
    return {base_title(item.song.title) for item in items if item != exclude}


def alternatives(lineup, item=None):
    """Ranked suggestions that could take ``item``'s place: not already in
    the lineup, and not sharing a title with another of its songs."""
    run = source_run(lineup.service)
    if run is None:
        return []
    items = _items(lineup)
    taken = _titles(items, exclude=item)
    in_lineup = {i.song_id for i in items}
    return [
        s
        for s in _ranked(run)
        if s.song_id not in in_lineup and base_title(s.song.title) not in taken
    ]


def addable_songs(lineup, query=""):
    """Songs from the pool that could be added: not marked "Not a worship
    song" by a person, not in the lineup, and not sharing a title with one
    of its songs."""
    taken = _titles(_items(lineup))
    songs = Song.objects.exclude(lineup_items__lineup=lineup).exclude(
        worship_check=Song.WorshipCheck.REJECTED, reviewed_at__isnull=False
    )
    if query:
        songs = songs.filter(Q(title__icontains=query) | Q(artist__icontains=query))
    return [song for song in songs if base_title(song.title) not in taken]


def open_slots(lineup):
    """The template's slots no song in the lineup fills."""
    filled = {item.slot_id for item in lineup.items.all() if item.slot_id}
    return [s for s in lineup.service.template.slots.all() if s.pk not in filled]


# --- Making a lineup ----------------------------------------------------------


def create_from_run(service, user, run=None):
    """Make the service's lineup from a run's placed suggestions, in slot
    order. Refused for a cancelled or past service (F7), when the service
    already has a lineup, or when no run placed any song."""
    closed = suggesting.planning_closed(service)
    if closed:
        raise LineupRefused(closed)
    labels = _labels()
    lineup_word = labels.get("lineup").lower()
    if Lineup.objects.filter(service=service).exists():
        raise LineupRefused(
            f"This {labels.get('worship_service').lower()} already has a {lineup_word}."
        )
    run = run or source_run(service)
    placed = suggesting.results(run)[0] if run else []
    if not placed:
        raise LineupRefused(
            f"There are no suggested songs to make the {lineup_word} from yet."
        )
    with transaction.atomic():
        lineup = Lineup.objects.create(service=service, run=run)
        LineupItem.objects.bulk_create(
            LineupItem(
                lineup=lineup,
                song=suggestion.song,
                slot=suggestion.slot,
                position=position,
                reasons=_reasons(suggestion),
            )
            for position, suggestion in enumerate(placed)
        )
    return lineup


# --- Review actions -----------------------------------------------------------


def _renumber(items):
    for position, item in enumerate(items):
        if item.position != position:
            item.position = position
            item.save(update_fields=["position"])


def _check_unlocked(item, verb):
    if item.locked:
        raise LineupRefused(f"{item.song.title} is locked; unlock it to {verb} it.")


def _check_title(items, song, exclude=None):
    if base_title(song.title) in _titles(items, exclude=exclude):
        raise LineupRefused(
            f"A song called {song.title} is already in the "
            f"{_labels().get('lineup').lower()}."
        )


def swap(lineup, item, song, user):
    """Put a ranked alternative in place of ``item``'s song. The slot and
    position stay; the key and notes, which were about the old song, go."""
    with transaction.atomic():
        lineup = _locked_lineup(lineup)
        check_change(lineup, user)
        _check_unlocked(item, "swap")
        choice = next((s for s in alternatives(lineup, item) if s.song == song), None)
        if choice is None:
            raise LineupRefused(f"{song.title} isn't one of the ranked choices.")
        item.song = song
        item.reasons = _reasons(choice, slot_reason="")
        item.key, item.notes = "", ""
        item.save()
        _edited(lineup, user)
    return item


def set_locked(lineup, item, locked, user):
    """Lock a song in place, or unlock it. Not an edit to the songs, so it
    doesn't mark the lineup."""
    with transaction.atomic():
        lineup = _locked_lineup(lineup)
        check_change(lineup, user)
        item.locked = locked
        item.save(update_fields=["locked"])
    return item


def move(lineup, item, step, user):
    """Move ``item`` one place up (``step`` -1) or down (+1). The two songs
    trade places and slots, so the slots stay in the service's order."""
    with transaction.atomic():
        lineup = _locked_lineup(lineup)
        check_change(lineup, user)
        items = _items(lineup)
        index = next(i for i, other in enumerate(items) if other.pk == item.pk)
        target = index + step
        if not 0 <= target < len(items):
            raise LineupRefused(f"{item.song.title} can't move further that way.")
        other = items[target]
        _check_unlocked(items[index], "move")
        _check_unlocked(other, "move")
        mine, theirs = items[index], other
        mine.slot, theirs.slot = theirs.slot, mine.slot
        mine.position, theirs.position = theirs.position, mine.position
        mine.save(update_fields=["slot", "position"])
        theirs.save(update_fields=["slot", "position"])
        _edited(lineup, user)


def remove(lineup, item, user):
    """Take a song out; its slot is left empty."""
    with transaction.atomic():
        lineup = _locked_lineup(lineup)
        check_change(lineup, user)
        _check_unlocked(item, "remove")
        item.delete()
        _renumber(_items(lineup))
        _edited(lineup, user)


def add_from_pool(lineup, song, slot, user):
    """Add a pool song into an empty slot of the service's template or,
    with no slot, at the end. Any song may be added except one a person
    marked "Not a worship song"; one that failed the Worship Check or was
    never checked shows a warning in the review (``check_warning``)."""
    with transaction.atomic():
        lineup = _locked_lineup(lineup)
        check_change(lineup, user)
        if marked_not_worship(song):
            raise LineupRefused(
                f"{song.title} was marked as not a worship song, so it can't be added."
            )
        items = _items(lineup)
        if any(i.song_id == song.pk for i in items):
            raise LineupRefused(f"{song.title} is already in it.")
        _check_title(items, song)
        if slot is not None and slot not in open_slots(lineup):
            raise LineupRefused(f"The {slot.name} slot already has a song.")
        item = LineupItem(
            lineup=lineup, song=song, slot=slot, reasons=[ADDED_FROM_POOL]
        )
        # Before the first song whose slot comes later in the service.
        index = len(items)
        if slot is not None:
            index = next(
                (
                    i
                    for i, other in enumerate(items)
                    if other.slot is None or other.slot.position > slot.position
                ),
                len(items),
            )
        item.position = index
        item.save()
        _renumber([*items[:index], item, *items[index:]])
        _edited(lineup, user)
    return item


def set_details(lineup, item, key, notes, user):
    """The song's service key and notes."""
    with transaction.atomic():
        lineup = _locked_lineup(lineup)
        check_change(lineup, user)
        item.key, item.notes = key, notes
        item.save(update_fields=["key", "notes"])
        _edited(lineup, user)
    return item


def regenerate(lineup, user):
    """Fill the lineup again from the service's latest suggestions, keeping
    every locked song where it is."""
    with transaction.atomic():
        lineup = _locked_lineup(lineup)
        check_change(lineup, user)
        run = source_run(lineup.service)
        if run is None:
            raise LineupRefused("Find songs first: there are no suggestions yet.")
        kept = [item for item in _items(lineup) if item.locked]
        kept_titles = _titles(kept)
        kept_songs = {item.song_id for item in kept}
        filled = {item.slot_id for item in kept if item.slot_id}
        slots = [
            slot
            for slot in lineup.service.template.slots.all()
            if slot.pk not in filled
        ]
        candidates = [
            s
            for s in _ranked(run)
            if s.song_id not in kept_songs
            and base_title(s.song.title) not in kept_titles
        ]
        placements = sequencing.place(
            candidates, slots, feel_weight=suggesting.feel_weight(run)
        )
        lineup.items.filter(locked=False).delete()
        new = [
            LineupItem.objects.create(
                lineup=lineup,
                song=candidates[p.index].song,
                slot=p.slot,
                reasons=_reasons(candidates[p.index], slot_reason=p.reason),
            )
            for p in placements
        ]
        order = sorted(
            [*kept, *new],
            key=lambda i: (
                i.slot is None,
                i.slot.position if i.slot else 0,
                i.position,
            ),
        )
        _renumber(order)
        lineup.run = run
        _edited(lineup, user)
    return lineup


# --- Confirmation and the final say ---------------------------------------------


def confirm(lineup, user):
    """Confirm the lineup. The pastor's confirmation puts on the pastor's
    lock; the leader's doesn't."""
    with transaction.atomic():
        lineup = _locked_lineup(lineup)
        lineup_word = _labels().get("lineup").lower()
        if lineup.is_confirmed:
            raise LineupRefused(f"This {lineup_word} is already confirmed.")
        if not may_confirm(lineup, user):
            raise LineupRefused(f"You may not confirm this {lineup_word}.")
        if lineup.service.is_cancelled:
            raise LineupRefused(suggesting.planning_closed(lineup.service))
        if not lineup.items.exists():
            raise LineupRefused(f"Add a song before confirming the {lineup_word}.")
        lineup.status = Lineup.Status.CONFIRMED
        lineup.confirmed_at, lineup.confirmed_by = timezone.now(), user
        lineup.pastor_locked = has_final_say(user)
        lineup.sent_back_note, lineup.sent_back_at, lineup.sent_back_by = "", None, None
        lineup.save()
    return lineup


def _back_to_draft(lineup):
    lineup.status = Lineup.Status.DRAFT
    lineup.pastor_locked = False
    _clear_mark(lineup)


def reopen(lineup, user):
    """Make a confirmed lineup a draft again and lift the pastor's lock.
    Team members then see a note that it is being revised."""
    with transaction.atomic():
        lineup = _locked_lineup(lineup)
        _check_final_say(user)
        if not lineup.is_confirmed:
            raise LineupRefused(
                f"This {_labels().get('lineup').lower()} isn't confirmed."
            )
        _back_to_draft(lineup)
        lineup.save()
    return lineup


def send_back(lineup, note, user):
    """Return the lineup to draft with a note for the worship leader.
    Sending back a confirmed lineup reopens it."""
    note = note.strip()
    with transaction.atomic():
        lineup = _locked_lineup(lineup)
        _check_final_say(user)
        if not note:
            raise LineupRefused("Write a note saying what to change.")
        _back_to_draft(lineup)
        lineup.sent_back_note = note
        lineup.sent_back_at, lineup.sent_back_by = timezone.now(), user
        lineup.save()
    return lineup


# --- The audit trail ------------------------------------------------------------


def _songs(lineup):
    return "; ".join(
        f"{item.position + 1}. "
        + (f"{item.slot.name}: " if item.slot else "")
        + f"{item.song.title} ({item.song.artist})"
        + (f", key {item.key}" if item.key else "")
        + (", locked" if item.locked else "")
        for item in _items(lineup)
    )


LINEUP_AUDIT_FIELDS = {
    "Status": lambda lineup: lineup.get_status_display(),
    "Songs": _songs,
    "Song notes": lambda lineup: "; ".join(
        f"{item.song.title}: {item.notes}" for item in _items(lineup) if item.notes
    ),
    "Locked for the final say": "pastor_locked",
    "Sent back with the note": "sent_back_note",
}
