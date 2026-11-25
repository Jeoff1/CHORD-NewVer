"""Rules for the team roster (Design-Decisions, Phase 8, decided 2026-11-23).

- **Who is on the team:** only holders of ``teams.view_assignment`` (a
  permission, never a role name) can have a Team Profile or Blackout Dates,
  be assigned or take a swap.
- **Who can be assigned:** only active team people whose Team Profile has
  the part, never on one of their Blackout Dates, and once per part at a
  service. The person is notified (unless they assigned themself).
- **Replies:** an assignment starts Pending; the assigned person accepts or
  declines it once. A declined assignment stays on the service page for the
  leader to fill.
- **Cancelled or past services** take no new assignments, replies,
  removals or swaps, so their team stays as it was.
- **Blackout Dates** are whole days in the church's time zone. One that
  covers a day the person already serves on (a Pending or Accepted
  assignment at a service that isn't cancelled) is refused.
- **Swap Requests:** someone Pending or Accepted asks to be replaced, and
  may withdraw while it is open. The first person who has the part, isn't
  blacked out that day and isn't already on that service takes it, with no
  approval: their new assignment is Accepted, and the original one ends.

Assigning, taking a swap and adding a blackout lock the person's row, so
they can't pass each other; taking a swap also locks the request's row, so
only the first of two people pressing at once gets it.
"""

import datetime

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone

from apps.accounts.roles import users_with_perm
from apps.audit.models import AuditEvent
from apps.audit.services import diff, record_change, snapshot
from apps.church.models import ChurchProfile
from apps.core.people import display_name
from apps.worship.scheduling import church_time_zone

from . import notifying
from .models import Assignment, BlackoutDate, SwapRequest, TeamPart, TeamProfile

Reply = Assignment.Reply
SERVING = (Reply.PENDING, Reply.ACCEPTED)
# Holders of this permission are the team: they can have a Team Profile and
# Blackout Dates, be assigned and take swaps.
TEAM_PERMISSION = "teams.view_assignment"

ASSIGNMENT_AUDIT_FIELDS = {
    "Person": lambda assignment: display_name(assignment.person),
    "Team part": "part",
    "Service": "service",
    "Reply": lambda assignment: assignment.get_reply_display(),
}
PROFILE_AUDIT_FIELDS = {
    "Person": lambda profile: display_name(profile.user),
    "Team parts": lambda profile: profile.parts.all(),
}
BLACKOUT_AUDIT_FIELDS = {
    "Person": lambda blackout: display_name(blackout.person),
    "Dates": lambda blackout: blackout.date_range(),
    "Note": "note",
}
SWAP_AUDIT_FIELDS = {
    "Team part": "part",
    "Service": "service",
    "Handed over by": lambda swap: display_name(swap.requested_by),
    "Status": lambda swap: swap.get_status_display(),
    "Taken by": lambda swap: display_name(swap.taken_by) if swap.taken_by else "",
}


class RosterRefused(Exception):
    """A roster change the rules don't allow; the message is for the person.
    ``assignment`` names the assignment that stood in the way, if any."""

    def __init__(self, message, *, assignment=None):
        super().__init__(message)
        self.assignment = assignment


def _service_word():
    return ChurchProfile.load().label_set.get("worship_service").lower()


def roster_closed(service):
    """Why the service's team can't change any more, or "" when it can."""
    if service.is_cancelled:
        return f"This {_service_word()} is cancelled, so its team can't change."
    if service.has_started:
        return (
            f"This {_service_word()} has already taken place, so its team can't change."
        )
    return ""


def church_today():
    return timezone.localdate(timezone=church_time_zone())


def service_day(service):
    """The service's date in the church's time zone."""
    return timezone.localtime(service.starts_at, church_time_zone()).date()


def day_bounds(starts_on, ends_on):
    """The moments that start ``starts_on`` and end ``ends_on``, in the
    church's time zone."""
    zone = church_time_zone()
    start = datetime.datetime.combine(starts_on, datetime.time.min, tzinfo=zone)
    end = datetime.datetime.combine(
        ends_on + datetime.timedelta(days=1), datetime.time.min, tzinfo=zone
    )
    return start, end


def _blacked_out(day):
    return BlackoutDate.objects.filter(starts_on__lte=day, ends_on__gte=day)


def _lock(person):
    """Lock the person's row until the transaction ends."""
    get_user_model().objects.select_for_update().filter(pk=person.pk).first()


# --- The team -------------------------------------------------------------------


def may_serve(user):
    """Whether ``user`` is on the team: active, holding ``TEAM_PERMISSION``."""
    return user.is_active and user.has_perm(TEAM_PERMISSION)


