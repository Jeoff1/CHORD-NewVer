"""Rules for Announcements (Design-Decisions, Phase 8, decided 2026-11-23).

- Everything is inside one church (decision 0014). "Everyone" means
  everyone working in that church. "One service's team" means that
  service's assigned people whose reply is Pending or Accepted, and is
  offered (and shown) only while Teams is switched on.
- An announcement to everyone may be Public: it then also shows on the
  church's homepage.
- Posting is the permission ``announcements.add_announcement``. Reading
  needs none.
- No expiry: only the author archives an announcement, which hides it.
"""

from django.db.models import Q
from django.utils import timezone

from apps.audit.models import AuditEvent
from apps.audit.services import diff, record_change, snapshot
from apps.church.modules import is_enabled
from apps.core.people import display_name
from apps.worship.models import WorshipService

from .models import Announcement

Audience = Announcement.Audience
SERVING = ("pending", "accepted")  # Assignment replies still on the team

AUDIT_FIELDS = {
    "Title": "title",
    "Message": "body",
    "To": lambda announcement: audience_label(announcement),
    "Author": lambda announcement: display_name(announcement.author),
    "Archived": "is_archived",
    "Shown on the homepage": lambda announcement: (
        announcement.visibility == Announcement.Visibility.PUBLIC
    ),
}


class AnnouncementRefused(Exception):
    """An announcement the rules don't allow; the message is for the person."""


def teams_on(church):
    return is_enabled("teams", church)


def audience_label(announcement):
    if announcement.audience == Audience.SERVICE_TEAM:
        return f"The team of {announcement.service}"
    return "Everyone"


def team_services(church):
    """The church's services whose team can be written to: coming and not
    cancelled."""
    return (
        WorshipService.objects.for_church(church)
        .filter(is_cancelled=False, starts_at__gt=timezone.now())
        .order_by("starts_at")
    )


def visible_to(user, church):
    """The announcements of ``church`` that ``user`` sees, newest first:
    every unarchived one for everyone, and, while Teams is on, those for
    the teams they are on (Pending or Accepted) or wrote."""
    shown = Q(audience=Audience.EVERYONE)
    if teams_on(church):
        shown |= Q(audience=Audience.SERVICE_TEAM) & (
            Q(
                service__assignments__person=user,
                service__assignments__reply__in=SERVING,
            )
            | Q(author=user)
        )
    return (
        Announcement.objects.for_church(church)
        .filter(archived_at__isnull=True)
        .filter(shown)
        .select_related("author", "service")
        .distinct()
    )


def post(
    author,
    church,
    *,
    title,
    body,
    audience,
    service=None,
    visibility=Announcement.Visibility.INTERNAL,
):
    if audience == Audience.SERVICE_TEAM:
        word = church.label_set.get("worship_service").lower()
        if not teams_on(church):
            raise AnnouncementRefused(
                f"Announcements to one {word}'s team need the Teams module."
            )
        if service is None or not team_services(church).filter(pk=service.pk).exists():
            raise AnnouncementRefused(f"Choose a coming {word} that isn't cancelled.")
        # Only an announcement to everyone may show on the homepage.
        visibility = Announcement.Visibility.INTERNAL
    else:
        service = None
    announcement = Announcement.objects.create(
        church=church,
        title=title,
        body=body,
        audience=audience,
        service=service,
        author=author,
        visibility=visibility,
    )
    record_change(
        author,
        announcement,
        AuditEvent.Action.CREATED,
        diff({}, snapshot(announcement, AUDIT_FIELDS)),
    )
    return announcement


def archive(announcement, user):
    """Only the author archives; it then shows to nobody."""
    if announcement.author_id != user.pk:
        raise AnnouncementRefused("Only the author can archive it.")
    if announcement.is_archived:
        return announcement
    before = snapshot(announcement, AUDIT_FIELDS)
    announcement.archived_at = timezone.now()
    announcement.save(update_fields=["archived_at", "updated_at"])
    record_change(
        user,
        announcement,
        AuditEvent.Action.CHANGED,
        diff(before, snapshot(announcement, AUDIT_FIELDS)),
    )
    return announcement
