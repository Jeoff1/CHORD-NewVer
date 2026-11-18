"""Song suggestions: the church's settings for them, its seasons, and each
search run with the songs it ranked."""

import datetime

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

from apps.core.setting_lists import ChoiceItem

from .schedule import TemplateSlot, WorshipService


def _weight(label, default, help_text):
    return models.FloatField(
        label,
        default=default,
        validators=[MinValueValidator(0), MaxValueValidator(10)],
        help_text=help_text,
    )


class SuggestionSettings(models.Model):
    """How the church wants songs found and ranked. There is one row."""

    search_genres = models.CharField(
        max_length=200,
        blank=True,
        default="worship",
        help_text="Spotify genres to search within, separated by commas. A "
        "search that finds nothing in a genre is run again without it. Leave "
        "blank to search every genre.",
    )
    phrases_per_theme = models.PositiveSmallIntegerField(
        default=4,
        validators=[MinValueValidator(1), MaxValueValidator(10)],
        help_text="How many words or short phrases from the theme to search for.",
    )
    pages_per_phrase = models.PositiveSmallIntegerField(
        default=2,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="Spotify returns 10 songs a page.",
    )
    market = models.CharField(
        max_length=2,
        blank=True,
        help_text="Two-letter country code, such as PH or US, to find only "
        "songs playable there. Leave blank for any country.",
    )
    weight_relevance = _weight(
        "Theme match weight", 1.0, "How much a song's lyrics matching the theme count."
    )
    # Defaults recalibrated for fixed-scale relevance (2026-11-18): the old
    # per-run scaling stretched about 0.27 of similarity to the full 0-to-1,
    # the fixed scale stretches 0.40, so the other weights shrank by about
    # 0.27 / 0.40 to keep the same trade-offs.
    weight_familiarity = _weight(
        "Familiarity weight", 0.2, "How much songs the team knows are preferred."
    )
    weight_season = _weight(
        "Season weight", 0.15, "How much songs that fit the current season count."
    )
    weight_recency = _weight(
        "Recent use weight", 0.3, "How much songs sung recently are held back."
    )
    weight_feel = _weight(
        "Feel mismatch weight",
        0.15,
        "How much a song loses when placed in a slot of another feel, for each "
        "step between upbeat, mid-tempo and slow.",
    )
    repeat_window_weeks = models.PositiveSmallIntegerField(
        "Repeat window (weeks)",
        default=4,
        validators=[MaxValueValidator(52)],
        help_text="A song sung within this many weeks is held back; the more "
        "recent, the more.",
    )
    suggestions_kept = models.PositiveSmallIntegerField(
        "Ranked songs kept",
        default=20,
        validators=[MinValueValidator(5), MaxValueValidator(100)],
        help_text="How many ranked songs each run keeps as choices.",
    )

    class Meta:
        verbose_name = "suggestion settings"
        verbose_name_plural = "suggestion settings"
        default_permissions = ("change", "view")

    def __str__(self):
        return "Suggestion settings"

    @classmethod
    def load(cls):
        settings_row, _ = cls.objects.get_or_create(pk=1)
        return settings_row

    def genres(self):
        return [g.strip() for g in self.search_genres.split(",") if g.strip()]

    def weights(self):
        return {
            "relevance": self.weight_relevance,
            "familiarity": self.weight_familiarity,
            "season": self.weight_season,
            "recency": self.weight_recency,
            "feel": self.weight_feel,
        }


class Season(ChoiceItem):
    """A time of the church's year, such as a time of preparation before a
    festival, with the Theme Tags that suit it. None are defined at first."""

    starts_on = models.DateField("Starts")
    ends_on = models.DateField("Ends")
    repeats_yearly = models.BooleanField(
        "Every year",
        default=False,
        help_text="Use only the month and day, so the season comes back every "
        "year. Leave off for seasons whose dates move.",
    )
    tags = models.ManyToManyField(
        "songs.ThemeTag",
        related_name="seasons",
        verbose_name="theme tags",
        help_text="Songs with any of these tags fit the season.",
    )

    class Meta(ChoiceItem.Meta):
        pass

    def contains(self, day):
        if not self.repeats_yearly:
            return self.starts_on <= day <= self.ends_on
        start = (self.starts_on.month, self.starts_on.day)
        end = (self.ends_on.month, self.ends_on.day)
        today = (day.month, day.day)
        if start <= end:
            return start <= today <= end
        return today >= start or today <= end  # runs over the new year