def team_people():
    """Active users holding ``TEAM_PERMISSION`` through a role, or as
    superusers. Teams is open only to the first church for now (Phase 9B,
    decision 0014)."""
    return users_with_perm(
        ChurchProfile.load(), TEAM_PERMISSION, include_superusers=True
    )


def _not_on_team(person):
    return f"{display_name(person)} isn't on the team, so has no Team Profile."


# --- Team Profiles ------------------------------------------------------------


def parts_of(person):
    profile = TeamProfile.objects.filter(user=person).first()
    return list(profile.parts.all()) if profile else []


def set_parts(person, parts, actor):
    """Make ``parts`` the person's Team Profile, with an audit entry."""
    if not may_serve(person):
        raise RosterRefused(_not_on_team(person))
    profile, is_new = TeamProfile.objects.get_or_create(user=person)
    before = {} if is_new else snapshot(profile, PROFILE_AUDIT_FIELDS)
    profile.parts.set(parts)
    record_change(
        actor,
        profile,
        AuditEvent.Action.CREATED if is_new else AuditEvent.Action.CHANGED,
        diff(before, snapshot(profile, PROFILE_AUDIT_FIELDS)),
    )
    return profile


# --- Assignments --------------------------------------------------------------


def candidates(service, part):
    """The team people whose Team Profile has ``part``, each with the reason
    they can't be assigned to it at ``service`` ("" when they can). People
    without ``TEAM_PERMISSION`` are left out, even with a profile."""
    people = team_people().filter(team_profile__parts=part)
    people = sorted(people, key=lambda p: (p.first_name, p.last_name, p.get_username()))
    blacked_out = set(
        _blacked_out(service_day(service)).values_list("person_id", flat=True)
    )
    assigned = set(
        Assignment.objects.filter(service=service, part=part).values_list(
            "person_id", flat=True
        )
    )
    return [
        (person, _reason(service, part, person, blacked_out, assigned))
        for person in people
    ]


def _reason(service, part, person, blacked_out, assigned):
    if person.pk in assigned:
        return f"Already assigned to {part} at this {_service_word()}."
    if person.pk in blacked_out:
        day = service_day(service)
        return f"Can't serve on {day:%b} {day.day}, a blackout date."
    return ""


def unavailable_reason(service, part, person):
    """Why ``person`` can't take ``part`` at ``service``, or ""."""
    if not person.is_active:
        return f"{display_name(person)}'s account is deactivated."
    if not may_serve(person):
        return f"{display_name(person)} isn't on the team."
    if not TeamProfile.objects.filter(user=person, parts=part).exists():
        return f"{display_name(person)}'s Team Profile doesn't have {part}."
    mine = {person.pk}
    blacked_out = (
        mine if _blacked_out(service_day(service)).filter(person=person) else set()
    )
    assigned = (
        mine
        if Assignment.objects.filter(service=service, part=part, person=person)
        else set()
    )
    reason = _reason(service, part, person, blacked_out, assigned)
    return f"{display_name(person)}: {reason}" if reason else ""


def assign(service, part, person, actor):
    """Assign ``person`` to ``part`` at ``service``; their reply starts
    Pending and they are notified. Raises ``RosterRefused`` when the rules
    don't allow it."""
    closed = roster_closed(service)
    if closed:
        raise RosterRefused(closed)
    if not part.is_active:
        raise RosterRefused(f"{part} is switched off, so nobody can be assigned to it.")
    try:
        with transaction.atomic():
            _lock(person)
            reason = unavailable_reason(service, part, person)
            if reason:
                raise RosterRefused(reason)
            assignment = Assignment.objects.create(
                service=service, part=part, person=person, assigned_by=actor
            )
            notifying.assigned(assignment, actor)
    except IntegrityError as error:
        raise RosterRefused(
            f"Already assigned to {part} at this {_service_word()}."
        ) from error
    record_change(
        actor,
        assignment,
        AuditEvent.Action.CREATED,
        diff({}, snapshot(assignment, ASSIGNMENT_AUDIT_FIELDS)),
    )
    return assignment


def reply(assignment, person, answer):
    """The assigned person accepts or declines, once, while the service can
    still change. Declining withdraws an open swap request for it."""
    if assignment.person_id != person.pk:
        raise RosterRefused("Only the person assigned can reply.")
    if answer not in (Reply.ACCEPTED, Reply.DECLINED):
        raise RosterRefused("Choose Accept or Decline.")
    closed = roster_closed(assignment.service)
    if closed:
        raise RosterRefused(closed)
    if assignment.reply != Reply.PENDING:
        raise RosterRefused(
            f"You've already {assignment.get_reply_display().lower()} this."
        )
    with transaction.atomic():
        before = snapshot(assignment, ASSIGNMENT_AUDIT_FIELDS)
        assignment.reply = answer
        assignment.replied_at = timezone.now()
        assignment.save(update_fields=["reply", "replied_at", "updated_at"])
        record_change(
            person,
            assignment,
            AuditEvent.Action.CHANGED,
            diff(before, snapshot(assignment, ASSIGNMENT_AUDIT_FIELDS)),
        )
        if answer == Reply.DECLINED:
            _withdraw_open_swaps(assignment, person)
    return assignment


