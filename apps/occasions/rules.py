"""Rules for Occasions (Phase 9A, A5; decision 0013).

- Every Occasion books the time from its start for its length. A worship
  service books its template's length. A new or moved Occasion, a request
  and an approval are refused when their time overlaps a booking that
  isn't cancelled; back-to-back times are fine.
- ``occasions.view_occasion`` shows an Occasion's details; everyone else
  sees only "Booked" on the calendar.
- Requesting is ``occasions.request_occasion``; approving or declining is
  ``occasions.approve_occasion``. Permissions, never role names.
- The requester gets a Notification when the request is approved or
  declined.
"""

import datetime

from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from apps.accounts.roles import users_with_perm
from apps.audit.models import AuditEvent
from apps.audit.services import diff, record_change, snapshot
from apps.church.modules import is_enabled
from apps.core.locks import BOOKINGS, wait_for_transaction_lock
from apps.core.people import display_name
from apps.notifications.services import notify
from apps.worship.bookings import Booking
from apps.worship.models import WorshipService
from apps.worship.models.schedule import MAX_LENGTH_MINUTES
from apps.worship.scheduling import church_time_zone, format_moment

from .models import Occasion, OccasionRequest, OccasionType

VIEW = "occasions.view_occasion"
REQUEST = "occasions.request_occasion"
APPROVE = "occasions.approve_occasion"

Status = OccasionRequest.Status

OCCASION_AUDIT_FIELDS = {
    "Occasion": "occasion_type",
    "Date and time": lambda occasion: format_moment(
        occasion.starts_at, occasion.church
    ),
    "Length (minutes)": "length_minutes",
    "For": "occasion_for",
    "Officiant": lambda occasion: (
        display_name(occasion.officiant) if occasion.officiant_id else ""
    ),
    "Venue": "venue",
    "Notes": "notes",
    "Cancelled": "is_cancelled",
}
REQUEST_AUDIT_FIELDS = {
    "Occasion": "occasion_type",
    "Date and time": lambda request: format_moment(request.starts_at, request.church),
    "For": "occasion_for",
    "Note": "note",
    "Status": lambda request: request.get_status_display(),
    "Reason": "decline_reason",
    "Booked as": lambda request: str(request.occasion) if request.occasion else "",
}


class OccasionRefused(Exception):
    """Something the rules don't allow; the message says why."""


def can_see(user, church):
    """Whether ``user`` sees ``church``'s Occasions in full. Asked of the
    booking's own church, never the person's Current Church: someone from
    another church sees only "Booked" (Phase 9B)."""
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return user.is_active
    return users_with_perm(church, VIEW).filter(pk=user.pk).exists()


def requestable_types(church):
    return OccasionType.objects.for_church(church).active()


# --- Booked time --------------------------------------------------------------


def clashes(church, starts_at, ends_at, *, exclude=None):
    """The church's bookings that aren't cancelled and overlap
    ``starts_at`` to ``ends_at``: worship services and Occasions, soonest
    first. Each church has its own calendar. ``exclude`` is an Occasion
    being moved."""
    earliest = starts_at - datetime.timedelta(minutes=MAX_LENGTH_MINUTES)
    window = {"starts_at__lt": ends_at, "starts_at__gt": earliest}
    services = WorshipService.objects.for_church(church).filter(
        is_cancelled=False, **window
    )
    occasions = Occasion.objects.for_church(church).filter(is_cancelled=False, **window)
    if exclude is not None and exclude.pk:
        occasions = occasions.exclude(pk=exclude.pk)
    found = [
        *services.select_related("template"),
        *occasions.select_related("occasion_type"),
    ]
    return sorted(
        (booking for booking in found if booking.ends_at > starts_at),
        key=lambda booking: booking.starts_at,
    )


def _clock(value, church):
    local = timezone.localtime(value, church_time_zone(church))
    return f"{local.hour % 12 or 12}:{local:%M %p}"


def in_church(user, church):
    """Whether ``user`` is one of ``church``'s people (an active Membership,
    or a superuser)."""
    if not user.is_authenticated:
        return False
    return (
        user.is_superuser
        or user.memberships.filter(church=church, is_active=True).exists()
    )


