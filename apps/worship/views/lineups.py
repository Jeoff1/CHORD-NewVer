"""A service's lineup: making it from suggestions, reviewing, confirming,
and the final say (Design-Decisions, Phase 6; decision 0008).

The rules are in ``apps/worship/lineups.py``; these views check the
permissions, call the rules, and record the audit trail. Team members see
a lineup only once it is confirmed; while a lineup that was confirmed is a
draft again, they see only a note that it is being revised.
"""

from django.contrib import messages
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import formats
from django.utils.functional import cached_property
from django.utils.http import urlencode
from django.views import View
from django.views.generic import FormView, TemplateView, UpdateView

from apps.audit.models import AuditEvent
from apps.audit.services import diff, record_change, snapshot
from apps.core.views import FormPageMixin
from apps.songs import connections
from apps.songs.models import ChordSheet, Song
from apps.songs.views import playback_context, song_sheet_context

from .. import lineups, playlists
from ..forms import LineupItemForm, SendBackForm
from ..models import Lineup, LineupItem
from .base import ServiceMixin

CHANGE = lineups.CHANGE
FINAL_SAY = lineups.FINAL_SAY


def lineup_url(service):
    return reverse("worship:lineup", kwargs={"public_id": service.public_id})


def _with_warnings(objects, song=lambda obj: obj):
    """``objects`` as a list, each with ``check_warning``: what its song's
    Worship Check warns about in the review ("" when it passed)."""
    objects = list(objects)
    for obj in objects:
        obj.check_warning = lineups.check_warning(song(obj))
    return objects


def lineup_context(lineup, user):
    """What the lineup page and the service page's lineup card show."""
    visible = lineup is not None and lineups.visible_to(lineup, user)
    if lineup is None or not (visible or lineup.is_being_revised):
        # No lineup, or a draft the user may not see and that was never
        # confirmed: for them there is no lineup yet.
        return {"lineup": None}
    items = _with_warnings(
        lineup.items.select_related("song", "slot").order_by("position", "pk")
        if visible
        else [],
        song=lambda item: item.song,
    )
    # Arrows show only for moves the rules allow (``lineups.move``).
    moves = lineups.allowed_moves(items)
    # Which songs have an approved chord sheet: required once confirmed.
    with_sheet = set(
        ChordSheet.objects.approved()
        .filter(song_id__in=[item.song_id for item in items])
        .values_list("song_id", flat=True)
    )
    for item in items:
        item.can_move_up, item.can_move_down = moves[item.pk]
        item.has_sheet = item.song_id in with_sheet
    tracks = [item.song.spotify_id for item in items if item.song.spotify_id]
    return {
        **(playlist_context(lineup, user, tracks) if visible else {}),
        "lineup": lineup,
        "lineup_visible": visible,
        "lineup_items": items,
        "sheets_ready": sum(1 for item in items if item.has_sheet),
        "lineup_revising": lineup.is_being_revised,
        "can_change_lineup": lineups.may_change(lineup, user),
        "can_confirm_lineup": lineups.may_confirm(lineup, user),
        "has_final_say": lineups.has_final_say(user),
        "sees_lineup_drafts": lineups.sees_drafts(user),
    }


def playlist_context(lineup, user, tracks):
    """The Lineup Playlist, and whether to offer "Save to Spotify" (to
    people who confirm lineups, once it is confirmed, while no playlist
    holds its current songs). A playlist on the Church Spotify Account is
    public, so everyone who sees the confirmed lineup gets its link; a
    personal one is private, so only its owner does (Design-Decisions,
    Phase 7; decision 0011)."""
    configured = connections.is_configured()
    church = configured and connections.church_account() is not None
    may_save = playlists.may_save(user)
    on_church = bool(lineup.spotify_playlist_id) and (
        lineup.spotify_playlist_on_church_account
    )
    return {
        "may_save_playlist": may_save,
        "offer_spotify_save": configured
        and may_save
        and playlists.needs_saving(lineup, tracks, church=church),
        # Saving works without a personal connection when the church's
        # account is connected.
        "spotify_save_ready": church or (configured and connections.is_connected(user)),
        "church_playlist": on_church,
        "spotify_playlist_is_mine": bool(lineup.spotify_playlist_id)
        and not on_church
        and lineup.spotify_playlist_owner_id == user.pk,
    }


