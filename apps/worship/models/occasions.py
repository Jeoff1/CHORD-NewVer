"""Occasion Requests (Phase 9A, A5; decision 0012).

A signed-in person asks for an Occasion: a service made from a template the
church marks as an occasion, such as a wedding or a funeral. A holder of
``worship.approve_occasion`` approves it, which creates the Worship
Service, or declines it with a reason. The requester may withdraw it while
it is Pending. No fees, requirements or church records.
"""

from django.conf import settings
from django.db import models

from apps.core.models import PublicIdModel, TimeStampedModel

from .schedule import ServiceTemplate, WorshipService


class OccasionRequest(PublicIdModel, TimeStampedModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        DECLINED = "declined", "Declined"
        WITHDRAWN = "withdrawn", "Withdrawn"

    requester = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="occasion_requests",
    )
    template = models.ForeignKey(
        ServiceTemplate,
        on_delete=models.PROTECT,
        related_name="occasion_requests",
        verbose_name="Occasion",
    )
    starts_at = models.DateTimeField("Preferred date and start time")
    occasion_for = models.CharField(
        "For",
        max_length=200,
        help_text="Who the occasion is for, such as the couple's names.",
    )
    note = models.TextField(
        blank=True,
        help_text="Anything the church should know. Only people who approve "
        "requests see it.",
    )
    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.PENDING
    )
    decline_reason = models.TextField(blank=True)
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    decided_at = models.DateTimeField(null=True, blank=True)
    # The service approving it created.
    service = models.OneToOneField(
        WorshipService,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="occasion_request",
    )

    class Meta:
        ordering = ["-created_at", "-pk"]
        default_permissions = ()
        permissions = [
            ("request_occasion", "Can request an occasion"),
            ("approve_occasion", "Can approve or decline occasion requests"),
        ]

    def __str__(self):
        return f"{self.template.name} for {self.occasion_for}"

    @property
    def is_pending(self):
        return self.status == self.Status.PENDING
