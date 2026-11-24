"""Rules for the worship schedule: weekly scheduling, the calendar grid and
what the audit trail records."""

import calendar
import datetime
import zoneinfo
from dataclasses import dataclass, field

from django.db import transaction
from django.utils import timezone

from apps.audit.models import AuditEvent
from apps.audit.services import diff, record_change, snapshot
from apps.church.models import ChurchProfile

from .models import WorshipService

MAX_WEEKS_AHEAD = 26


def church_time_zone():
    return zoneinfo.ZoneInfo(ChurchProfile.load().time_zone)


def format_moment(value):
    """A date and time in the church's wording style: Nov 22, 2026 9:00 AM."""
    if value is None:
        return ""
    local = timezone.localtime(value, church_time_zone())
    hour = local.hour % 12 or 12
    return f"{local:%b} {local.day}, {local.year} {hour}:{local:%M %p}"


SERVICE_AUDIT_FIELDS = {
    "Name": "name",
    "Template": "template",
    "Date and time": lambda service: format_moment(service.starts_at),
    "Rehearsal": lambda service: format_moment(service.rehearsal_at),
    "Notes": "notes",
    "Headcount": "attendance",
    "Cancelled": "is_cancelled",
}
THEME_AUDIT_FIELDS = {
    "Title": "title",
    "Main scripture": "scripture",
    "Notes": "notes",
    "Series": "series",
}
TEMPLATE_AUDIT_FIELDS = {
    "Name": "name",
    "Description": "description",
    "Usual day": lambda template: template.get_weekday_display() or "",
    "Usual start time": lambda template: (
        f"{template.start_time:%H:%M}" if template.start_time else ""
    ),
    "Usual length (minutes)": "length_minutes",
    "Order": "sort_order",
    "Active": "is_active",
    "Song slots": lambda template: " / ".join(str(s) for s in template.slots.all()),
}


@transaction.atomic
def schedule_ahead(template, weeks, actor, *, today=None):
    """Create the template's services for the next ``weeks`` weeks.

    Dates that already have this template's service are left alone, so
    running it again only fills the gaps. Returns the services created.
    """
    if not template.repeats_weekly:
        raise ValueError("The template has no usual day and time.")
    zone = church_time_zone()
    today = today or timezone.localdate(timezone=zone)
    first = today + datetime.timedelta(days=(template.weekday - today.weekday()) % 7)
    created = []
    for week in range(min(weeks, MAX_WEEKS_AHEAD)):
        day = first + datetime.timedelta(weeks=week)
        starts_at = datetime.datetime.combine(day, template.start_time, tzinfo=zone)
        service, is_new = WorshipService.objects.get_or_create(
            template=template, starts_at=starts_at, defaults={"name": template.name}
        )
        if is_new:
            record_change(
                actor,
                service,
                AuditEvent.Action.CREATED,
                diff({}, snapshot(service, SERVICE_AUDIT_FIELDS)),
            )
            created.append(service)
    return created


@dataclass
class CalendarDay:
    date: datetime.date
    in_month: bool
    is_today: bool
    services: list = field(default_factory=list)
    # Other Modules' bookings on this day (``bookings.Booking``).
    bookings: list = field(default_factory=list)


def month_grid(year, month, services, *, bookings=(), today=None):
    """Weeks of ``CalendarDay`` for one month, Sunday first, holding the
    given services and other bookings on their local dates."""
    zone = church_time_zone()
    today = today or timezone.localdate(timezone=zone)
    by_date, others = {}, {}
    for service in services:
        local_date = timezone.localtime(service.starts_at, zone).date()
        by_date.setdefault(local_date, []).append(service)
    for booking in sorted(bookings, key=lambda b: b.starts_at):
        local_date = timezone.localtime(booking.starts_at, zone).date()
        others.setdefault(local_date, []).append(booking)
    weeks = calendar.Calendar(firstweekday=calendar.SUNDAY).monthdatescalendar(
        year, month
    )
    return [
        [
            CalendarDay(
                date=day,
                in_month=day.month == month,
                is_today=day == today,
                services=by_date.get(day, []),
                bookings=others.get(day, []),
            )
            for day in week
        ]
        for week in weeks
    ]


def month_bounds(year, month):
    """The aware datetimes covering every day the month's grid shows."""
    zone = church_time_zone()
    weeks = calendar.Calendar(firstweekday=calendar.SUNDAY).monthdatescalendar(
        year, month
    )
    first, last = weeks[0][0], weeks[-1][-1]
    start = datetime.datetime.combine(first, datetime.time.min, tzinfo=zone)
    end = datetime.datetime.combine(
        last + datetime.timedelta(days=1), datetime.time.min, tzinfo=zone
    )
    return start, end


def shift_month(year, month, delta):
    index = year * 12 + (month - 1) + delta
    return index // 12, index % 12 + 1