class SearchRun(models.Model):
    """One search for a service's songs: from its theme to ranked songs."""

    class Status(models.TextChoices):
        QUEUED = "queued", "Waiting"
        RUNNING = "running", "Running"
        DONE = "done", "Done"
        FAILED = "failed", "Failed"

    service = models.ForeignKey(
        WorshipService, on_delete=models.CASCADE, related_name="search_runs"
    )
    use_spotify = models.BooleanField(
        default=True, help_text="Off: rank the songs already in the pool."
    )
    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.QUEUED
    )
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    created_at = models.DateTimeField(default=timezone.now)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    # What happened, for the progress panel and for review.
    progress = models.PositiveSmallIntegerField(default=0)  # percent
    stage = models.CharField(max_length=200, blank=True)
    message = models.TextField(blank=True)
    phrases = models.JSONField(default=list, blank=True)
    theme_tags = models.JSONField(
        default=list, blank=True, help_text="Theme Tag IDs the theme is about."
    )
    pages_read = models.PositiveIntegerField(default=0)
    songs_found = models.PositiveIntegerField(default=0)
    songs_added = models.PositiveIntegerField(default=0)
    songs_analysed = models.PositiveIntegerField(default=0)
    songs_ranked = models.PositiveIntegerField(default=0)
    weights = models.JSONField(default=dict, blank=True)

    # Spotify usage, for the safeguards (Design-Decisions, Phase 5).
    spotify_calls = models.PositiveIntegerField(
        default=0, help_text="Requests sent to Spotify during the run."
    )
    spotify_limits = models.JSONField(
        default=list,
        blank=True,
        help_text="Each 429 met: when, why and the Retry-After, in seconds.",
    )
    fell_back = models.BooleanField(
        "Ranked the pool instead",
        default=False,
        help_text="Spotify was paused, so the run ranked the songs already in "
        "the pool.",
    )
    # Information only, never used in a decision (Design-Decisions, Phase 5
    # follow-up): which searches found nothing with the genre filter.
    searches = models.JSONField(
        default=list,
        blank=True,
        help_text="Each Spotify search: phrase, genre, pages, tracks found, and "
        "whether it ran again without the genre.",
    )

    class Meta:
        ordering = ["-created_at", "-pk"]
        default_permissions = ("view",)
        permissions = [("suggest_songs", "Can ask for song suggestions")]
        get_latest_by = "created_at"

    def __str__(self):
        return f"Song search for {self.service}"

    @property
    def is_active(self):
        return self.status in (self.Status.QUEUED, self.Status.RUNNING)

    @property
    def run_time(self):
        if self.started_at and self.finished_at:
            return self.finished_at - self.started_at
        return None

    def run_time_display(self):
        duration = self.run_time
        if duration is None:
            return ""
        seconds = round(duration / datetime.timedelta(seconds=1))
        minutes, seconds = divmod(seconds, 60)
        return f"{minutes} min {seconds} s" if minutes else f"{seconds} s"

    @property
    def genre_dropped_searches(self):
        return [search for search in self.searches if search.get("genre_dropped")]


class Suggestion(models.Model):
    """A song a run ranked, with why. Songs placed in the service's song
    slots have a slot; the rest are choices for swapping."""

    run = models.ForeignKey(
        SearchRun, on_delete=models.CASCADE, related_name="suggestions"
    )
    song = models.ForeignKey(
        "songs.Song", on_delete=models.CASCADE, related_name="suggestions"
    )
    rank = models.PositiveSmallIntegerField()
    score = models.FloatField()
    relevance = models.FloatField()
    familiarity = models.FloatField()
    season = models.FloatField()
    recency = models.FloatField()
    match = models.FloatField(
        null=True, blank=True, help_text="The raw similarity of theme and lyrics."
    )
    slot = models.ForeignKey(
        TemplateSlot,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    slot_reason = models.CharField(
        max_length=200,
        blank=True,
        help_text="Why the song is in its slot, when that needs saying.",
    )
    reasons = models.JSONField(default=list)

    class Meta:
        ordering = ["rank"]
        default_permissions = ()
        constraints = [
            models.UniqueConstraint(fields=["run", "song"], name="one_song_per_run")
        ]

    def __str__(self):
        return f"{self.rank}. {self.song}"
