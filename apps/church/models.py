import zoneinfo

from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models

from apps.core.models import TimeStampedModel

from .labels import Labels

TIME_ZONE_CHOICES = [(tz, tz) for tz in sorted(zoneinfo.available_timezones())]
MAX_LOGO_BYTES = 2 * 1024 * 1024


def validate_logo_size(file):
    if file.size > MAX_LOGO_BYTES:
        raise ValidationError("The logo must be 2 MB or smaller.")


class ChurchProfile(TimeStampedModel):
    """The single record describing this installation's church.

    It holds the church's details, which Modules are switched off, and its
    Labels. Load it with ``ChurchProfile.load()``.
    """

    SINGLETON_PK = 1

    name = models.CharField(max_length=200, default="My Church")
    address = models.TextField(blank=True)
    phone = models.CharField(max_length=40, blank=True)
    email = models.EmailField(blank=True)
    website = models.URLField(blank=True)
    logo = models.ImageField(
        upload_to="church/", blank=True, validators=[validate_logo_size]
    )
    currency = models.CharField(
        max_length=3,
        default="PHP",
        validators=[
            RegexValidator(r"^[A-Z]{3}$", "Use a three-letter code such as PHP.")
        ],
        help_text="Three-letter currency code, such as PHP or USD.",
    )
    time_zone = models.CharField(
        max_length=64, choices=TIME_ZONE_CHOICES, default="Asia/Manila"
    )
    disabled_modules = models.JSONField(default=list, blank=True)
    labels = models.JSONField(default=dict, blank=True)
    setup_completed = models.BooleanField(default=False)

    class Meta:
        default_permissions = ("change",)
        constraints = [
            models.CheckConstraint(
                condition=models.Q(pk=1), name="church_profile_single_row"
            )
        ]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        self.pk = self.SINGLETON_PK
        if self.created_at is None:
            # A new instance replaces the existing row; keep its creation time.
            self.created_at = (
                type(self)
                .objects.filter(pk=self.pk)
                .values_list("created_at", flat=True)
                .first()
            )
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        profile, _ = cls.objects.get_or_create(pk=cls.SINGLETON_PK)
        return profile

    @property
    def label_set(self):
        return Labels(self.labels)