def remove(assignment, actor):
    """Take an assignment off the service, while its team can still change.
    An open swap request for it is withdrawn."""
    closed = roster_closed(assignment.service)
    if closed:
        raise RosterRefused(closed)
    with transaction.atomic():
        _withdraw_open_swaps(assignment, actor)
        record_change(
            actor,
            assignment,
            AuditEvent.Action.DELETED,
            diff(snapshot(assignment, ASSIGNMENT_AUDIT_FIELDS), {}),
        )
        assignment.delete()


def service_team(service):
    return service.assignments.select_related("person", "part").prefetch_related(
        "swap_requests"
    )


def upcoming_assignments(person):
    """The person's assignments from today on, soonest first."""
    start, _ = day_bounds(church_today(), church_today())
    return (
        Assignment.objects.filter(person=person, service__starts_at__gte=start)
        .select_related("service", "part")
        .prefetch_related("swap_requests")
        .order_by("service__starts_at", "part__sort_order", "pk")
    )


def open_swap(assignment):
    """The assignment's open swap request, or None."""
    return assignment.open_swap_request


# --- Swap Requests --------------------------------------------------------------


def swap_refusal(assignment, person):
    """Why ``person`` can't ask for a swap of ``assignment``, or ""."""
    if assignment.person_id != person.pk:
        return "Only the person assigned can ask for a swap."
    if assignment.reply not in SERVING:
        return "A declined assignment can't be swapped."
    closed = roster_closed(assignment.service)
    if closed:
        return closed
    if open_swap(assignment):
        return "You've already asked for a swap."
    return ""


def request_swap(assignment, person):
    """Ask to be replaced in ``assignment``. Anyone eligible can take it."""
    refusal = swap_refusal(assignment, person)
    if refusal:
        raise RosterRefused(refusal)
    try:
        with transaction.atomic():
            swap = SwapRequest.objects.create(
                assignment=assignment,
                service=assignment.service,
                part=assignment.part,
                requested_by=person,
            )
    except IntegrityError as error:
        raise RosterRefused("You've already asked for a swap.") from error
    record_change(
        person,
        swap,
        AuditEvent.Action.CREATED,
        diff({}, snapshot(swap, SWAP_AUDIT_FIELDS)),
    )
    return swap


def _close(swap, status, actor, *, taken_by=None):
    before = snapshot(swap, SWAP_AUDIT_FIELDS)
    swap.status = status
    swap.taken_by = taken_by
    swap.closed_at = timezone.now()
    swap.save()
    record_change(
        actor,
        swap,
        AuditEvent.Action.CHANGED,
        diff(before, snapshot(swap, SWAP_AUDIT_FIELDS)),
    )


def _locked_swap(swap):
    return (
        SwapRequest.objects.select_for_update(of=("self",))
        .select_related("service", "part", "requested_by", "assignment")
        .get(pk=swap.pk)
    )


def _no_longer_open(swap):
    if swap.status == SwapRequest.Status.TAKEN:
        return "Someone else took this swap first."
    return "This swap request was withdrawn."


def withdraw_swap(swap, person):
    """The person who asked takes the request back, while it is open."""
    with transaction.atomic():
        swap = _locked_swap(swap)
        if swap.requested_by_id != person.pk:
            raise RosterRefused("Only the person who asked can withdraw it.")
        if not swap.is_open:
            raise RosterRefused(_no_longer_open(swap))
        _close(swap, SwapRequest.Status.WITHDRAWN, person)
    return swap


def _withdraw_open_swaps(assignment, actor):
    for swap in (
        SwapRequest.objects.select_for_update(of=("self",))
        .select_related("service", "part", "requested_by")
        .filter(assignment=assignment, status=SwapRequest.Status.OPEN)
    ):
        _close(swap, SwapRequest.Status.WITHDRAWN, actor)


def take_refusal(swap, person):
    """Why ``person`` can't take ``swap``, or "" when they can: they need
    the part, mustn't be blacked out that day or already on that service."""
    if not swap.is_open:
        return _no_longer_open(swap)
    closed = roster_closed(swap.service)
    if closed:
        return closed
    if swap.requested_by_id == person.pk:
        return "This is your own swap request."
    if not may_serve(person):
        return "Only people on the team can take a swap."
    if not TeamProfile.objects.filter(user=person, parts=swap.part).exists():
        return f"Your Team Profile doesn't have {swap.part}."
    if _blacked_out(service_day(swap.service)).filter(person=person).exists():
        return "That day is one of your blackout dates."
    if Assignment.objects.filter(service=swap.service, person=person).exists():
        return f"You're already on this {_service_word()}."
    return ""


