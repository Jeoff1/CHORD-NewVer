"""Upcoming services on a church's homepage (Phase 9B): only when the
church switches it on, and only each service's date, time and kind (its
template's name). Never its theme, lineup, songs or team."""

from dataclasses import dataclass

from django.utils import timezone

from apps.church.homepage import Section
from apps.church.modules import is_enabled

from .models import WorshipService
from .scheduling import church_time_zone

SHOWN = 5


@dataclass(frozen=True)
class PublicService:
    """All the homepage knows of a service."""

    starts_at: object  # in the church's time zone
    kind: str


def upcoming(church):
    if not (church.show_upcoming_services and is_enabled("worship", church)):
        return []
    zone = church_time_zone(church)
    services = (
        WorshipService.objects.for_church(church)
        .filter(is_cancelled=False, starts_at__gte=timezone.now())
        .select_related("template")
        .order_by("starts_at")[:SHOWN]
    )
    return [
        PublicService(timezone.localtime(s.starts_at, zone), s.template.name)
        for s in services
    ]


def homepage_section(church, request):
    services = upcoming(church)
    if not services:
        return None
    return Section(
        template="worship/includes/homepage_upcoming.html",
        context={"upcoming": services},
        order=10,
        slot="side",
    )
