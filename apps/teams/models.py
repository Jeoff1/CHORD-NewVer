"""Teams: who serves at each worship service, and when people can't.

Design-Decisions, Phase 8. A Team Profile belongs to a user account, not to
a Member record (the Members module stays as built).
"""

from django.conf import settings
from django.db import models

from apps.core.models import PublicIdModel, TimeStampedModel
from apps.core.people import display_name
from apps.core.setting_lists import ChoiceItem
from apps.worship.models import WorshipService


class TeamPart(ChoiceItem):
    """A voice or instrument someone can take at a worship service."""

    class Meta(ChoiceItem.Meta):
        pass


class TeamProfile(TimeStampedModel):
    """The Team Parts a person can take. Nothing else: no vocal range."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="team_profile"
    )
    parts = models.ManyToManyField(TeamPart, blank=True, related_name="profiles")

    class Meta:
        default_permissions = ("change", "view")

    def __str__(self):
        return f"Team profile: {display_name(self.user)}"


class Assignment(PublicIdModel, TimeStampedModel):
    """One person taking one Team Part at one worship service."""

    class Reply(models.TextChoices):
        PENDING = "pending", "Pending"
        ACCEPTED = "accepted", "Accepted"
        DECLINED = "declined", "Declined"

    service = models.ForeignKey(
        WorshipService, on_delete=models.CASCADE, related_name="assignments"
    )
    part = models.ForeignKey(
        TeamPart, on_delete=models.PROTECT, related_name="assignments"
    )
    person = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="assignments"
    )
    reply = models.CharField(
        max_length=10, choices=Reply.choices, default=Reply.PENDING
    )
    replied_at = models.DateTimeField(null=True, blank=True)
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )

    class Meta:
        ordering = ["part__sort_order", "part__name", "pk"]
        # Replies need no permission: only the assigned person replies.
        default_permissions = ("add", "delete", "view")
        constraints = [
            models.UniqueConstraint(
                fields=["service", "part", "person"],
                name="one_assignment_per_person_part_service",
            )
        ]

    def __str__(self):
        return f"{display_name(self.person)}: {self.part} at {self.service}"

    @property
    def is_serving(self):
        """Pending or Accepted: the person is still on the service's team."""
        return self.reply != self.Reply.DECLINED

    @property
    def open_swap_request(self):
        """The open Swap Request for this assignment, or None. Prefetch
        ``swap_requests`` when listing many."""
        return next((swap for swap in self.swap_requests.all() if swap.is_open), None)


class BlackoutDate(TimeStampedModel):
    """Whole days, in the church's time zone, on which a person can't serve."""

    person = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="blackout_dates",
    )
    starts_on = models.DateField("From")
    ends_on = models.DateField("To", help_text="The last day you can't serve.")
    note = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ["starts_on", "ends_on", "pk"]
        # Each person manages their own; no permission is needed.
        default_permissions = ()
        constraints = [
            models.CheckConstraint(
                condition=models.Q(ends_on__gte=models.F("starts_on")),
                name="blackout_ends_on_or_after_start",
            )
        ]

    def __str__(self):
        return f"{display_name(self.person)}: {self.date_range()}"

    def date_range(self):
        start, end = self.starts_on, self.ends_on
        if start == end:
            return f"{start:%b} {start.day}, {start.year}"
        if start.year == end.year:
            return f"{start:%b} {start.day} to {end:%b} {end.day}, {end.year}"
        return f"{start:%b} {start.day}, {start.year} to {end:%b} {end.day}, {end.year}"


class SwapRequest(PublicIdModel, TimeStampedModel):
    """A person asking to be replaced in an Assignment. The first person who
    may take it gets the assignment, with no approval. It is kept after it
    closes, as the record of who handed over and who took it."""

    class Status(models.TextChoices):
        OPEN = "open", "Open"
        WITHDRAWN = "withdrawn", "Withdrawn"
        TAKEN = "taken", "Taken"

    # Cleared when the assignment ends (taken, or removed by the leader).
    assignment = models.ForeignKey(
        Assignment,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="swap_requests",
    )
    service = models.ForeignKey(
        WorshipService, on_delete=models.CASCADE, related_name="swap_requests"
    )
    part = models.ForeignKey(TeamPart, on_delete=models.PROTECT, related_name="+")
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="swap_requests"
    )
    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.OPEN
    )
    taken_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    closed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["service__starts_at", "pk"]
        default_permissions = ()
        constraints = [
            models.UniqueConstraint(
                fields=["assignment"],
                condition=models.Q(status="open"),
                name="one_open_swap_request_per_assignment",
            )
        ]

    def __str__(self):
        return (
            f"Swap request: {self.part} at {self.service}, from "
            f"{display_name(self.requested_by)}"
        )

    @property
    def is_open(self):
        return self.status == self.Status.OPEN


class Notification(TimeStampedModel):
    """A note in the app for one person. Never sent by email or SMS."""

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications"
    )
    text = models.CharField(max_length=300)
    url = models.CharField(max_length=300, blank=True)
    # A repeat with the same key replaces an unread one instead of piling up.
    key = models.CharField(max_length=100, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at", "-pk"]
        default_permissions = ()
        indexes = [models.Index(fields=["recipient", "read_at"])]

    def __str__(self):
        return self.text

    @property
    def is_read(self):
        return self.read_at is not None