def clash_message(found, user):
    """Why a time can't be booked. A worship service is named for the
    church's own people; an Occasion only for those who may see Occasions.
    Anyone else, such as someone requesting from the church's homepage,
    reads only "already booked" (Phase 9B)."""
    booking = found[0]
    hidden = (
        not can_see(user, booking.church)
        if isinstance(booking, Occasion)
        else not in_church(user, booking.church)
    )
    if hidden:
        return "That time is already booked. Choose another date or time."
    name = (
        booking.name
        if isinstance(booking, WorshipService)
        else str(booking.occasion_type.name)
    )
    start = timezone.localtime(booking.starts_at, church_time_zone(booking.church))
    return (
        f"That time overlaps {name}, booked on {start:%b} {start.day} from "
        f"{_clock(booking.starts_at, booking.church)} to "
        f"{_clock(booking.ends_at, booking.church)}. Choose "
        "another date or time."
    )


def _check_free(church, starts_at, ends_at, user, *, exclude=None):
    found = clashes(church, starts_at, ends_at, exclude=exclude)
    if found:
        raise OccasionRefused(clash_message(found, user))


def _ends(starts_at, minutes):
    return starts_at + datetime.timedelta(minutes=minutes)


# --- Occasions ------------------------------------------------------------------


def save_occasion(occasion, actor, *, before=None):
    """Add a new Occasion or save changes to one, refusing a time that
    overlaps another booking (a cancelled one books nothing)."""
    is_new = occasion.pk is None
    with transaction.atomic():
        wait_for_transaction_lock(BOOKINGS)
        if not occasion.is_cancelled:
            _check_free(
                occasion.church,
                occasion.starts_at,
                occasion.ends_at,
                actor,
                exclude=occasion,
            )
        occasion.save()
        record_change(
            actor,
            occasion,
            AuditEvent.Action.CREATED if is_new else AuditEvent.Action.CHANGED,
            diff(before or {}, snapshot(occasion, OCCASION_AUDIT_FIELDS)),
        )
    return occasion


def calendar_source(start, end, church, user):
    """The church's Occasions starting between ``start`` and ``end``, as
    Bookings for its Worship calendar: in full for people who may see them,
    otherwise only "Booked" (and nothing for a cancelled one)."""
    if not is_enabled("occasions", church):
        return []
    occasions = (
        Occasion.objects.for_church(church)
        .filter(starts_at__gte=start, starts_at__lt=end)
        .select_related("occasion_type")
    )
    if not can_see(user, church):
        return [
            Booking(occasion.starts_at, occasion.ends_at)
            for occasion in occasions
            if not occasion.is_cancelled
        ]
    return [
        Booking(
            occasion.starts_at,
            occasion.ends_at,
            label=f"{occasion.occasion_type.name}: {occasion.occasion_for}",
            url=reverse("occasions:detail", kwargs={"public_id": occasion.public_id}),
            is_cancelled=occasion.is_cancelled,
        )
        for occasion in occasions
    ]


# --- Requests -------------------------------------------------------------------


def request_occasion(requester, occasion_type, starts_at, occasion_for, note=""):
    """Send an Occasion Request; it is Pending until someone decides."""
    if not occasion_type.is_active:
        raise OccasionRefused("That occasion can't be requested.")
    if starts_at <= timezone.now():
        raise OccasionRefused("Choose a date and time that hasn't passed yet.")
    church = occasion_type.church
    _check_free(
        church, starts_at, _ends(starts_at, occasion_type.length_minutes), requester
    )
    request = OccasionRequest.objects.create(
        church=church,
        requester=requester,
        occasion_type=occasion_type,
        starts_at=starts_at,
        occasion_for=occasion_for,
        note=note,
    )
    record_change(
        requester,
        request,
        AuditEvent.Action.CREATED,
        diff({}, snapshot(request, REQUEST_AUDIT_FIELDS)),
        church=church,
    )
    _tell_approvers(request)
    return request


