"""Song suggestions on the service page, and their settings.

Suggestions are a lineup before it is confirmed, so team members never see
them: every view and panel here needs ``worship.suggest_songs``
(Design-Decisions, Phase 5).
"""

from django.conf import settings
from django.contrib import messages
from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.views import View
from django.views.generic import TemplateView, UpdateView

from apps.audit.models import AuditEvent
from apps.audit.services import diff, record_change, snapshot
from apps.core.music import Feel
from apps.core.views import FormPageMixin
from apps.songs import pool
from apps.songs.models import Song
from apps.songs.spotify import block_message, current_block

from .. import suggesting
from ..forms import SuggestionSettingsForm
from ..models import Suggestion, SuggestionSettings
from .base import ServiceMixin, WorshipMixin, settings_nav

SUGGEST = "worship.suggest_songs"

SETTINGS_AUDIT_FIELDS = {
    "Search genres": "search_genres",
    "Phrases per theme": "phrases_per_theme",
    "Pages per phrase": "pages_per_phrase",
    "Market": "market",
    "Theme match weight": "weight_relevance",
    "Familiarity weight": "weight_familiarity",
    "Season weight": "weight_season",
    "Recent use weight": "weight_recency",
    "Feel mismatch weight": "weight_feel",
    "Repeat window (weeks)": "repeat_window_weeks",
    "Ranked songs kept": "suggestions_kept",
}


def can_suggest(user):
    return user.has_perm(SUGGEST)


def spotify_configured():
    return bool(settings.SPOTIFY_CLIENT_ID and settings.SPOTIFY_CLIENT_SECRET)


def panel_context(service, user):
    """What the suggestions panel shows. Call it only for users who may
    suggest songs."""
    run = suggesting.latest_run(service)
    placed, others = suggesting.results(run) if run else ([], [])
    block = current_block()
    theme = service.posted_theme
    return {
        "run": run,
        "placed": placed,
        "others": others,
        "show_run_details": user.has_perm("worship.view_searchrun"),
        "worker_seems_stopped": bool(run) and suggesting.worker_seems_stopped(run),
        "spotify_ready": spotify_configured() and not (block and block.is_pause),
        "spotify_configured": spotify_configured(),
        "block_message": block_message(block) if block else "",
        "theme_needs_notes": bool(theme) and not theme.notes.strip(),
        "can_correct": user.has_perm("songs.change_song"),
        "feel_choices": Feel.choices,
    }


class _CorrectionView(ServiceMixin, View):
    """A one-click correction to a suggested song, from the panel. The run's
    songs are placed again at once; an HTMX request gets the panel back."""

    permission_required = (SUGGEST, "songs.change_song")

    def post(self, request, public_id, pk):
        suggestion = get_object_or_404(
            Suggestion.objects.select_related("song", "run"),
            pk=pk,
            run__service=self.service,
        )
        song = suggestion.song
        before = snapshot(song, pool.SONG_AUDIT_FIELDS)
        if not self.correct(song):
            return HttpResponseBadRequest("Choose upbeat, mid-tempo or slow.")
        record_change(
            request.user,
            song,
            AuditEvent.Action.CHANGED,
            diff(before, snapshot(song, pool.SONG_AUDIT_FIELDS)),
        )
        suggesting.place_again(suggestion.run)
        if request.headers.get("HX-Request"):
            context = {"service": self.service}
            context.update(panel_context(self.service, request.user))
            return render(request, "worship/includes/suggestions.html", context)
        return redirect(f"{self.service_url()}#suggestions")


class SuggestionFeelView(_CorrectionView):
    """Set a suggested song's feel. Analysing the song again keeps it."""

    def correct(self, song):
        feel = self.request.POST.get("feel", "")
        if feel not in Feel.values:
            return False
        song.feel, song.feel_reviewed = feel, True
        song.save(update_fields=["feel", "feel_reviewed", "updated_at"])
        return True


class NotWorshipView(_CorrectionView):
    """Mark a suggested song as not a worship song. A person decided it, so
    the song counts as Reviewed and analysis keeps the decision."""

    def correct(self, song):
        song.worship_check = Song.WorshipCheck.REJECTED
        song.reviewed_at, song.reviewed_by = timezone.now(), self.request.user
        song.save(
            update_fields=["worship_check", "reviewed_at", "reviewed_by", "updated_at"]
        )
        return True


class SuggestView(ServiceMixin, View):
    """Queue a Search Run for the service."""

    permission_required = SUGGEST

    def post(self, request, public_id):
        use_spotify = request.POST.get("source") != "pool"
        try:
            suggesting.request_run(self.service, request.user, use_spotify=use_spotify)
        except suggesting.RunRefused as refusal:
            messages.error(request, str(refusal))
        else:
            messages.success(
                request,
                "Finding songs. This page shows the progress; it can take a few "
                "minutes.",
            )
        return redirect(f"{self.service_url()}#suggestions")


class SuggestionPanelView(ServiceMixin, TemplateView):
    """The suggestions panel alone, which the service page reloads (HTMX)
    while a run is in progress."""

    permission_required = SUGGEST
    template_name = "worship/includes/suggestions.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(panel_context(self.service, self.request.user))
        return context


class SuggestionSettingsView(WorshipMixin, FormPageMixin, UpdateView):
    permission_required = "worship.change_suggestionsettings"
    form_class = SuggestionSettingsForm
    page_title = "Suggestion settings"
    intro = (
        "How songs are found on Spotify and ranked for a service's theme. "
        "Ranking adds the weighted theme match, familiarity and season fit, "
        "and takes away for recent use."
    )
    success_url = reverse_lazy("worship:suggestion_settings")

    def get_object(self, queryset=None):
        return SuggestionSettings.load()

    def get_links(self):
        return settings_nav(self.request)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        self.before = snapshot(self.object, SETTINGS_AUDIT_FIELDS)
        return kwargs

    def form_valid(self, form):
        response = super().form_valid(form)
        record_change(
            self.request.user,
            self.object,
            AuditEvent.Action.CHANGED,
            diff(self.before, snapshot(self.object, SETTINGS_AUDIT_FIELDS)),
        )
        messages.success(self.request, "The suggestion settings were saved.")
        return response