class LineupMixin(ServiceMixin):
    """Gives the service's lineup as ``self.lineup`` (404 when it has none)."""

    @cached_property
    def lineup(self):
        lineup = Lineup.objects.filter(service=self.service).first()
        if lineup is None:
            raise Http404("This service has no lineup yet.")
        return lineup

    def lineup_url(self):
        return lineup_url(self.service)

    def audited(self, action, *args):
        """Run a rule from ``lineups`` on the lineup, record the change, and
        say what went wrong when the rule refuses."""
        before = snapshot(self.lineup, lineups.LINEUP_AUDIT_FIELDS)
        try:
            action(self.lineup, *args, self.request.user)
        except lineups.LineupRefused as refusal:
            messages.error(self.request, str(refusal))
            return False
        lineup = Lineup.objects.get(pk=self.lineup.pk)
        record_change(
            self.request.user,
            lineup,
            AuditEvent.Action.CHANGED,
            diff(before, snapshot(lineup, lineups.LINEUP_AUDIT_FIELDS)),
        )
        return True

    def refuse_unless_changeable(self):
        """A redirect with the reason when the user may not change the
        lineup now (the pastor's lock); None when they may."""
        try:
            lineups.check_change(self.lineup, self.request.user)
        except lineups.LineupRefused as refusal:
            messages.error(self.request, str(refusal))
            return redirect(self.lineup_url())
        return None


class ItemMixin(LineupMixin):
    @cached_property
    def item(self):
        return get_object_or_404(
            LineupItem.objects.select_related("song", "slot"),
            pk=self.kwargs["pk"],
            lineup=self.lineup,
        )


# --- Seeing the lineup --------------------------------------------------------


class LineupView(LineupMixin, TemplateView):
    permission_required = "worship.view_lineup"
    template_name = "worship/lineup_detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        lineup = self.lineup
        user = self.request.user
        if not lineups.visible_to(lineup, user) and not lineup.is_being_revised:
            # A draft that was never confirmed doesn't exist for the team.
            raise Http404("This lineup isn't confirmed yet.")
        context.update(lineup_context(lineup, user))
        if context["can_change_lineup"]:
            context["open_slots"] = lineups.open_slots(lineup)
        return context


# --- Making the lineup ----------------------------------------------------------


class LineupCreateView(ServiceMixin, View):
    """Make the lineup from the suggestions the planner has reviewed."""

    permission_required = ("worship.add_lineup", "worship.suggest_songs")

    def post(self, request, public_id):
        try:
            lineup = lineups.create_from_run(self.service, request.user)
        except lineups.LineupRefused as refusal:
            messages.error(request, str(refusal))
            return redirect(f"{self.service_url()}#suggestions")
        record_change(
            request.user,
            lineup,
            AuditEvent.Action.CREATED,
            diff({}, snapshot(lineup, lineups.LINEUP_AUDIT_FIELDS)),
        )
        messages.success(request, "The suggested songs were saved as a draft.")
        return redirect(lineup_url(self.service))


# --- Review actions ---------------------------------------------------------------


class ItemActionView(ItemMixin, View):
    """Lock, unlock, move up or down, or remove one song."""

    permission_required = CHANGE
    ACTIONS = {
        "lock": lambda lineup, item, user: lineups.set_locked(lineup, item, True, user),
        "unlock": lambda lineup, item, user: lineups.set_locked(
            lineup, item, False, user
        ),
        "up": lambda lineup, item, user: lineups.move(lineup, item, -1, user),
        "down": lambda lineup, item, user: lineups.move(lineup, item, 1, user),
        "remove": lineups.remove,
    }

    def post(self, request, public_id, pk, action):
        if action not in self.ACTIONS:
            raise Http404("No such action.")
        self.audited(self.ACTIONS[action], self.item)
        return redirect(self.lineup_url())


