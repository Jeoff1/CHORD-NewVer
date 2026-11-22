"""Lineups: the songs chosen for a worship service, reviewed and confirmed.

A Lineup is its own stored copy, made from a Search Run's suggestions:
later corrections to the run (a song's feel, "Not a worship song", a new
Worship Check) never rearrange it or remove its songs (workflow review F4).

The rules for changing, confirming, reopening and sending back a lineup are
in ``apps/worship/lineups.py`` (Design-Decisions, Phase 6).
"""

from django.conf import settings
from django.db import models

from apps.core.models import TimeStampedModel
from apps.core.music import KEY_CHOICES
from apps.core.people import display_name

from .schedule import TemplateSlot, WorshipService
from .suggestions import SearchRun


class Lineup(TimeStampedModel):
    """The songs for one worship service: a draft, or confirmed.

    The final say is the permission ``finalize_lineup`` (decision 0008),
    never a role name. Its holders' confirmation, or their edit to a
    confirmed lineup, puts on the **pastor's lock**: the worship leader
    can't change the lineup until a holder reopens it.
    """

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        CONFIRMED = "confirmed", "Confirmed"

    service = models.OneToOneField(
        WorshipService, on_delete=models.CASCADE, related_name="lineup"
    )
    run = models.ForeignKey(
        SearchRun,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        help_text="The Search Run whose suggestions the lineup came from.",
    )
    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.DRAFT
    )
    # The latest confirmation. Kept when the lineup is reopened, so a draft
    # that was once confirmed is known to be "being revised".
    confirmed_at = models.DateTimeField(null=True, blank=True)
    confirmed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    pastor_locked = models.BooleanField(
        "Pastor's lock",
        default=False,
        help_text="Only people with the final say may change the lineup.",
    )
    # The mark: the latest edit to the lineup while it was confirmed. Only
    # the latest shows: "Edited by <pastor Label> (<name>)" when the editor
    # had the final say, otherwise "Changed by <name>".
    edited_at = models.DateTimeField(null=True, blank=True)
    edited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    edited_with_final_say = models.BooleanField(default=False)
    # Sending back returns the lineup to draft with a note for the leader.
    sent_back_note = models.TextField(blank=True)
    sent_back_at = models.DateTimeField(null=True, blank=True)
    sent_back_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )

    # What became of each suggestion placed in the lineup during review:
    # {suggestion pk: "kept" | "swapped" | "removed"}. Confirming turns it
    # into Suggestion Feedback (``apps/worship/feedback.py``).
    suggestion_outcomes = models.JSONField(default=dict, blank=True)

    # The Spotify playlist the lineup was saved as (Design-Decisions, Phase
    # 7): on the account of the person who saved it, holding the track IDs
    # as they were then. Saving again updates the same playlist when the
    # same person saves it.
    spotify_playlist_id = models.CharField(max_length=64, blank=True)
    spotify_playlist_owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    spotify_playlist_tracks = models.JSONField(default=list, blank=True)
    spotify_playlist_saved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        default_permissions = ("add", "change", "view")
        permissions = [
            ("finalize_lineup", "Can have the final say on lineups"),
            ("view_song_usage", "Can see the song usage report"),
        ]

    def __str__(self):
        return f"Lineup for {self.service}"

    @property
    def is_confirmed(self):
        return self.status == self.Status.CONFIRMED

    @property
    def is_being_revised(self):
        """A draft that was confirmed before: the team sees a note instead."""
        return not self.is_confirmed and self.confirmed_at is not None

    @property
    def edited_by_name(self):
        return display_name(self.edited_by)

    @property
    def confirmed_by_name(self):
        return display_name(self.confirmed_by)

    @property
    def sent_back_by_name(self):
        return display_name(self.sent_back_by)

    @property
    def spotify_playlist_owner_name(self):
        return display_name(self.spotify_playlist_owner)

    @property
    def spotify_playlist_url(self):
        if self.spotify_playlist_id:
            return f"https://open.spotify.com/playlist/{self.spotify_playlist_id}"
        return ""


