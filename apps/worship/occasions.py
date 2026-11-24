"""Occasions and their requests (Phase 9A, A5; decision 0012).

- An **Occasion** is a Worship Service made from a template the church marks
  as an occasion (``ServiceTemplate.is_occasion``), such as a wedding.
- Every service books the time from its start for its template's length.
  A request, or an approval, that overlaps a booked time of a service that
  isn't cancelled is refused.
- Requesting is ``worship.request_occasion``; approving or declining is
  ``worship.approve_occasion``. Both are permissions, never role names.
- Only people who may see occasions (``can_see_occasions``) see an
  occasion's details; everyone else sees "Booked".
- The requester gets a Notification when the request is approved or
  declined.
"""

import datetime

from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from apps.audit.models import AuditEvent
from apps.audit.services import diff, record_change, snapshot
from apps.core.locks import BOOKINGS, wait_for_transaction_lock
from apps.core.people import display_name
from apps.notifications.services import notify

from .models import OccasionRequest, ServiceTemplate, WorshipService
from .models.schedule import MAX_LENGTH_MINUTES
from .scheduling import SERVICE_AUDIT_FIELDS, format_moment

REQUEST = "worship.request_occasion"
APPROVE = "worship.approve_occasion"
# Holding any of these shows an occasion's details: the people who plan
# services, play at them, approve them or record their headcount.
SEE_DETAILS = (
    "worship.change_worshipservice",
    "worship.view_lineup",
    APPROVE,
    "worship.record_attendance",
)

Status = OccasionRequest.Status

REQUEST_AUDIT_FIELDS = {
    "Occasion": "template",
    "Date and time": lambda request: format_moment(request.starts_at),
    "For": "occasion_for",
    "Note": "note",
    "Status": lambda request: request.get_status_display(),
    "Reason": "decline_reason",
    "Service": lambda request: str(request.service) if request.service else "",
}


class OccasionRefused(Exception):
    """A request, approval, decline or withdrawal the rules don't allow."""


def can_see_occasions(user):
    return any(user.has_perm(permission) for permission in SEE_DETAILS)


def occasion_templates():
    """The occasions people may request now: active occasion templates."""
    return ServiceTemplate.objects.active().filter(is_occasion=True)


def ends_at(template, starts_at):
    return starts_at + datetime.timedelta(minutes=template.length_minutes)


def clashes(starts_at, finishes_at, *, exclude=None):
    """Services that aren't cancelled and whose booked time overlaps
    ``starts_at`` to ``finishes_at``, soonest first."""
    earliest = starts_at - datetime.timedelta(minutes=MAX_LENGTH_MINUTES)
    nearby = (
        WorshipService.objects.filter(
            is_cancelled=False, starts_at__lt=finishes_at, starts_at__gt=earliest
        )
        .select_related("template")
        .order_by("starts_at")
    )
    return [
        service
        for service in nearby
        if service.ends_at > starts_at and service.pk != getattr(exclude, "pk", None)
    ]


def clash_message(services, user):
    """Why a time can't be booked, naming the clash only for people who may
    see it."""
    service = services[0]
    if service.is_occasion and not can_see_occasions(user):
        return "That time is already booked. Choose another date or time."
    start = timezone.localtime(service.starts_at)
    return (
        f"That time overlaps {service.name}, booked on {start:%b} {start.day} "
        f"from {_clock(service.starts_at)} to {_clock(service.ends_at)}. "
        "Choose another date or time."
    )


def _clock(value):
    local = timezone.localtime(value)
    return f"{local.hour % 12 or 12}:{local:%M %p}"


def _check_time(template, starts_at, user, *, exclude=None):
    if starts_at <= timezone.now():
        raise OccasionRefused("Choose a date and time that hasn't passed yet.")
    found = clashes(starts_at, ends_at(template, starts_at), exclude=exclude)
    if found:
        raise OccasionRefused(clash_message(found, user))


def request_occasion(requester, template, starts_at, occasion_for, note=""):
    """Send an Occasion Request; it is Pending until someone decides."""
    if not (template.is_occasion and template.is_active):
        raise OccasionRefused("That occasion can't be requested.")
    _check_time(template, starts_at, requester)
    occasion = OccasionRequest.objects.create(
        requester=requester,
        template=template,
        starts_at=starts_at,
        occasion_for=occasion_for,
        note=note,
    )
    record_change(
        requester,
        occasion,
        AuditEvent.Action.CREATED,
        diff({}, snapshot(occasion, REQUEST_AUDIT_FIELDS)),
    )
    return occasion


def _locked_pending(occasion):
    locked = OccasionRequest.objects.select_for_update(of=("self",)).get(pk=occasion.pk)
    if not locked.is_pending:
        raise OccasionRefused(
            f"This request was already {locked.get_status_display().lower()}."
        )
    return locked


def _when(occasion):
    local = timezone.localtime(occasion.starts_at)
    return f"{local:%b} {local.day}, {local.year}"


def _tell_requester(occasion, text):
    notify([occasion.requester], text, reverse("worship:my_occasions"))


def approve(occasion, actor, *, starts_at=None, name="", officiant=None, venue=""):
    """Approve a Pending request: create its Worship Service, at the date
    and time the approver chose (the requested one by default)."""
    with transaction.atomic():
        # One booking at a time, so two approvals can't take the same time.
        wait_for_transaction_lock(BOOKINGS)
        locked = _locked_pending(occasion)
        before = snapshot(locked, REQUEST_AUDIT_FIELDS)
        starts_at = starts_at or locked.starts_at
        _check_time(locked.template, starts_at, actor)
        service = WorshipService.objects.create(
            template=locked.template,
            name=name or f"{locked.template.name}: {locked.occasion_for}"[:120],
            starts_at=starts_at,
            occasion_for=locked.occasion_for,
            officiant=officiant,
            venue=venue,
        )
        record_change(
            actor,
            service,
            AuditEvent.Action.CREATED,
            diff({}, snapshot(service, SERVICE_AUDIT_FIELDS)),
        )
        locked.status = Status.APPROVED
        locked.service = service
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
            f"Your request for {locked.template.name} on {_when(service)} was "
            f"approved by {display_name(actor)}.",
        )
    return service


def decline(occasion, actor, reason):
    """Decline a Pending request, with the reason the requester will read."""
    reason = (reason or "").strip()
    if not reason:
        raise OccasionRefused("Give the reason, for the person who asked.")
    with transaction.atomic():
        locked = _locked_pending(occasion)
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
            f"Your request for {locked.template.name} on {_when(locked)} was "
            f"declined: {reason}"[:300],
        )
    return locked


def withdraw(occasion, person):
    """The requester takes back their own Pending request."""
    if occasion.requester_id != person.pk:
        raise OccasionRefused("Only the person who asked can withdraw it.")
    with transaction.atomic():
        locked = _locked_pending(occasion)
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


def pending_count():
    return OccasionRequest.objects.filter(status=Status.PENDING).count()
