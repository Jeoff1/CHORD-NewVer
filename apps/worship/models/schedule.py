"""The worship schedule: service templates, services and their themes."""

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.core.models import PublicIdModel, TimeStampedModel
from apps.core.music import Feel
from apps.core.setting_lists import ChoiceItem


class ServiceTemplate(ChoiceItem):
    """A kind of worship service the church holds, such as its main weekly
    service or a youth night, with the places in it where songs are sung.

    A template with a usual day and time can be scheduled weeks ahead.
    """

    class Weekday(models.IntegerChoices):
        MONDAY = 0, "Monday"
        TUESDAY = 1, "Tuesday"
        WEDNESDAY = 2, "Wednesday"
        THURSDAY = 3, "Thursday"
        FRIDAY = 4, "Friday"
        SATURDAY = 5, "Saturday"
        SUNDAY = 6, "Sunday"

    weekday = models.PositiveSmallIntegerField(
        "Usual day",
        choices=Weekday.choices,
        null=True,
        blank=True,
        help_text="Give the usual day and time to schedule this service weeks ahead.",
    )
    start_time = models.TimeField("Usual start time", null=True, blank=True)

    class Meta(ChoiceItem.Meta):
        pass

    @property
    def repeats_weekly(self):
        return self.weekday is not None and self.start_time is not None

    def slot_summary(self):
        return ", ".join(str(slot) for slot in self.slots.all())


class TemplateSlot(models.Model):
    """A place in a service where a song is sung, in order."""

    template = models.ForeignKey(
        ServiceTemplate, on_delete=models.CASCADE, related_name="slots"
    )
    name = models.CharField(max_length=60)
    feel = models.CharField(
        max_length=10,
        choices=Feel.choices,
        blank=True,
        help_text="The feel of song that suits this slot. Blank means any.",
    )
    position = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["position", "pk"]
        default_permissions = ()

    def __str__(self):
        return f"{self.name} ({self.get_feel_display()})" if self.feel else self.name


class SermonSeries(ChoiceItem):
    """A run of services whose themes belong together."""

    class Meta(ChoiceItem.Meta):
        verbose_name_plural = "sermon series"


class WorshipServiceQuerySet(models.QuerySet):
    def upcoming(self, now=None):
        return self.filter(starts_at__gte=start_of_today(now))

    def past(self, now=None):
        return self.filter(starts_at__lt=start_of_today(now))

    def held(self):
        """Services that took place: not cancelled, and already started."""
        return self.filter(is_cancelled=False, starts_at__lte=timezone.now())


def start_of_today(now=None):
    now = timezone.localtime(now or timezone.now())
    return now.replace(hour=0, minute=0, second=0, microsecond=0)


class WorshipService(PublicIdModel, TimeStampedModel):
    """One gathering for worship, on one date."""

    name = models.CharField(max_length=120)
    template = models.ForeignKey(
        ServiceTemplate, on_delete=models.PROTECT, related_name="services"
    )
    starts_at = models.DateTimeField("Date and time")
    rehearsal_at = models.DateTimeField("Rehearsal", null=True, blank=True)
    notes = models.TextField(
        blank=True, help_text="Shown to everyone who can see this service."
    )
    attendance = models.PositiveIntegerField(
        "Headcount", null=True, blank=True, help_text="How many people attended."
    )
    is_cancelled = models.BooleanField("Cancelled", default=False)

    objects = WorshipServiceQuerySet.as_manager()

    class Meta:
        ordering = ["starts_at", "pk"]
        default_permissions = ("add", "change", "view")
        permissions = [
            ("record_attendance", "Can record the headcount of a worship service"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["template", "starts_at"],
                name="one_service_per_template_time",
                violation_error_message="This service is already scheduled at "
                "that date and time.",
            )
        ]

    def __str__(self):
        local = timezone.localtime(self.starts_at)
        return f"{self.name}, {local:%b} {local.day}, {local.year}"

    @property
    def local_date(self):
        return timezone.localtime(self.starts_at).date()

    @property
    def has_started(self):
        return self.starts_at <= timezone.now()

    @property
    def posted_theme(self):
        """The service's theme, or None when it hasn't been posted."""
        return getattr(self, "theme", None)


class Theme(TimeStampedModel):
    """What a service's message is about; the starting point for its songs."""

    service = models.OneToOneField(
        WorshipService, on_delete=models.CASCADE, related_name="theme"
    )
    title = models.CharField(max_length=200)
    scripture = models.CharField(
        "Main scripture", max_length=200, blank=True, help_text="For example, John 3:16"
    )
    notes = models.TextField(
        blank=True,
        help_text="Notes or an outline. The more it says, the better the song "
        "suggestions fit.",
    )
    series = models.ForeignKey(
        SermonSeries,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="themes",
    )
    posted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        editable=False,
        related_name="+",
    )

    class Meta:
        default_permissions = ("change",)

    def __str__(self):
        return self.title

    def text(self):
        """Everything the theme says, as one text for matching songs."""
        return "\n".join(
            part for part in (self.title, self.scripture, self.notes) if part
        )