def _tell_approvers(request):
    """The church's people who approve requests hear of a new one."""
    approvers = users_with_perm(request.church, APPROVE).exclude(
        pk=request.requester_id
    )
    notify(
        approvers,
        f"{display_name(request.requester)} asked for "
        f"{request.occasion_type.name} on {_day(request.starts_at, request.church)}."[
            :300
        ],
        reverse("occasions:decide", kwargs={"public_id": request.public_id}),
        church=request.church,
    )


def _locked_pending(request):
    locked = OccasionRequest.objects.select_for_update(of=("self",)).get(pk=request.pk)
    if not locked.is_pending:
        raise OccasionRefused(
            f"This request was already {locked.get_status_display().lower()}."
        )
    return locked


def _day(value, church):
    local = timezone.localtime(value, church_time_zone(church))
    return f"{local:%b} {local.day}, {local.year}"


def _tell_requester(request, text):
    # My requests across every church: the requester may belong to another
    # church, or to none (Phase 9B).
    notify(
        [request.requester],
        text[:300],
        reverse("public_requests:my_requests"),
        church=request.church,
    )


def approve(request, actor, *, starts_at=None, officiant=None, venue=""):
    """Approve a Pending request: book its Occasion, at the time the
    approver chose (the requested one by default)."""
    with transaction.atomic():
        wait_for_transaction_lock(BOOKINGS)
        locked = _locked_pending(request)
        before = snapshot(locked, REQUEST_AUDIT_FIELDS)
        starts_at = starts_at or locked.starts_at
        if starts_at <= timezone.now():
            raise OccasionRefused("Choose a date and time that hasn't passed yet.")
        occasion = Occasion(
            church=locked.church,
            occasion_type=locked.occasion_type,
            starts_at=starts_at,
            length_minutes=locked.occasion_type.length_minutes,
            occasion_for=locked.occasion_for,
            officiant=officiant,
            venue=venue,
            notes=locked.note,
        )
        _check_free(occasion.church, occasion.starts_at, occasion.ends_at, actor)
        occasion.save()
        record_change(
            actor,
            occasion,
            AuditEvent.Action.CREATED,
            diff({}, snapshot(occasion, OCCASION_AUDIT_FIELDS)),
        )
        locked.status = Status.APPROVED
        locked.occasion = occasion
        locked.decided_by = actor
        locked.decided_at = timezone.now()
        locked.save()
        record_change(
            actor,
            locked,
            AuditEvent.Action.CHANGED,
            diff(before, snapshot(locked, REQUEST_AUDIT_FIELDS)),
        )
        _tell_requester(
            locked,
            f"Your request for {locked.occasion_type.name} at {locked.church.name} "
            f"on {_day(starts_at, locked.church)} "
            f"was approved by {display_name(actor)}.",
        )
    return occasion


def decline(request, actor, reason):
    """Decline a Pending request, with the reason the requester will read."""
    reason = (reason or "").strip()
    if not reason:
        raise OccasionRefused("Give the reason, for the person who asked.")
    with transaction.atomic():
        locked = _locked_pending(request)
        before = snapshot(locked, REQUEST_AUDIT_FIELDS)
        locked.status = Status.DECLINED
        locked.decline_reason = reason
        locked.decided_by = actor
        locked.decided_at = timezone.now()
        locked.save()
        record_change(
            actor,
            locked,
            AuditEvent.Action.CHANGED,
            diff(before, snapshot(locked, REQUEST_AUDIT_FIELDS)),
        )
        _tell_requester(
            locked,
            f"Your request for {locked.occasion_type.name} at {locked.church.name} "
            f"on {_day(locked.starts_at, locked.church)} was declined: {reason}",
        )
    return locked


def withdraw(request, person):
    """The requester takes back their own Pending request."""
    if request.requester_id != person.pk:
        raise OccasionRefused("Only the person who asked can withdraw it.")
    with transaction.atomic():
        locked = _locked_pending(request)
        before = snapshot(locked, REQUEST_AUDIT_FIELDS)
        locked.status = Status.WITHDRAWN
        locked.save()
        record_change(
            person,
            locked,
            AuditEvent.Action.CHANGED,
            diff(before, snapshot(locked, REQUEST_AUDIT_FIELDS)),
        )
    return locked


def pending_count(church):
    return (
        OccasionRequest.objects.for_church(church).filter(status=Status.PENDING).count()
    )
