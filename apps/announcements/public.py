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
    """The profile's Announcements tab: the latest public ones, newest first.
    While the Module is on the tab is always there, with a short note when
    there is nothing yet (redesign, 27 Nov 2026)."""
    if not is_enabled("announcements", church):
        return None
    shown = list(public_announcements(church)[:SHOWN])
    return Section(
        template="announcements/includes/homepage_public.html",
        context={"public_announcements": shown},
        order=10,
        slot="tab",
        label="Announcements",
        count=len(shown),
        icon="megaphone",
    )
