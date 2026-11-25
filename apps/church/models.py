import zoneinfo

from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models
from django.utils.text import slugify

from apps.core.models import TimeStampedModel

from .labels import Labels

TIME_ZONE_CHOICES = [(tz, tz) for tz in sorted(zoneinfo.available_timezones())]
MAX_LOGO_BYTES = 2 * 1024 * 1024


def validate_logo_size(file):
    if file.size > MAX_LOGO_BYTES:
        raise ValidationError("The logo must be 2 MB or smaller.")


def unique_slug(name, *, exclude_pk=None):
    """A slug made from ``name`` that no other church uses: "grace-chapel",
    then "grace-chapel-2" and so on."""
    base = slugify(name)[:70] or "church"
    taken = set(
        ChurchProfile.objects.exclude(pk=exclude_pk)
        .filter(slug__startswith=base)
        .values_list("slug", flat=True)
    )
    slug, n = base, 1
    while slug in taken:
        n += 1
        slug = f"{base}-{n}"
    return slug


def first_church_id():
    """The pk of the first church, created if there is none.

    Phase 9B, slice a only: the default of every new ``church`` foreign key,
    so code not yet scoped keeps working. Slice b removes these defaults and
    sets the church explicitly everywhere.
    """
    pk = ChurchProfile.objects.order_by("pk").values_list("pk", flat=True).first()
    return pk if pk is not None else ChurchProfile.objects.create().pk


class ChurchProfile(TimeStampedModel):
    """One church on the platform (decision 0014).

    It holds the church's details, which Modules are switched off, and its
    Labels. A request's church is ``request.church`` (the Current Church).
    """

    name = models.CharField(max_length=200, default="My Church")
    slug = models.SlugField(
        max_length=80,
        unique=True,
        editable=False,
        help_text="The church's address on the platform: /churches/<slug>/.",
    )
    about = models.TextField(blank=True, help_text="Shown on the church's homepage.")
    show_in_directory = models.BooleanField(
        "Show in the directory",
        default=True,
        help_text="List the church on the platform's public list of churches.",
    )
    show_upcoming_services = models.BooleanField(
        "Show upcoming services",
        default=False,
        help_text="Show the next worship services on the homepage: date, time "
        "and kind only.",
    )
    # The Members and Teams Modules aren't separated per church yet, so only
    # the first church, migrated from before Phase 9B, may use them.
    members_teams_unlocked = models.BooleanField(default=False, editable=False)
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
        ordering = ["pk"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slug(self.name, exclude_pk=self.pk)
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        """The first church. Phase 9B, slice a only: code not yet scoped
        still calls this; slice b replaces every call with the request's or
        the record's church and removes it."""
        return cls.objects.get(pk=first_church_id())

    @property
    def label_set(self):
        return Labels(self.labels)


def church_foreign_key(**kwargs):
    """The ``church`` field of a record that belongs to one church
    (decision 0014). Phase 9B, slice a: it defaults to the first church so
    code not yet scoped keeps working; slice b removes the default."""
    kwargs.setdefault("related_name", "+")
    kwargs.setdefault("default", first_church_id)
    return models.ForeignKey("church.ChurchProfile", on_delete=models.CASCADE, **kwargs)


def church_settings_field():
    """The ``church`` of a settings row, one per church (decision 0014).
    Phase 9B, slice a: defaults to the first church, like
    ``church_foreign_key``."""
    return models.OneToOneField(
        "church.ChurchProfile",
        on_delete=models.CASCADE,
        related_name="+",
        default=first_church_id,
    )
