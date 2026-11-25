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

    def roles_in(self, church):
        """The roles this user holds in ``church`` (none without an active
        Membership there)."""
        return Role.objects.filter(
            memberships__user=self,
            memberships__church=church,
            memberships__is_active=True,
        )

    @property
    def roles(self):
        """The roles held in the Current Church (the first church when there
        is none, outside a request; Phase 9B, slice a only)."""
        from apps.church.models import ChurchProfile

        church = getattr(self, "current_church", None) or ChurchProfile.load()
        return self.roles_in(church)


class Role(Group):
    """A named set of permissions given to users in one church; each church
    edits its own roles (decisions 0003 and 0014).

    Built on Django's Group, whose ``name`` must be unique across the whole
    installation, so the name people see is ``title`` (unique per church)
    and ``name`` holds a hidden internal name. Permissions come through a
    ``Membership``, never through ``user.groups`` (see ``backends.py``).
    Seeded default roles carry a ``key`` so later phases can grant them new
    permissions; roles the church creates have no key.
    """

    church = models.ForeignKey(
        "church.ChurchProfile", on_delete=models.CASCADE, related_name="roles"
    )
    title = models.CharField("Name", max_length=150)
    key = models.SlugField(max_length=50, null=True, blank=True, editable=False)
    description = models.CharField(max_length=250, blank=True)
    # Default permissions already granted once (see roles.py), so a
    # permission the church removes is never granted again.
    granted_defaults = models.JSONField(default=list, blank=True, editable=False)

    class Meta:
        ordering = ["title"]
        constraints = [
            models.UniqueConstraint(
                fields=["church", "title"],
                name="role_title_unique_per_church",
                violation_error_message="This church already has a role with "
                "that name.",
            ),
            models.UniqueConstraint(
                fields=["church", "key"], name="role_key_unique_per_church"
            ),
        ]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        self.name = f"{self.church_id}:{self.title}"
        super().save(*args, **kwargs)

    @property
    def is_administrator(self):
        from .roles import ADMINISTRATOR

        return self.key == ADMINISTRATOR


class Membership(models.Model):
    """A user's place in one church: their roles there, and whether it is
    active (decision 0014). A user has at most one per church, and may
    belong to several churches or none."""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="memberships")
    church = models.ForeignKey(
        "church.ChurchProfile", on_delete=models.CASCADE, related_name="memberships"
    )
    roles = models.ManyToManyField(Role, blank=True, related_name="memberships")
    is_active = models.BooleanField("Active", default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "pk"]
        default_permissions = ()
        constraints = [
            models.UniqueConstraint(
                fields=["user", "church"], name="one_membership_per_church"
            )
        ]

    def __str__(self):
        return f"{self.user} in {self.church}"
