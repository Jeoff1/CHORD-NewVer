"""The song library: the pool's songs, corrections, and adding from Spotify."""

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.utils.http import url_has_allowed_host_and_scheme
from django.views import View
from django.views.decorators.cache import never_cache
from django.views.generic import DetailView, TemplateView, UpdateView

from apps.audit.models import AuditEvent
from apps.audit.services import diff, record_change, snapshot
from apps.church.models import ChurchProfile
from apps.church.modules import ModuleRequiredMixin
from apps.core.music import Feel
from apps.core.views import FilteredListView, FormPageMixin
from apps.worship.views.base import settings_nav

from . import connections, pool, sheets
from .analysis import apply_check_rules
from .forms import (
    ChordSheetForm,
    SongForm,
    SpotifyTrackForm,
    WorshipCheckSettingsForm,
)
from .models import ChordSheet, Song, ThemeTag, WorshipCheckSettings
from .spotify import (
    SpotifyClient,
    SpotifyError,
    SpotifyRateLimited,
    block_message,
    current_block,
)
from .viewer import sheet_view

CHECK_SETTINGS_AUDIT_FIELDS = {
    "Pass mark": "pass_mark",
    "Artists not on the Trusted Artists list": lambda row: (
        row.get_unlisted_rule_display()
    ),
    "Stricter pass mark": "unlisted_pass_mark",
}


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

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        if request.headers.get("HX-Request"):
            # The viewer, this page's only htmx, re-renders the chord sheet.
            context = song_sheet_context(self.object, request)
            return render(request, "songs/includes/chord_sheet.html", context)
        return self.render_to_response(self.get_context_data(object=self.object))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        song = self.object
        context.update(song_sheet_context(song, self.request))
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


