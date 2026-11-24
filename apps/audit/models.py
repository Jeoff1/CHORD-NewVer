from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.db import models


class AuditEvent(models.Model):
    """One change to one object, written by ``apps.audit.services``.

    Every module records its changes here instead of keeping its own audit
    table.
    """

    class Action(models.TextChoices):
        CREATED = "created", "Created"
        CHANGED = "changed", "Changed"
        DELETED = "deleted", "Deleted"

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    action = models.CharField(max_length=16, choices=Action.choices)
    content_type = models.ForeignKey(ContentType, on_delete=models.PROTECT)
    object_id = models.CharField(max_length=64)
    object_repr = models.CharField(max_length=200)
    # {"field label": [old value, new value]}, values as display strings.
    changes = models.JSONField(default=dict, blank=True)
    occurred_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-occurred_at", "-pk"]
        default_permissions = ("view",)
        indexes = [models.Index(fields=["content_type", "object_id"])]

    def __str__(self):
        return f"{self.get_action_display()} {self.object_repr}"


class SignInEvent(models.Model):
    """One sign-in, sign-out or failed sign-in (Phase 9A, A3).

    Part of the Audit Trail, kept apart from ``AuditEvent`` (which records
    changes to data) so that signing in never mixes with what people
    changed. Never edited or removed. Never holds a password: a failed
    sign-in keeps only the username that was tried.
    """

    class Kind(models.TextChoices):
        SIGNED_IN = "signed_in", "Signed in"
        SIGNED_OUT = "signed_out", "Signed out"
        FAILED = "failed", "Failed sign-in"

    kind = models.CharField(max_length=16, choices=Kind.choices)
    # The account, when the username matched one (a failed sign-in with an
    # unknown username has none).
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    username = models.CharField(max_length=150, blank=True)
    occurred_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-occurred_at", "-pk"]
        # Seen with audit.view_auditevent, like the rest of the Audit Trail.
        default_permissions = ()
        indexes = [models.Index(fields=["user", "-occurred_at"])]

    def __str__(self):
        return f"{self.get_kind_display()}: {self.username}"
