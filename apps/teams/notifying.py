"""In-app Notifications (Design-Decisions, Phase 8). Never email or SMS.

They go to a service's assigned people whose reply is Pending or Accepted,
never to the person who caused them, when:

- the lineup is confirmed;
- a confirmed lineup is edited, by the pastor ("Edited by <pastor Label>")
  or anyone else ("Changed by");

and to a person when they are assigned to a service. Nothing is sent for
a cancelled or past service, or while Teams is switched off. Lineup edits
are collapsed: a person with an unread note about the same lineup's edits
gets it updated, not another one.
"""

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

from apps.church.models import ChurchProfile
from apps.church.modules import is_enabled
from apps.core.people import display_name
from apps.worship import signals

from .models import Assignment, Notification

SERVING = (Assignment.Reply.PENDING, Assignment.Reply.ACCEPTED)


def notify(people, text, url="", *, key=""):
    """Give each of ``people`` a Notification. With ``key``, an unread one
    with the same key is brought up to date instead."""
    now = timezone.now()
    for person in people:
        updated = 0
        if key:
            updated = Notification.objects.filter(
                recipient=person, key=key, read_at__isnull=True
            ).update(text=text, url=url, created_at=now, updated_at=now)
        if not updated:
            Notification.objects.create(recipient=person, text=text, url=url, key=key)


def _open(service):
    return is_enabled("teams") and not (service.is_cancelled or service.has_started)


def serving_people(service, *, exclude=None):
    """The service's active assigned people who are Pending or Accepted."""
    people = get_user_model().objects.filter(
        is_active=True,
        assignments__service=service,
        assignments__reply__in=SERVING,
    )
    if exclude is not None:
        people = people.exclude(pk=exclude.pk)
    return people.distinct()


def assigned(assignment, actor):
    """Tell the person they were assigned, unless they did it themself."""
    if actor is not None and actor.pk == assignment.person_id:
        return
    if not _open(assignment.service):
        return
    notify(
        [assignment.person],
        f"You were assigned to {assignment.part} at {assignment.service}.",
        reverse("teams:my_schedule"),
    )


def lineup_text(lineup, user, event):
    labels = ChurchProfile.load().label_set
    word = labels.get("lineup").lower()
    service = lineup.service
    if event == signals.CONFIRMED:
        return f"The {word} for {service} was confirmed."
    who = display_name(user)
    if lineup.edited_with_final_say:
        who = f"{labels.get('pastor')} ({who})"
    verb = "edited" if lineup.edited_with_final_say else "changed"
    return f"The confirmed {word} for {service} was {verb} by {who}."


def on_lineup_changed(sender, lineup, user, event, **kwargs):
    """Receiver for ``apps.worship.signals.lineup_changed``."""
    service = lineup.service
    if not lineup.is_confirmed or not _open(service):
        return
    key = f"lineup-edited:{lineup.pk}" if event == signals.EDITED else ""
    notify(
        serving_people(service, exclude=user),
        lineup_text(lineup, user, event),
        reverse("worship:lineup", kwargs={"public_id": service.public_id}),
        key=key,
    )


def unread_count(user):
    return Notification.objects.filter(recipient=user, read_at__isnull=True).count()


def mark_read(notification):
    if notification.read_at is None:
        notification.read_at = timezone.now()
        notification.save(update_fields=["read_at", "updated_at"])


def mark_all_read(user):
    return Notification.objects.filter(recipient=user, read_at__isnull=True).update(
        read_at=timezone.now()
    )