def safe_next(request, fallback):
    """The ``next`` URL from the request when it is on this site."""
    target = request.POST.get("next") or request.GET.get("next") or ""
    if target and url_has_allowed_host_and_scheme(
        target, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return target
    return fallback


def song_sheet_context(song, request, *, base_key="", sheet_url=None):
    """What a page shows about a song's chord sheet for ``request.user``:
    the approved sheet in the viewer (for people who may view sheets), the
    pending sheets they may see, whether they may add one, and Find chords.
    ``sheet_url`` is the page the viewer re-renders from; its query string
    holds the viewer's choices."""
    user = request.user
    approved = sheets.approved_sheet(song)
    context = {
        "approved_sheet": approved,
        "pending_sheets": sheets.pending_for(song, user),
        "may_add_sheet": sheets.may_add(user, song),
        "may_approve_sheets": sheets.may_approve(user),
        "find_chords": sheets.find_chords_links(song) if approved is None else [],
        "sheet_url": sheet_url
        or reverse("songs:detail", kwargs={"public_id": song.public_id}),
    }
    if approved is not None and user.has_perm(sheets.VIEW):
        context.update(
            sheet_view(
                approved,
                request.GET,
                base_key=base_key,
                recording_key=song.recording_key,
            )
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


class WorshipCheckSettingsView(SongsMixin, FormPageMixin, UpdateView):
    """The pass mark and the optional rule for artists not on the Trusted
    Artists list. Saving decides the Worship Check again for every song no
    person has reviewed (no model runs)."""

    permission_required = "songs.change_worshipchecksettings"
    form_class = WorshipCheckSettingsForm
    page_title = "Worship check"
    intro = (
        "How a song's worship score decides whether it is suggested. The score "
        "comes from the song's lyrics; a Trusted Artist adds 0.25. These are the "
        "church's rules, applied after the analysis."
    )

    def get_object(self, queryset=None):
        return WorshipCheckSettings.load()

    def get_success_url(self):
        return reverse("songs:check_settings")

    def get_links(self):
        return settings_nav(self.request)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        self.before = snapshot(self.object, CHECK_SETTINGS_AUDIT_FIELDS)
        return kwargs

    def form_valid(self, form):
        response = super().form_valid(form)
        record_change(
            self.request.user,
            self.object,
            AuditEvent.Action.CHANGED,
            diff(self.before, snapshot(self.object, CHECK_SETTINGS_AUDIT_FIELDS)),
        )
        changed = apply_check_rules()
        messages.success(
            self.request,
            f"The worship check settings were saved; {changed} "
            f"song{'s' if changed != 1 else ''} checked again.",
        )
        return response


# --- Chord sheets -----------------------------------------------------------------


class ChordSheetFormView(SongsMixin, View):
    """Add or replace a song's chord sheet, typed or pasted. Someone who may
    approve sheets saves an approved one; anyone else, a pending one for a
    song in a confirmed lineup (``sheets.py``)."""

    permission_required = sheets.ADD
    template_name = "songs/chordsheet_form.html"

    def dispatch(self, request, *args, **kwargs):
        self.song = get_object_or_404(Song, public_id=kwargs.get("public_id"))
        return super().dispatch(request, *args, **kwargs)

    def has_permission(self):
        return super().has_permission() and sheets.may_add(self.request.user, self.song)

    def back_url(self):
        fallback = (
            reverse("songs:detail", kwargs={"public_id": self.song.public_id})
            if self.request.user.has_perm("songs.view_song")
            else reverse("worship:home")
        )
        return safe_next(self.request, fallback)

    def starting_sheet(self):
        user = self.request.user
        if sheets.may_approve(user):
            return sheets.approved_sheet(self.song)
        return self.song.chord_sheets.pending().filter(added_by=user).first()

    def render_form(
        self, form, converted=False, imported="", import_error="", kept_warning=""
    ):
        return render(
            self.request,
            self.template_name,
            {
                "song": self.song,
                "form": form,
                "converted": converted,
                "imported": imported,
                "import_error": import_error,
                "kept_warning": kept_warning,
                "next": self.back_url(),
                "approves": sheets.may_approve(self.request.user),
                "find_chords": sheets.find_chords_links(self.song),
            },
        )

    def get(self, request, public_id):
        sheet = self.starting_sheet()
        initial = {"key": sheet.key, "chordpro": sheet.chordpro} if sheet else {}
        return self.render_form(ChordSheetForm(initial=initial))

    def import_file(self, request):
        """Put an uploaded ChordPro file's text, and the key it names, in
        the form for the person to check. Nothing is saved, and the file
        isn't kept."""
        initial = {
            "key": request.POST.get("key", ""),
            "chordpro": request.POST.get("chordpro", ""),
        }
        uploaded = request.FILES.get("import_file")
        if uploaded is None:
            return self.render_form(
                ChordSheetForm(initial=initial), import_error="Choose a file to import."
            )
        try:
            text, key = sheets.read_import(uploaded)
        except sheets.SheetRefused as refusal:
            return self.render_form(
                ChordSheetForm(initial=initial), import_error=str(refusal)
            )
        initial.update(chordpro=text, key=key or initial["key"])
        return self.render_form(ChordSheetForm(initial=initial), imported=uploaded.name)

    def post(self, request, public_id):
        if request.POST.get("action") == "import":
            return self.import_file(request)
        form = ChordSheetForm(request.POST)
        if not form.is_valid():
            return self.render_form(form)
        text, key = form.cleaned_data["chordpro"], form.cleaned_data["key"]
        if request.POST.get("action") == "convert":
            data = request.POST.copy()
            data["chordpro"], kept, stray = sheets.convert(text)
            return self.render_form(
                ChordSheetForm(data),
                converted=True,
                kept_warning=sheets.kept_message(kept, stray),
            )
        earlier = self.starting_sheet()
        before = snapshot(earlier, sheets.SHEET_AUDIT_FIELDS) if earlier else {}
        try:
            sheet = sheets.save(self.song, request.user, text, key)
        except sheets.SheetRefused as refusal:
            form.add_error("chordpro", str(refusal))
            return self.render_form(form)
        record_change(
            request.user,
            sheet,
            AuditEvent.Action.CHANGED if earlier else AuditEvent.Action.CREATED,
            diff(before, snapshot(sheet, sheets.SHEET_AUDIT_FIELDS)),
        )
        if sheet.is_approved:
            messages.success(
                request, f"The chord sheet for {self.song.title} was saved."
            )
        else:
            messages.success(
                request,
                f"Thanks: the chord sheet for {self.song.title} is waiting for "
                "approval. The team sees it once it is approved.",
            )
        if sheet.kept or sheet.stray:
            messages.warning(request, sheets.kept_message(sheet.kept, sheet.stray))
        return redirect(self.back_url())


class _SheetDecisionView(SongsMixin, View):
    """Approve or discard a pending chord sheet."""

    permission_required = sheets.APPROVE

    def post(self, request, pk):
        sheet = get_object_or_404(ChordSheet.objects.select_related("song"), pk=pk)
        fallback = reverse("songs:detail", kwargs={"public_id": sheet.song.public_id})
        before = snapshot(sheet, sheets.SHEET_AUDIT_FIELDS)
        try:
            self.decide(sheet, request.user)
        except sheets.SheetRefused as refusal:
            messages.error(request, str(refusal))
        else:
            self.record(sheet, before)
        return redirect(safe_next(request, fallback))


class SheetApproveView(_SheetDecisionView):
    def decide(self, sheet, user):
        sheets.approve(sheet, user)

    def record(self, sheet, before):
        sheet.refresh_from_db()
        record_change(
            self.request.user,
            sheet,
            AuditEvent.Action.CHANGED,
            diff(before, snapshot(sheet, sheets.SHEET_AUDIT_FIELDS)),
        )
        messages.success(
            self.request, f"The chord sheet for {sheet.song.title} was approved."
        )


class SheetDiscardView(_SheetDecisionView):
    def decide(self, sheet, user):
        sheets.discard(sheet, user)

    def record(self, sheet, before):
        record_change(
            self.request.user, sheet, AuditEvent.Action.DELETED, diff(before, {})
        )
        messages.success(self.request, "The pending chord sheet was discarded.")


# --- Playback and each user's Spotify account ------------------------------------


def playback_context(song, user):
    """How a song plays on its page (Design-Decisions, Phase 7). A
    connected account plays it in the browser with the Web Playback SDK,
    which needs Premium; the page's script falls back to Spotify's embedded
    player whenever the SDK can't be used. Without a connection the
    embedded player shows at once. "Open in Spotify" always shows."""
    if not song.spotify_id:
        return {"playback": None}
    return {
        "playback": {
            "track_uri": f"spotify:track:{song.spotify_id}",
            "embed_url": f"https://open.spotify.com/embed/track/{song.spotify_id}",
            "open_url": song.spotify_url,
            "use_sdk": connections.is_connected(user),
            "may_connect": connections.is_configured(),
        }
    }


class SpotifyAccountMixin(ModuleRequiredMixin, LoginRequiredMixin):
    """A person's own Spotify account: anyone signed in may connect theirs."""

    module = "worship"


def spotify_account_url():
    return reverse("songs:spotify_account")


class SpotifyAccountView(SpotifyAccountMixin, TemplateView):
    template_name = "songs/spotify_account.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            configured=connections.is_configured(),
            connection=connections.connection_for(self.request.user),
            next=safe_next(self.request, ""),
        )
        return context


class SpotifyConnectView(SpotifyAccountMixin, View):
    """Send the person to Spotify to agree; Spotify returns them to the
    callback below."""

    def post(self, request):
        if not connections.is_configured():
            messages.error(request, "Spotify isn't set up on this installation.")
            return redirect(spotify_account_url())
        target = connections.start(
            request,
            SpotifyClient.from_settings(),
            safe_next(request, spotify_account_url()),
        )
        return redirect(target)


class SpotifyCallbackView(SpotifyAccountMixin, View):
    """Where Spotify sends people back, for their own account or for the
    Church Spotify Account (one Redirect URI for both)."""

    def get(self, request):
        pending = connections.take_pending(request, request.GET.get("state", ""))
        if pending is None:
            messages.error(
                request,
                "That Spotify sign-in didn't come from this page. Connect again.",
            )
            return redirect(spotify_account_url())
        church = pending["purpose"] == connections.CHURCH
        home = church_spotify_url() if church else spotify_account_url()
        next_url = pending["next"] or home
        if church and not request.user.has_perm(CHURCH_SETTINGS):
            raise PermissionDenied
        code = request.GET.get("code", "")
        if request.GET.get("error") or not code:
            messages.info(request, "Spotify wasn't connected.")
            return redirect(next_url)
        if church:
            return self.finish_church(request, code, next_url)
        had_connection = connections.connection_for(request.user) is not None
        try:
            connections.finish(
                request.user,
                code,
                connections.redirect_uri(request),
                SpotifyClient.from_settings(),
            )
        except SpotifyError as error:
            messages.error(request, f"Spotify wasn't connected: {error}")
            return redirect(home)
        if not had_connection:
            record_change(
                request.user,
                request.user,
                AuditEvent.Action.CHANGED,
                {"Spotify account": ["Not connected", "Connected"]},
            )
        messages.success(request, "Your Spotify account is connected.")
        return redirect(next_url)

    def finish_church(self, request, code, next_url):
        had_account = connections.church_account() is not None
        try:
            connections.finish_church(
                request.user,
                code,
                connections.redirect_uri(request),
                SpotifyClient.from_settings(),
            )
        except SpotifyError as error:
            messages.error(request, f"Spotify wasn't connected: {error}")
            return redirect(church_spotify_url())
        _audit_church_account(request.user, connected=True, before=had_account)
        messages.success(
            request,
            "The church's Spotify account is connected. Lineup playlists are "
            "saved on it from now on.",
        )
        return redirect(next_url)


def _audit_church_account(user, *, connected, before):
    """The audit trail records only whether it is connected, never tokens."""
    if before == connected:
        return
    states = ["Not connected", "Connected"]
    record_change(
        user,
        ChurchProfile.load(),
        AuditEvent.Action.CHANGED,
        {"Church Spotify account": [states[before], states[connected]]},
    )


class SpotifyDisconnectView(SpotifyAccountMixin, View):
    def post(self, request):
        if connections.disconnect(request.user):
            record_change(
                request.user,
                request.user,
                AuditEvent.Action.CHANGED,
                {"Spotify account": ["Connected", "Not connected"]},
            )
            messages.success(
                request,
                "Your Spotify account was disconnected. You can also remove "
                "CHORD from the apps on your Spotify account page.",
            )
        return redirect(spotify_account_url())


@method_decorator(never_cache, name="dispatch")
class SpotifyPlayerTokenView(SpotifyAccountMixin, View):
    """The signed-in person's own access token, for the Web Playback SDK
    in their browser. Only the page's script reads it; it is never shown or
    logged, and the refresh token never leaves the server. A 429 or a block
    fails fast, so the player falls back at once."""

    def post(self, request):
        connection = connections.connection_for(request.user)
        if connection is None or not connections.is_configured():
            return JsonResponse({"error": "Spotify isn't connected."}, status=404)
        try:
            token = connections.access_token(connection, SpotifyClient.from_settings())
        except SpotifyRateLimited as limit:
            return JsonResponse({"error": str(limit)}, status=429)
        except SpotifyError as error:
            return JsonResponse({"error": str(error)}, status=502)
        seconds = (connection.expires_at - timezone.now()).total_seconds()
        return JsonResponse({"access_token": token, "expires_in": max(int(seconds), 0)})


# --- The Church Spotify Account (a church setting; decision 0011) ----------------

CHURCH_SETTINGS = "church.change_churchprofile"


def church_spotify_url():
    return reverse("songs:church_spotify")


class ChurchSpotifyMixin(
    ModuleRequiredMixin, LoginRequiredMixin, PermissionRequiredMixin
):
    """Only people who may change church settings (the Administrator by
    default) connect or disconnect the church's account."""

    module = "worship"
    permission_required = CHURCH_SETTINGS


class ChurchSpotifyView(ChurchSpotifyMixin, TemplateView):
    template_name = "songs/church_spotify.html"

    def get_context_data(self, **kwargs):
        from apps.church.forms import SECTION_ORDER, SECTIONS

        context = super().get_context_data(**kwargs)
        context.update(
            configured=connections.is_configured(),
            account=connections.church_account(),
            sections=[(key, SECTIONS[key][0]) for key in SECTION_ORDER],
            section="spotify",
        )
        return context


class ChurchSpotifyConnectView(ChurchSpotifyMixin, View):
    def post(self, request):
        if not connections.is_configured():
            messages.error(request, "Spotify isn't set up on this installation.")
            return redirect(church_spotify_url())
        target = connections.start(
            request,
            SpotifyClient.from_settings(),
            church_spotify_url(),
            purpose=connections.CHURCH,
        )
        return redirect(target)


class ChurchSpotifyDisconnectView(ChurchSpotifyMixin, View):
    def post(self, request):
        if connections.disconnect_church():
            _audit_church_account(request.user, connected=False, before=True)
            messages.success(
                request,
                "The church's Spotify account was disconnected. Lineup "
                "playlists go to the account of whoever saves them again.",
            )
        return redirect(church_spotify_url())
