"""The song library: the pool's songs, corrections, and adding from Spotify."""

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.views import View
from django.views.generic import DetailView, TemplateView, UpdateView

from apps.audit.models import AuditEvent
from apps.audit.services import diff, record_change, snapshot
from apps.church.modules import ModuleRequiredMixin
from apps.core.music import Feel
from apps.core.views import FilteredListView, FormPageMixin
from apps.worship.views.base import settings_nav

from . import pool
from .forms import SongForm, SpotifyTrackForm
from .models import Song, ThemeTag
from .spotify import SpotifyClient, SpotifyError, block_message, current_block


class SongsMixin(ModuleRequiredMixin, LoginRequiredMixin, PermissionRequiredMixin):
    module = "worship"


def song_url(song):
    return reverse("songs:detail", kwargs={"public_id": song.public_id})


def _percent(score):
    return None if score is None else round(score * 100)


class SongListView(SongsMixin, FilteredListView):
    permission_required = "songs.view_song"
    model = Song
    template_name = "songs/song_list.html"
    search_fields = ("title", "artist", "album")
    KNOWN = {"yes": "The team knows it", "no": "New to the team"}

    def filters(self):
        get = self.request.GET.get
        return {
            "check": get("check", "") if get("check") in Song.WorshipCheck else "",
            "feel": get("feel", "") if get("feel") in Feel else "",
            "lyrics": get("lyrics", "") if get("lyrics") in Song.LyricsStatus else "",
            "known": get("known", "") if get("known") in self.KNOWN else "",
            "tag": get("tag", "") if get("tag", "").isdigit() else "",
        }

    def get_queryset(self):
        queryset = super().get_queryset().prefetch_related("tags")
        chosen = self.filters()
        if chosen["check"]:
            queryset = queryset.filter(worship_check=chosen["check"])
        if chosen["feel"]:
            queryset = queryset.filter(feel=chosen["feel"])
        if chosen["lyrics"]:
            queryset = queryset.filter(lyrics_status=chosen["lyrics"])
        if chosen["known"]:
            queryset = queryset.filter(team_knows=chosen["known"] == "yes")
        if chosen["tag"]:
            queryset = queryset.filter(tags__pk=chosen["tag"])
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            chosen=self.filters(),
            check_choices=Song.WorshipCheck.choices,
            feel_choices=Feel.choices,
            lyrics_choices=Song.LyricsStatus.choices,
            known_choices=self.KNOWN.items(),
            tags=ThemeTag.objects.active(),
            settings_url=next(iter(settings_nav(self.request)), (None, None))[1],
        )
        return context


class SongDetailView(SongsMixin, DetailView):
    permission_required = "songs.view_song"
    model = Song
    slug_field = "public_id"
    slug_url_kwarg = "public_id"
    template_name = "songs/song_detail.html"

    def get_queryset(self):
        return Song.objects.select_related("reviewed_by")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        song = self.object
        context.update(
            ranked_tags=song.ranked_tags(),
            worship_percent=_percent(song.worship_model_score),
            # The Trusted Artist bonus raised the score the check uses.
            bonus_percent=(
                _percent(song.worship_score - song.worship_model_score)
                if song.worship_score is not None
                and song.worship_model_score is not None
                and song.worship_score > song.worship_model_score
                else None
            ),
        )
        return context


class SongUpdateView(SongsMixin, FormPageMixin, UpdateView):
    permission_required = "songs.change_song"
    model = Song
    form_class = SongForm
    slug_field = "public_id"
    slug_url_kwarg = "public_id"
    intro = (
        "Your corrections stay when the song is analysed again; only the "
        "scores are renewed."
    )

    def get_page_title(self):
        return f"Edit {self.object}"

    def get_success_url(self):
        return song_url(self.object)

    def get_cancel_url(self):
        return song_url(self.object)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        self.before = snapshot(self.object, pool.SONG_AUDIT_FIELDS)
        return kwargs

    def form_valid(self, form):
        form.instance.reviewed_at = timezone.now()
        form.instance.reviewed_by = self.request.user
        response = super().form_valid(form)
        record_change(
            self.request.user,
            self.object,
            AuditEvent.Action.CHANGED,
            diff(self.before, snapshot(self.object, pool.SONG_AUDIT_FIELDS)),
        )
        messages.success(self.request, f"{self.object} was saved.")
        return response


class SongCheckAgainView(SongsMixin, View):
    """Queue a song for a fresh lyrics lookup and analysis."""

    permission_required = "songs.change_song"

    def post(self, request, public_id):
        song = get_object_or_404(Song, public_id=public_id)
        before = snapshot(song, pool.SONG_AUDIT_FIELDS)
        pool.check_again(song)
        record_change(
            request.user,
            song,
            AuditEvent.Action.CHANGED,
            diff(before, snapshot(song, pool.SONG_AUDIT_FIELDS)),
        )
        messages.success(
            request,
            "The song will be checked again the next time songs are processed.",
        )
        return redirect(song_url(song))


class SpotifySearchView(SongsMixin, TemplateView):
    """Find a track on Spotify and add it to the pool. It searches only when
    the form is submitted, never as the user types (a Spotify safeguard)."""

    permission_required = "songs.add_song"
    template_name = "songs/spotify_search.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        query = self.request.GET.get("q", "").strip()[:200]
        block = current_block()
        context.update(
            q=query,
            tracks=None,
            problem="",
            block_message=block_message(block) if block else "",
        )
        if not query:
            return context
        try:
            tracks = SpotifyClient.from_settings().search_tracks(query).tracks
        except SpotifyError as error:
            context["problem"] = str(error)
            return context
        in_pool = dict(
            Song.objects.filter(
                spotify_id__in=[track.spotify_id for track in tracks]
            ).values_list("spotify_id", "public_id")
        )
        context["tracks"] = [(track, in_pool.get(track.spotify_id)) for track in tracks]
        return context


class SpotifyAddView(SongsMixin, View):
    permission_required = "songs.add_song"

    def post(self, request):
        form = SpotifyTrackForm(request.POST)
        if not form.is_valid():
            messages.error(request, "That isn't a Spotify track.")
            return redirect("songs:spotify_search")
        spotify_id = form.cleaned_data["spotify_id"]
        # A Spotify safeguard: never fetch a track the pool already has.
        known = Song.objects.filter(spotify_id=spotify_id).first()
        if known is not None:
            messages.info(request, f"{known} is already in the song pool.")
            return redirect(song_url(known))
        try:
            track = SpotifyClient.from_settings().get_track(spotify_id)
        except SpotifyError as error:
            messages.error(request, str(error))
            return redirect("songs:spotify_search")
        song, created = pool.add_from_spotify(track)
        if created:
            record_change(
                request.user,
                song,
                AuditEvent.Action.CREATED,
                diff({}, snapshot(song, pool.SONG_AUDIT_FIELDS)),
            )
            messages.success(
                request,
                f"{song} was added. Its lyrics are fetched and analysed the "
                "next time songs are processed.",
            )
        else:
            messages.info(request, f"{song} is already in the song pool.")
        return redirect(song_url(song))
