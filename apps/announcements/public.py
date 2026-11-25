"""Announcements on a church's homepage (Phase 9B): only Public ones to
everyone that aren't archived, while Announcements is switched on."""

from apps.church.homepage import Section
from apps.church.modules import is_enabled

from .models import Announcement

SHOWN = 5


def public_announcements(church):
    if not is_enabled("announcements", church):
        return Announcement.objects.none()
    return Announcement.objects.for_church(church).filter(
        audience=Announcement.Audience.EVERYONE,
        visibility=Announcement.Visibility.PUBLIC,
        archived_at__isnull=True,
    )


def homepage_section(church, request):
    shown = list(public_announcements(church)[:SHOWN])
    if not shown:
        return None
    return Section(
        template="announcements/includes/homepage_public.html",
        context={"public_announcements": shown},
        order=30,
    )
