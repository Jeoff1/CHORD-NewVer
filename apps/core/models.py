"""Abstract base models shared by every CHORD module."""

import uuid

from django.db import models


class TimeStampedModel(models.Model):
    """Records when a row was created and last changed."""

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class PublicIdModel(models.Model):
    """Adds a random UUID for use in URLs, so row IDs can't be guessed or counted."""

    public_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)

    class Meta:
        abstract = True
