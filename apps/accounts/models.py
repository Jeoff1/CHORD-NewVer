from django.contrib.auth.models import AbstractUser, Group
from django.db import models


class User(AbstractUser):
    """Project user model; extend with CHORD-specific fields as needed.

    Users are deactivated, never deleted, so the audit trail keeps its actors.
    """

    # Set on accounts made in a batch with a Temporary Password (Phase 9A,
    # A4): until the person chooses their own password, every page sends
    # them to Change password (``middleware.PasswordChangeRequiredMiddleware``).
    must_change_password = models.BooleanField(default=False, editable=False)

    class Theme(models.TextChoices):
        DEVICE = "device", "Match my device"
        LIGHT = "light", "Light"
        DARK = "dark", "Dark"

    # The person's own choice of light or dark mode (Phase 9A, A7; the
    # Settings hub's Personal category). By default the page follows the
    # device's setting.
    theme = models.CharField(
        "Appearance", max_length=6, choices=Theme.choices, default=Theme.DEVICE
    )

    class Meta(AbstractUser.Meta):
        default_permissions = ("add", "change", "view")

    @property
    def roles(self):
        return Role.objects.filter(user=self)


class Role(Group):
    """A named set of permissions given to users; the church edits roles.

    Built on Django's Group, so Django's permission checks include it. Seeded
    default roles carry a ``key`` so later phases can grant them new
    permissions; roles the church creates have no key.
    """

    key = models.SlugField(
        max_length=50, unique=True, null=True, blank=True, editable=False
    )
    description = models.CharField(max_length=250, blank=True)
    # Default permissions already granted once (see roles.py), so a
    # permission the church removes is never granted again.
    granted_defaults = models.JSONField(default=list, blank=True, editable=False)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    @property
    def is_administrator(self):
        from .roles import ADMINISTRATOR

        return self.key == ADMINISTRATOR