def swaps_open_to(person):
    """The open swap requests ``person`` may take, soonest first."""
    if not may_serve(person):
        return []
    swaps = SwapRequest.objects.filter(
        status=SwapRequest.Status.OPEN,
        service__is_cancelled=False,
        service__starts_at__gt=timezone.now(),
        part__profiles__user=person,
    ).select_related("service", "part", "requested_by")
    return [swap for swap in swaps if not take_refusal(swap, person)]


def take_swap(swap, person):
    """``person`` takes the swap: the original assignment ends, and they get
    the part as Accepted. Only the first of two people at once gets it."""
    with transaction.atomic():
        swap = _locked_swap(swap)
        _lock(person)
        refusal = take_refusal(swap, person)
        if refusal:
            raise RosterRefused(refusal)
        original = swap.assignment
        record_change(
            person,
            original,
            AuditEvent.Action.DELETED,
            diff(snapshot(original, ASSIGNMENT_AUDIT_FIELDS), {}),
        )
        original.delete()
        swap.assignment = None
        taken = Assignment.objects.create(
            service=swap.service,
            part=swap.part,
            person=person,
            reply=Reply.ACCEPTED,
            replied_at=timezone.now(),
            assigned_by=swap.requested_by,
        )
        record_change(
            person,
            taken,
            AuditEvent.Action.CREATED,
            diff({}, snapshot(taken, ASSIGNMENT_AUDIT_FIELDS)),
        )
        _close(swap, SwapRequest.Status.TAKEN, person, taken_by=person)
    return taken


# --- Blackout Dates -----------------------------------------------------------


def blackout_conflicts(person, starts_on, ends_on):
    """The person's assignments a blackout from ``starts_on`` to ``ends_on``
    would cover: Pending or Accepted, at services that aren't cancelled."""
    start, end = day_bounds(starts_on, ends_on)
    return (
        Assignment.objects.filter(
            person=person,
            reply__in=SERVING,
            service__is_cancelled=False,
            service__starts_at__gte=start,
            service__starts_at__lt=end,
        )
        .select_related("service", "part")
        .order_by("service__starts_at")
    )


def _conflict_message(conflicts):
    first = conflicts[0]
    if first.reply == Reply.PENDING:
        step = "Decline it on My schedule first"
    else:
        step = "You've accepted it, so ask for a swap first"
    more = len(conflicts) - 1
    others = f" (and {more} more)" if more else ""
    return (
        f"You're assigned to {first.part} at {first.service}{others}, inside "
        f"these dates. {step}."
    )


def add_blackout(person, starts_on, ends_on, note=""):
    """Add a Blackout Date for ``person``. Raises ``RosterRefused`` when the
    person isn't on the team, or the days are the wrong way round, already
    passed, or cover an assignment (named in ``RosterRefused.assignment``)."""
    if not may_serve(person):
        raise RosterRefused("Only people on the team have blackout dates.")
    if ends_on < starts_on:
        raise RosterRefused("The last day can't be before the first.")
    if ends_on < church_today():
        raise RosterRefused("These days have already passed.")
    with transaction.atomic():
        _lock(person)
        conflicts = list(blackout_conflicts(person, starts_on, ends_on))
        if conflicts:
            raise RosterRefused(_conflict_message(conflicts), assignment=conflicts[0])
        blackout = BlackoutDate.objects.create(
            person=person, starts_on=starts_on, ends_on=ends_on, note=note
        )
    record_change(
        person,
        blackout,
        AuditEvent.Action.CREATED,
        diff({}, snapshot(blackout, BLACKOUT_AUDIT_FIELDS)),
    )
    return blackout


def remove_blackout(blackout, person):
    if blackout.person_id != person.pk:
        raise RosterRefused("Only the person can remove their blackout dates.")
    record_change(
        person,
        blackout,
        AuditEvent.Action.DELETED,
        diff(snapshot(blackout, BLACKOUT_AUDIT_FIELDS), {}),
    )
    blackout.delete()


def upcoming_blackouts(person):
    return BlackoutDate.objects.filter(person=person, ends_on__gte=church_today())


def usable_parts(current=()):
    """Active Team Parts, plus ``current`` ones so editing keeps them."""
    ids = [part.pk for part in current]
    return TeamPart.objects.filter(Q(is_active=True) | Q(pk__in=ids))


def swap_url(assignment):
    return reverse("teams:swap_request", kwargs={"public_id": assignment.public_id})
