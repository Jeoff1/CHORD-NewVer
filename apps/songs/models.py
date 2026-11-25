"""The song pool: every song the system has checked, with its lyrics,
analysis and the church's corrections."""

import re

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q

from apps.church.models import (
    church_foreign_key,
    church_settings_field,
    first_church_id,
)
from apps.core.models import PublicIdModel, TimeStampedModel
from apps.core.music import KEY_CHOICES, Feel
from apps.core.setting_lists import ChurchChoiceItem


def word_set(text):
    """Lower-case words of a comma- or space-separated text."""
    return {word for word in re.split(r"[^\w']+", text.lower()) if word}


class ThemeTag(ChurchChoiceItem):
    """A worship theme a song can be about, such as Grace or Hope. The
    analysis suggests tags from a song's lyrics; people correct them."""

    keywords = models.CharField(
        max_length=300,
        blank=True,
        help_text="Words in lyrics that point to this theme, separated by "
        "commas. Used when the full song models aren't installed.",
    )

    class Meta(ChurchChoiceItem.Meta):
        pass

    def keyword_set(self):
        """The keywords, or the tag's own name when it has none."""
        return word_set(self.keywords) or word_set(self.name)


class TrustedArtist(ChurchChoiceItem):
    """An artist whose songs the church trusts as worship songs. A song by
    a trusted artist passes the worship check more easily."""

    class Meta(ChurchChoiceItem.Meta):
        pass


class SongQuerySet(models.QuerySet):
    def accepted(self):
        return self.filter(worship_check=Song.WorshipCheck.ACCEPTED)

    def needs_lyrics(self):
        return self.filter(lyrics_status=Song.LyricsStatus.PENDING)

    def needs_analysis(self):
        return self.filter(lyrics_status=Song.LyricsStatus.FOUND, analysed_at=None)


class Song(PublicIdModel, TimeStampedModel):
    """A song in the pool. Spotify supplies what it is and how to play it;
    the lyrics come from LRCLIB, and only the lyrics are analysed."""

    class LyricsStatus(models.TextChoices):
        PENDING = "pending", "Not looked up yet"
        FOUND = "found", "Found"
        MISSING = "missing", "Not found"
        INSTRUMENTAL = "instrumental", "Instrumental"
        FAILED = "failed", "Lookup failed"

    class WorshipCheck(models.TextChoices):
        UNCHECKED = "unchecked", "Not checked"
        ACCEPTED = "accepted", "Worship song"
        REJECTED = "rejected", "Not a worship song"

    # What the song is (from Spotify; never model input).
    church = church_foreign_key()
    spotify_id = models.CharField("Spotify track ID", max_length=64, blank=True)
    title = models.CharField(max_length=300)
    artist = models.CharField(max_length=300)
    album = models.CharField(max_length=300, blank=True)
    length_seconds = models.PositiveIntegerField("Length", null=True, blank=True)

    # Lyrics (from LRCLIB; private to this installation).
    lyrics = models.TextField(blank=True)
    lyrics_status = models.CharField(
        max_length=12, choices=LyricsStatus.choices, default=LyricsStatus.PENDING
    )
    lyrics_checked_at = models.DateTimeField(null=True, blank=True)

    # Analysis of the lyrics, which people can correct.
    worship_check = models.CharField(
        max_length=10, choices=WorshipCheck.choices, default=WorshipCheck.UNCHECKED
    )
    # The model's score reads the lyrics alone. The Trusted Artist bonus is a
    # church rule added afterwards, so it lives only in ``worship_score``;
    # training and anything else model-related uses ``worship_model_score``.
    worship_model_score = models.FloatField(
        "Model's worship score",
        null=True,
        blank=True,
        help_text="From the lyrics alone.",
    )
    worship_score = models.FloatField(
        null=True,
        blank=True,
        help_text="The model's score plus the Trusted Artist bonus, if any; "
        "the Worship Check uses it.",
    )
    feel = models.CharField(
        max_length=10,
        choices=Feel.choices,
        blank=True,
        help_text="Blank when the analysis wasn't sure; a person sets it.",
    )
    feel_reviewed = models.BooleanField(
        "Feel set by a person",
        default=False,
        help_text="Analysing the song again keeps its feel.",
    )
    tags = models.ManyToManyField(
        ThemeTag, blank=True, related_name="songs", verbose_name="theme tags"
    )
    tag_scores = models.JSONField(
        default=dict, blank=True, help_text="How strongly each tag fits, by tag ID."
    )
    embedding = models.JSONField(default=list, blank=True)
    analysed_with = models.CharField(max_length=60, blank=True)
    analysed_at = models.DateTimeField(null=True, blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )

    team_knows = models.BooleanField("The team knows it", default=False)
    # Entered by a person: Spotify gives no key (Audio Features is never
    # called). The practise-along view shows the chords in it.
    recording_key = models.CharField(
        "Recording's key",
        max_length=4,
        choices=KEY_CHOICES,
        blank=True,
        help_text="The key the Spotify recording is in, so musicians can play "
        "along with it. Leave blank when you don't know it.",
    )

    objects = SongQuerySet.as_manager()

    class Meta:
        ordering = ["title", "artist", "pk"]
        default_permissions = ("add", "change", "view")
        permissions = [("view_lyrics", "Can see a song's full lyrics")]
        constraints = [
            models.UniqueConstraint(
                fields=["church", "spotify_id"],
                condition=~Q(spotify_id=""),
                name="one_song_per_spotify_track",
            )
        ]

    def __str__(self):
        return f"{self.title} ({self.artist})"

    @property
    def spotify_url(self):
        if self.spotify_id:
            return f"https://open.spotify.com/track/{self.spotify_id}"
        return ""

    @property
    def length_display(self):
        if self.length_seconds is None:
            return ""
        minutes, seconds = divmod(self.length_seconds, 60)
        return f"{minutes}:{seconds:02d}"

    @property
    def is_reviewed(self):
        return self.reviewed_at is not None

    def ranked_tags(self):
        """The song's tags, best-fitting first, each with its score (or None
        when a person added it)."""
        scores = self.tag_scores or {}
        tagged = [(tag, scores.get(str(tag.pk))) for tag in self.tags.all()]
        return sorted(tagged, key=lambda pair: (-(pair[1] or 0), pair[0].name))