class SwapView(ItemMixin, TemplateView):
    """Choose a ranked alternative for one song."""

    permission_required = CHANGE
    template_name = "worship/lineup_swap.html"

    def get(self, request, *args, **kwargs):
        return self.refuse_unless_changeable() or super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            item=self.item,
            alternatives=lineups.alternatives(self.lineup, self.item),
        )
        return context

    def post(self, request, public_id, pk):
        song = get_object_or_404(Song, public_id=request.POST.get("song") or None)
        if self.audited(lineups.swap, self.item, song):
            messages.success(request, f"{song.title} took its place.")
        return redirect(self.lineup_url())


class AddSongView(LineupMixin, TemplateView):
    """Add a song from the pool, searching by title or artist."""

    permission_required = CHANGE
    template_name = "worship/lineup_add.html"

    def get(self, request, *args, **kwargs):
        return self.refuse_unless_changeable() or super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        query = self.request.GET.get("q", "").strip()[:100]
        context.update(
            q=query,
            songs=(
                _with_warnings(lineups.addable_songs(self.lineup, query)[:25])
                if query
                else None
            ),
            open_slots=lineups.open_slots(self.lineup),
        )
        return context

    def post(self, request, public_id):
        song = get_object_or_404(Song, public_id=request.POST.get("song") or None)
        slot = None
        if request.POST.get("slot"):
            slot = get_object_or_404(
                self.service.template.slots, pk=request.POST["slot"]
            )
        if self.audited(lineups.add_from_pool, song, slot):
            messages.success(request, f"{song.title} was added.")
        return redirect(self.lineup_url())


class ItemDetailsView(ItemMixin, FormPageMixin, UpdateView):
    """A song's service key and notes."""

    permission_required = CHANGE
    form_class = LineupItemForm
    submit_label = "Save"

    def get_object(self, queryset=None):
        return self.item

    def get(self, request, *args, **kwargs):
        return self.refuse_unless_changeable() or super().get(request, *args, **kwargs)

    def get_page_title(self):
        return f"{self.item.song.title}: key and notes"

    @property
    def intro(self):
        """The keys the song was sung in before, most recent first."""
        history = lineups.key_history(self.item)
        if not history:
            return "Not sung in a confirmed lineup before, so there is no key to go by."
        sung = ", ".join(
            f"{key} ({formats.date_format(service.local_date, 'M j, Y')})"
            for key, service in history
        )
        return f"Sung before in: {sung}."

    def get_cancel_url(self):
        return self.lineup_url()

    def form_valid(self, form):
        key, notes = form.cleaned_data["key"], form.cleaned_data["notes"]
        # The form copied the values onto the item; the rule saves them.
        self.item.refresh_from_db()
        if self.audited(lineups.set_details, self.item, key, notes):
            messages.success(self.request, f"{self.item.song.title} was saved.")
        return redirect(self.lineup_url())


class LineupSongView(ItemMixin, TemplateView):
    """One song of the lineup: its slot and key, and its chord sheet in the
    service key, with the viewer (decision 0009). Team members open it only
    once the lineup is confirmed."""

    permission_required = "worship.view_lineup"
    template_name = "worship/lineup_song.html"

    def visible_item(self):
        if not lineups.visible_to(self.lineup, self.request.user):
            raise Http404("This lineup isn't confirmed yet.")
        return self.item

    def sheet_context(self):
        item = self.visible_item()
        context = song_sheet_context(
            item.song,
            self.request,
            base_key=item.key,
            sheet_url=reverse(
                "worship:lineup_song",
                kwargs={"public_id": self.service.public_id, "pk": item.pk},
            ),
        )
        context["key_label"] = "Service key"
        return context

    def get(self, request, *args, **kwargs):
        if request.headers.get("HX-Request"):
            # The viewer re-renders only the chord sheet.
            return render(
                request, "songs/includes/chord_sheet.html", self.sheet_context()
            )
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(self.sheet_context())
        context.update(playback_context(self.item.song, self.request.user))
        context.update(
            item=self.item,
            song=self.item.song,
            here=self.request.get_full_path(),
        )
        # The lineup's order: Previous and Next, "song N of M" and the
        # "This lineup" list (Phase 9A, A7).
        items = list(
            self.lineup.items.select_related("song", "slot").order_by("position", "pk")
        )
        index = next(i for i, item in enumerate(items) if item.pk == self.item.pk)
        context.update(
            lineup_order=items,
            song_number=index + 1,
            previous_item=items[index - 1] if index > 0 else None,
            next_item=items[index + 1] if index + 1 < len(items) else None,
        )
        return context