class LineupItem(models.Model):
    """One song in a lineup, in order, with its slot and service key."""

    lineup = models.ForeignKey(Lineup, on_delete=models.CASCADE, related_name="items")
    song = models.ForeignKey(
        "songs.Song", on_delete=models.PROTECT, related_name="lineup_items"
    )
    slot = models.ForeignKey(
        TemplateSlot,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    position = models.PositiveSmallIntegerField(default=0)
    key = models.CharField(
        "Service key",
        max_length=4,
        choices=KEY_CHOICES,
        blank=True,
        help_text="The key the song is sung in at this service.",
    )
    notes = models.TextField(blank=True)
    reasons = models.JSONField(
        default=list,
        blank=True,
        help_text="Why the song was suggested for the theme, copied when it "
        "joined the lineup. The feel reason depends on the slot, so it is "
        "worked out when shown (slot_reason).",
    )
    locked = models.BooleanField(
        default=False,
        help_text="Kept in place: it isn't swapped, moved, removed or "
        "regenerated until it is unlocked.",
    )

    class Meta:
        ordering = ["position", "pk"]
        default_permissions = ()
        constraints = [
            models.UniqueConstraint(
                fields=["lineup", "song"], name="one_item_per_song_per_lineup"
            )
        ]

    def __str__(self):
        return f"{self.position + 1}. {self.song}"

    @property
    def slot_reason(self):
        """The feel reason for the slot the song is in now. Not stored:
        ``reasons`` keeps only the theme reasons, which don't depend on the
        slot, so a moved song never shows another slot's reason."""
        from ..sequencing import slot_reason

        return slot_reason(self.song, self.slot)


class SuggestionFeedback(models.Model):
    """What a person did with one suggestion in a confirmed lineup: kept,
    swapped in, swapped or removed. Training data for learning to rank (Phase 9).

    The features are only lyrics-based scores and the church's own data
    (Design-Decisions, Phase 9). Never stored here: Spotify fields (title,
    artist, album, track ID, length), the Trusted Artist bonus or any score
    that includes it (``Song.worship_score``), which version of a song was
    kept, or the genre-filter record of a Search Run. ``song`` and ``run``
    identify the row; they are never features.
    """

    class Label(models.TextChoices):
        KEPT = "kept", "Kept"
        # An alternative the leader chose in a swap: a positive, like kept,
        # but told apart from a top pick that stayed (decided 2026-11-19).
        SWAPPED_IN = "swapped_in", "Swapped in"
        SWAPPED = "swapped", "Swapped"
        REMOVED = "removed", "Removed"

    # The only columns training may use as features.
    FEATURES = (
        "relevance",
        "match",
        "familiarity",
        "season",
        "recency",
        "worship_model_score",
        "team_knows",
        "slot_feel",
    )

    lineup = models.ForeignKey(
        Lineup, on_delete=models.CASCADE, related_name="feedback"
    )
    run = models.ForeignKey(SearchRun, on_delete=models.CASCADE, related_name="+")
    song = models.ForeignKey("songs.Song", on_delete=models.CASCADE, related_name="+")
    label = models.CharField(max_length=10, choices=Label.choices)
    recorded_at = models.DateTimeField()
    rank = models.PositiveSmallIntegerField(help_text="Its rank in the run.")

    # Features: lyrics-based scores (from the suggestion) ...
    relevance = models.FloatField()
    match = models.FloatField(null=True, blank=True)
    worship_model_score = models.FloatField(
        null=True, blank=True, help_text="The model's score, from the lyrics alone."
    )
    # ... and the church's own data.
    familiarity = models.FloatField()
    season = models.FloatField()
    recency = models.FloatField()
    team_knows = models.BooleanField()
    slot_feel = models.CharField(
        max_length=10, blank=True, help_text="The feel of the slot it was placed in."
    )

    class Meta:
        ordering = ["lineup", "rank"]
        default_permissions = ()
        constraints = [
            models.UniqueConstraint(
                fields=["lineup", "song"], name="one_feedback_per_song_per_lineup"
            )
        ]

    def __str__(self):
        return (
            f"{self.get_label_display()}: suggestion {self.rank} of run {self.run_id}"
        )
