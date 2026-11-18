"""Music vocabulary shared by the worship, songs and teams apps."""

from django.db import models


class Feel(models.TextChoices):
    """How a song moves. Spotify no longer gives tempo, so the system
    guesses a song's feel from its lyrics and a person corrects it."""

    UPBEAT = "upbeat", "Upbeat"
    MID = "mid", "Mid-tempo"
    SLOW = "slow", "Slow"
