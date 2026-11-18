from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from apps.core.custom_fields import CustomFieldDefinition
from apps.core.models import PublicIdModel, TimeStampedModel
from apps.core.setting_lists import ChoiceItem
from apps.core.storage import get_private_storage, random_upload_name

MAX_PHOTO_BYTES = 5 * 1024 * 1024


class MembershipStatus(ChoiceItem):
    """A church-edited membership status, such as Member or Visitor."""

    counts_as_active = models.BooleanField(
        "Counts as active",
        default=True,
        help_text="People with this status are counted as active members.",
    )

    class Meta(ChoiceItem.Meta):
        verbose_name_plural = "membership statuses"

    @classmethod
    def default(cls):
        """The status new members get unless another is chosen."""
        return cls.objects.active().first()


class RelationshipType(ChoiceItem):
    """A church-edited role within a household, such as Head or Child."""


class MemberField(CustomFieldDefinition):
    """A Custom Field the church adds to every member record."""

    class Meta(CustomFieldDefinition.Meta):
        verbose_name = "member field"
        constraints = [
            models.UniqueConstraint(fields=["key"], name="unique_member_field_key")
        ]


class Household(PublicIdModel, TimeStampedModel):
    """People who live together, such as a family."""

    name = models.CharField(max_length=150, help_text="For example, “Santos Family”.")
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["name"]
        default_permissions = ("add", "change", "view")

    def __str__(self):
        return self.name


def member_photo_path(instance, filename):
    return random_upload_name("members/photos", filename)


def validate_photo_size(file):
    if file.size > MAX_PHOTO_BYTES:
        raise ValidationError("The photo must be 5 MB or smaller.")


class MemberQuerySet(models.QuerySet):
    def current(self):
        return self.filter(archived_at__isnull=True)

    def archived(self):
        return self.filter(archived_at__isnull=False)


class Member(PublicIdModel, TimeStampedModel):
    """A person in the church's directory, member or not.

    Birth date and contact details are private: only users with
    ``members.view_private_details`` see them. Members are archived, never
    deleted.
    """

    PRIVATE_FIELDS = ("birth_date", "email", "phone", "address")

    class Sex(models.TextChoices):
        FEMALE = "female", "Female"
        MALE = "male", "Male"

    first_name = models.CharField(max_length=100)
    middle_name = models.CharField(max_length=100, blank=True)
    last_name = models.CharField(max_length=100)
    suffix = models.CharField(max_length=20, blank=True, help_text="Jr., Sr., III")
    sex = models.CharField(max_length=10, choices=Sex.choices, blank=True)
    birth_date = models.DateField(null=True, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=40, blank=True)
    address = models.TextField(blank=True)
    photo = models.ImageField(
        storage=get_private_storage,
        upload_to=member_photo_path,
        blank=True,
        validators=[validate_photo_size],
    )
    status = models.ForeignKey(
        MembershipStatus, on_delete=models.PROTECT, related_name="members"
    )
    joined_on = models.DateField("Date joined", null=True, blank=True)
    household = models.ForeignKey(
        Household,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="members",
    )
    relationship = models.ForeignKey(
        RelationshipType,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        verbose_name="role in household",
    )
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="member",
        verbose_name="linked account",
        help_text="Lets this person sign in and see their own record.",
    )
    notes = models.TextField(blank=True)
    custom_data = models.JSONField(default=dict, blank=True, editable=False)
    archived_at = models.DateTimeField(null=True, blank=True, editable=False)

    objects = MemberQuerySet.as_manager()

    class Meta:
        ordering = ["last_name", "first_name", "middle_name"]
        default_permissions = ("add", "change", "view")
        permissions = [
            ("view_private_details", "Can view members' birth dates and contacts"),
            ("import_member", "Can import members from a CSV file"),
            ("export_member", "Can export members to a CSV file"),
        ]
        indexes = [models.Index(fields=["last_name", "first_name"])]

    def __str__(self):
        return self.full_name

    @property
    def full_name(self):
        parts = [self.first_name, self.middle_name, self.last_name, self.suffix]
        return " ".join(part for part in parts if part)

    @property
    def is_archived(self):
        return self.archived_at is not None
