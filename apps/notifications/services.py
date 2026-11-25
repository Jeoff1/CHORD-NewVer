"""Sending and reading in-app Notifications. Never email or SMS.

Each Module decides when to send one (Teams: ``apps/teams/notifying.py``;
Worship: occasion requests) and calls ``notify``.
"""

from django.utils import timezone

from .models import Notification


def notify(people, text, url="", *, church, key=""):
    """Give each of ``people`` a Notification about something in ``church``
    (None for one about the person's own account). With ``key``, an unread
    one with the same key in the same church is brought up to date
    instead."""
    now = timezone.now()
    for person in people:
        updated = 0
        if key:
            updated = Notification.objects.filter(
                recipient=person, church=church, key=key, read_at__isnull=True
            ).update(text=text, url=url, created_at=now, updated_at=now)
        if not updated:
            Notification.objects.create(
                recipient=person, church=church, text=text, url=url, key=key
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