class RegenerateView(LineupMixin, View):
    """Fill the lineup again from the latest suggestions, around locked songs."""

    permission_required = CHANGE

    def post(self, request, public_id):
        if self.audited(lineups.regenerate):
            messages.success(
                request, "The songs were chosen again; locked songs stayed."
            )
        return redirect(self.lineup_url())


# --- Confirmation and the final say ------------------------------------------------


class ConfirmView(LineupMixin, View):
    """The worship leader or anyone with the final say confirms."""

    def has_permission(self):
        user = self.request.user
        return user.has_perm(CHANGE) or user.has_perm(FINAL_SAY)

    def post(self, request, public_id):
        if self.audited(lineups.confirm):
            messages.success(request, "Confirmed: the team can see it now.")
            # Saving to Spotify never undoes or delays the confirmation: it
            # fails fast and the page offers "Save to Spotify" instead.
            lineup = Lineup.objects.get(pk=self.lineup.pk)
            _report_playlist(request, playlists.save(lineup, request.user))
        return redirect(self.lineup_url())


def _report_playlist(request, outcome):
    if outcome.saved:
        messages.success(request, outcome.message)
    elif outcome.message:
        messages.warning(request, outcome.message)


class SavePlaylistView(LineupMixin, View):
    """Save to Spotify: the confirmed lineup as its playlist, on the Church
    Spotify Account when it is connected, otherwise on the account of the
    person pressing it."""

    def has_permission(self):
        return playlists.may_save(self.request.user)

    def post(self, request, public_id):
        lineup = self.lineup
        if not lineup.is_confirmed:
            word = request.church.label_set.get("lineup").lower()
            messages.error(request, f"Confirm the {word} before saving it to Spotify.")
        elif connections.church_account() is None and not connections.is_connected(
            request.user
        ):
            messages.info(
                request, "Connect your Spotify account first, then save again."
            )
            query = urlencode({"next": self.lineup_url()})
            return redirect(f"{reverse('songs:spotify_account')}?{query}")
        else:
            _report_playlist(request, playlists.save(lineup, request.user))
        return redirect(self.lineup_url())


class ReopenView(LineupMixin, View):
    permission_required = FINAL_SAY

    def post(self, request, public_id):
        if self.audited(lineups.reopen):
            messages.success(
                request,
                "Reopened as a draft. The team sees that it is being revised.",
            )
        return redirect(self.lineup_url())


class SendBackView(LineupMixin, FormPageMixin, FormView):
    """Return the lineup to draft with a note for the worship leader."""

    permission_required = FINAL_SAY
    form_class = SendBackForm
    submit_label = "Send back"

    def get_page_title(self):
        word = self.request.church.label_set.get("lineup").lower()
        return f"Send the {word} back"

    def get_context_data(self, **kwargs):
        # Raise 404 for a service without a lineup before the page renders.
        self.lineup
        return super().get_context_data(**kwargs)

    @property
    def intro(self):
        word = self.request.church.label_set.get("lineup").lower()
        return (
            f"The {word} goes back to draft, and the worship leader sees your "
            "note. The team can't see it until it is confirmed again."
        )

    def get_cancel_url(self):
        return self.lineup_url()

    def form_valid(self, form):
        if self.audited(lineups.send_back, form.cleaned_data["note"]):
            messages.success(self.request, "Sent back with your note.")
        return redirect(self.lineup_url())
