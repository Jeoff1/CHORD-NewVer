"""Occasions (Phase 9A, A5; decision 0013).

Special services such as weddings, baptisms and funerals are not worship
services: they have no theme, song lineup or team. Each is an **Occasion**
of a church-edited **Occasion Type**. It books time on the Worship
calendar, and a time that overlaps a worship service or another occasion
can't be booked. People may ask for one with an **Occasion Request**.
"""

import datetime

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

from apps.core.models import PublicIdModel, TimeStampedModel
from apps.core.setting_lists import ChoiceItem
from apps.worship.models.schedule import MAX_LENGTH_MINUTES


def length_field(**kwargs):
    return models.PositiveSmallIntegerField(
        "Length (minutes)",
        validators=[MinValueValidator(15), MaxValueValidator(MAX_LENGTH_MINUTES)],
        **kwargs,
    )


class OccasionType(ChoiceItem):
    """A kind of occasion the church holds, such as a wedding, with how long
    it usually takes."""

    length_minutes = length_field(
        default=90,
        help_text="How long it usually takes. The calendar books this much "
        "time from its start.",
    )

    class Meta(ChoiceItem.Meta):
        pass


class Occasion(PublicIdModel, TimeStampedModel):
    """One special service on one date. Seen in full only with
    ``occasions.view_occasion``; everyone else sees "Booked"."""

    occasion_type = models.ForeignKey(
        OccasionType,
        on_delete=models.PROTECT,
        related_name="occasions",
        verbose_name="Occasion",
    )
    starts_at = models.DateTimeField("Date and time")
    length_minutes = length_field(
        blank=True,
        help_text="Leave blank to use the occasion's usual length.",
    )
    occasion_for = models.CharField(
        "For",
        max_length=200,
        help_text="Who it is for, such as the couple's names.",
    )
    officiant = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="officiated_occasions",
        help_text="Who leads it.",
    )
    venue = models.CharField(
        max_length=200, blank=True, help_text="Leave blank for the usual place."
    )
    notes = models.TextField(blank=True)
    is_cancelled = models.BooleanField(
        "Cancelled", default=False, help_text="A cancelled occasion frees its time."
    )

    class Meta:
        ordering = ["starts_at", "pk"]
        default_permissions = ("add", "change", "view")

    def __str__(self):
        local = timezone.localtime(self.starts_at)
        return (
            f"{self.occasion_type.name} for {self.occasion_for}, "
            f"{local:%b} {local.day}, {local.year}"
        )

    @property
    def ends_at(self):
        return self.starts_at + datetime.timedelta(minutes=self.length_minutes)

    @property
    def has_started(self):
        return self.starts_at <= timezone.now()


class OccasionRequest(PublicIdModel, TimeStampedModel):
    """Someone signed in asks for an Occasion. Approving it (with
    ``occasions.approve_occasion``) creates the Occasion."""

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
    occasion_type = models.ForeignKey(
        OccasionType,
        on_delete=models.PROTECT,
        related_name="requests",
        verbose_name="Occasion",
    )
    starts_at = models.DateTimeField("Preferred date and start time")
    occasion_for = models.CharField(
        "For",
        max_length=200,
        help_text="Who it is for, such as the couple's names.",
    )
    note = models.TextField(
        blank=True,
        help_text="Anything the church should know. Only the people who "
        "approve requests see it.",
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
    # The occasion approving it created.
    occasion = models.OneToOneField(
        Occasion,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="request",
    )

    class Meta:
        ordering = ["-created_at", "-pk"]
        default_permissions = ()
        permissions = [
            ("request_occasion", "Can request an occasion"),
            ("approve_occasion", "Can approve or decline occasion requests"),
        ]

    def __str__(self):
        return f"{self.occasion_type.name} for {self.occasion_for}"

    @property
    def is_pending(self):
        return self.status == self.Status.PENDING

    @property
    def ends_at(self):
        return self.starts_at + datetime.timedelta(
            minutes=self.occasion_type.length_minutes
        )
