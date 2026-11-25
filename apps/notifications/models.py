from django.conf import settings
from django.db import models

from apps.church.scoping import church_scoped_manager
from apps.core.models import TimeStampedModel


class Notification(TimeStampedModel):
    """A note in the app for one person. Never sent by email or SMS.

    Core, not part of a Module: any Module may send one, and people see
    them whichever Modules are switched on (Phase 9A, A5; before, they were
    part of Teams).
    """

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications"
    )
    # The church it is about; empty for one about the person's own account
    # (decision 0014).
    church = models.ForeignKey(
        "church.ChurchProfile",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="+",
    )
    text = models.CharField(max_length=300)
    url = models.CharField(max_length=300, blank=True)
    # A repeat with the same key replaces an unread one instead of piling up.
    key = models.CharField(max_length=100, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)

    objects = church_scoped_manager()
    church_path = "church"

    class Meta:
        ordering = ["-created_at", "-pk"]
        default_permissions = ()
        indexes = [
            models.Index(fields=["recipient", "read_at"], name="notif_unread_idx")
        ]

    def __str__(self):
        return self.text

    @property
    def is_read(self):
        return self.read_at is not None