class WorshipCheckSettings(models.Model):
    """How the church decides the Worship Check from the model's score. One
    row. These are church rules applied after the model: the artist name is
    compared with the Trusted Artist list here, never given to a model, and
    never a training feature (Design-Decisions, Phase 5 follow-up). One row
    per church."""

    church = church_settings_field()

    class UnlistedRule(models.TextChoices):
        OFF = "off", "Treat every artist the same"
        STRICTER = "stricter", "Artists not on the list need the stricter mark"
        REVIEW = "review", "Songs by artists not on the list wait for a person"

    pass_mark = models.FloatField(
        "Pass mark",
        default=0.5,
        validators=[MinValueValidator(0.05), MaxValueValidator(0.95)],
        help_text="A song passes the Worship Check when its worship score "
        "reaches this (0 to 1).",
    )
    unlisted_rule = models.CharField(
        "Artists not on the Trusted Artists list",
        max_length=10,
        choices=UnlistedRule.choices,
        default=UnlistedRule.OFF,
        help_text="With a rule on, add your trusted worship artists first: "
        "an empty list holds back every song.",
    )
    unlisted_pass_mark = models.FloatField(
        "Stricter pass mark",
        default=0.9,
        validators=[MinValueValidator(0.05), MaxValueValidator(0.99)],
        help_text="Used for artists not on the list when the stricter rule is on.",
    )

    class Meta:
        verbose_name = "worship check settings"
        verbose_name_plural = "worship check settings"
        default_permissions = ("change", "view")

    def __str__(self):
        return "Worship check settings"

    @classmethod
    def load(cls, church=None):
        """The church's row, created with the defaults if missing. Without
        ``church``, the first church's (Phase 9B, slice a only)."""
        church_id = church.pk if church is not None else first_church_id()
        settings_row, _ = cls.objects.get_or_create(church_id=church_id)
        return settings_row


