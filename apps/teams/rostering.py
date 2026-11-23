"""Rules for the team roster (Design-Decisions, Phase 8, decided 2026-11-23).

- **Who can be assigned:** only active people whose Team Profile has the
  part, never on one of their Blackout Dates, and once per part at a
  service.
- **Replies:** an assignment starts Pending; the assigned person accepts or
  declines it once. A declined assignment stays on the service page for the
  leader to fill.
- **Cancelled or past services** take no new assignments, no replies and
  no removals, so their team stays as it was.
- **Blackout Dates** are whole days in the church's time zone. One that
  covers a day the person already serves on (a Pending or Accepted
  assignment at a service that isn't cancelled) is refused.

Assigning and adding a blackout lock the person's row, so the two can't
pass each other and leave someone assigned on a blacked-out day.
"""

import datetime

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone

from apps.audit.models import AuditEvent
from apps.audit.services import diff, record_change, snapshot
from apps.church.models import ChurchProfile
from apps.core.people import display_name
from apps.worship.scheduling import church_time_zone

from .models import Assignment, BlackoutDate, TeamPart, TeamProfile

Reply = Assignment.Reply
SERVING = (Reply.PENDING, Reply.ACCEPTED)

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


class RosterRefused(Exception):
    """A roster change the rules don't allow; the message is for the person."""


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


# --- Team Profiles ------------------------------------------------------------


def parts_of(person):
    profile = TeamProfile.objects.filter(user=person).first()
    return list(profile.parts.all()) if profile else []


def set_parts(person, parts, actor):
    """Make ``parts`` the person's Team Profile, with an audit entry."""
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
    """Everyone active whose Team Profile has ``part``, each with the reason
    they can't be assigned to it at ``service`` ("" when they can)."""
    people = (
        get_user_model()
        .objects.filter(is_active=True, team_profile__parts=part)
        .order_by("first_name", "last_name", "username")
    )
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
    Pending. Raises ``RosterRefused`` when the rules don't allow it."""
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
    still change."""
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
    return assignment


def remove(assignment, actor):
    """Take an assignment off the service, while its team can still change."""
    closed = roster_closed(assignment.service)
    if closed:
        raise RosterRefused(closed)
    record_change(
        actor,
        assignment,
        AuditEvent.Action.DELETED,
        diff(snapshot(assignment, ASSIGNMENT_AUDIT_FIELDS), {}),
    )
    assignment.delete()


def service_team(service):
    return service.assignments.select_related("person", "part")


def upcoming_assignments(person):
    """The person's assignments from today on, soonest first."""
    start, _ = day_bounds(church_today(), church_today())
    return (
        Assignment.objects.filter(person=person, service__starts_at__gte=start)
        .select_related("service", "part")
        .order_by("service__starts_at", "part__sort_order", "pk")
    )


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
    days are the wrong way round, already passed, or cover an assignment."""
    if ends_on < starts_on:
        raise RosterRefused("The last day can't be before the first.")
    if ends_on < church_today():
        raise RosterRefused("These days have already passed.")
    with transaction.atomic():
        _lock(person)
        conflicts = list(blackout_conflicts(person, starts_on, ends_on))
        if conflicts:
            raise RosterRefused(_conflict_message(conflicts))
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
