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
