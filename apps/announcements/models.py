"""Announcements: notes to everyone, or to one service's team
(Design-Decisions, Phase 8)."""

from django.conf import settings
from django.db import models

from apps.core.models import PublicIdModel, TimeStampedModel
from apps.worship.models import WorshipService


class Announcement(PublicIdModel, TimeStampedModel):
    """A note posted to everyone signed in, or to one service's assigned
    team. It has no expiry: its author archives it."""

    class Audience(models.TextChoices):
        EVERYONE = "everyone", "Everyone"
        SERVICE_TEAM = "service_team", "One service's team"

    title = models.CharField(max_length=120)
    body = models.TextField("Message")
    audience = models.CharField(
        max_length=20, choices=Audience.choices, default=Audience.EVERYONE
    )
    service = models.ForeignKey(
        WorshipService,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="announcements",
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="+"
    )
    archived_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at", "-pk"]
        # Posting is a permission; reading needs none, and only the author
        # archives.
        default_permissions = ("add",)
        constraints = [
            models.CheckConstraint(
                condition=models.Q(audience="everyone", service__isnull=True)
                | models.Q(audience="service_team", service__isnull=False),
                name="announcement_service_only_for_a_service_team",
            )
        ]

    def __str__(self):
        return self.title

    @property
    def is_archived(self):
        return self.archived_at is not None