class SpotifyLimit(models.Model):
    """A 429 from Spotify, and until when CHORD leaves Spotify alone.

    Every row is kept as a record of Spotify's limits. The row whose
    ``blocked_until`` is still ahead is the block that every process (the
    search worker and web requests) checks before calling Spotify.
    """

    class Reason(models.TextChoices):
        RATE_LIMIT = "rate_limit", "Rate limit"
        LONG_WAIT = "long_wait", "Long wait (treated as a quota lockout)"
        QUOTA = "quota", "Quota exceeded"

    occurred_at = models.DateTimeField()
    reason = models.CharField(max_length=12, choices=Reason.choices)
    retry_after = models.PositiveIntegerField(
        null=True, blank=True, help_text="Seconds Spotify asked CHORD to wait."
    )
    blocked_until = models.DateTimeField()

    class Meta:
        ordering = ["-occurred_at", "-pk"]
        default_permissions = ()

    def __str__(self):
        return f"{self.get_reason_display()} at {self.occurred_at:%Y-%m-%d %H:%M}"

    @property
    def is_pause(self):
        """A quota lockout or a wait so long it is treated like one: Spotify
        is paused and suggestions rank the pool instead."""
        return self.reason != self.Reason.RATE_LIMIT


class ChordSheetQuerySet(models.QuerySet):
    def approved(self):
        return self.filter(status=ChordSheet.Status.APPROVED)

    def pending(self):
        return self.filter(status=ChordSheet.Status.PENDING)


class ChordSheet(TimeStampedModel):
    """A song's chords and words in ChordPro, in the song's original key.

    Only the ChordPro text and its key are stored; every other key, a capo
    and Nashville numbers are worked out when the sheet is shown
    (``chords.py``, decision 0009). A song has at most one approved sheet.
    A sheet from someone without ``approve_chordsheet`` waits as pending
    until someone with it approves it (``sheets.py``). Chord sheets are
    copyrighted: they stay in this installation and are never logged.
    """

    class Status(models.TextChoices):
        PENDING = "pending", "Waiting for approval"
        APPROVED = "approved", "Approved"

    song = models.ForeignKey(
        Song, on_delete=models.CASCADE, related_name="chord_sheets"
    )
    chordpro = models.TextField("ChordPro")
    key = models.CharField(
        "Original key",
        max_length=4,
        choices=KEY_CHOICES,
        help_text="The key the sheet is written in.",
    )
    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.PENDING
    )
    added_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    approved_at = models.DateTimeField(null=True, blank=True)

    objects = ChordSheetQuerySet.as_manager()

    class Meta:
        ordering = ["song", "-status", "-updated_at"]
        default_permissions = ("add", "view")
        permissions = [
            (
                "approve_chordsheet",
                "Can approve chord sheets; their own are approved at once",
            )
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["song"],
                condition=Q(status="approved"),
                name="one_approved_sheet_per_song",
            )
        ]

    def __str__(self):
        return f"Chord sheet for {self.song.title} ({self.get_status_display()})"

    @property
    def is_approved(self):
        return self.status == self.Status.APPROVED


class SpotifyTokens(TimeStampedModel):
    """A Spotify account's tokens, stored **encrypted** with Fernet (the key
    is ``SPOTIFY_TOKEN_KEY`` in ``.env``); ``apps/songs/connections.py``
    reads and writes them. They are never shown, logged or put in the audit
    trail, and nothing else from the account is stored."""

    access_token_encrypted = models.TextField(editable=False)
    refresh_token_encrypted = models.TextField(editable=False)
    expires_at = models.DateTimeField(help_text="When the access token runs out.")
    scope = models.CharField(max_length=500, blank=True)

    class Meta:
        abstract = True


class SpotifyConnection(SpotifyTokens):
    """A user's own Spotify account, connected with the Authorization Code
    flow, for playback and (without a Church Spotify Account) for saving
    lineups as playlists."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="spotify_connection",
    )

    class Meta:
        default_permissions = ()

    def __str__(self):
        return f"Spotify connection {self.pk}"


class ChurchSpotifyAccount(SpotifyTokens):
    """The church's own Spotify account, an optional church setting
    (decision 0011). When it is connected, every Lineup Playlist is made
    and updated on it, as a public playlist. It holds only the playlist
    scopes and is never used for playback. A church has at most one
    (decision 0014)."""

    church = church_settings_field()

    connected_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )

    class Meta:
        default_permissions = ()

    def __str__(self):
        return "Church Spotify account"
