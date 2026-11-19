"""Music vocabulary shared by the worship, songs and teams apps."""

from django.db import models


class Feel(models.TextChoices):
    """How a song moves. Spotify no longer gives tempo, so the system
    guesses a song's feel from its lyrics and a person corrects it."""

    UPBEAT = "upbeat", "Upbeat"
    MID = "mid", "Mid-tempo"
    SLOW = "slow", "Slow"


# The keys a song can be sung in, spelled the way chord charts usually spell
# them. Chord sheets (Phase 7) transpose from a song's original key to these.
MAJOR_KEYS = ("C", "Db", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B")
MINOR_KEYS = (
    "Cm",
    "C#m",
    "Dm",
    "Ebm",
    "Em",
    "Fm",
    "F#m",
    "Gm",
    "G#m",
    "Am",
    "Bbm",
    "Bm",
)
KEY_CHOICES = [
    ("Major", [(key, key) for key in MAJOR_KEYS]),
    ("Minor", [(key, key) for key in MINOR_KEYS]),
]
