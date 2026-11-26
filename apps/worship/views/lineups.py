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
from apps.church.scoping import get_in_church
from apps.core.views import FormPageMixin
from apps.songs import connections
from apps.songs.models import ChordSheet, Song
from apps.songs.views import playback_context, song_sheet_context
from apps.teams.views import service_team_context

from .. import lineups, playlists, suggesting
from ..forms import LineupItemForm, SendBackForm
from ..models import Lineup, LineupItem, SearchRun, Suggestion
from ..planning import CONFIRM, SONGS, planning_context, songs_step_label
from .base import ServiceMixin, can_plan
from .suggestions import can_suggest, panel_context, spotify_configured

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
    church = (
        configured and connections.church_account(lineup.service.church) is not None
    )
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


def playlist_preview(lineup, user, items):
    """What the Song Lineup page and the rundown say about the playlist
    before confirmation (Phase 9C): which songs it will hold, which have no
    Spotify track, and where it will be saved, or why it won't be. Nothing
    reaches Spotify here."""
    with_track = [item for item in items if item.song.spotify_id]
    without_track = [item for item in items if not item.song.spotify_id]
    connect_url = None
    if not connections.is_configured():
        where = ""
    elif connections.church_account(lineup.service.church) is not None:
        where = "on the church's Spotify account, as a public playlist"
    elif connections.is_connected(user):
        where = (
            "on the Spotify account of whoever confirms it, as a private "
            "playlist (yours, if you confirm)"
        )
    else:
        where = "on the Spotify account of whoever confirms it"
        connect_url = (
            f"{reverse('songs:spotify_account')}?"
            f"{urlencode({'next': lineup_url(lineup.service)})}"
        )
    return {
        "playlist_spotify_ready": connections.is_configured(),
        "playlist_with_track": with_track,
        "playlist_without_track": without_track,
        "playlist_where": where,
        "playlist_connect_url": connect_url,
    }


def plans(user):
    """People who plan see the Planning Steps on the lineup pages."""
    return can_plan(user) or lineups.sees_drafts(user)


def may_start(user):
    """Whether ``user`` may start a lineup by adding its first song."""
    return user.has_perm("worship.add_lineup") and user.has_perm(CHANGE)


def slot_rows(service, items, *, with_empty):
    """``[(kind, object)]``: the lineup's songs in order ("song", item) and,
    ``with_empty``, a row for each empty slot ("empty", slot) where its song
    would go (decision 0015)."""
    rows = [("song", item) for item in items]
    if not with_empty:
        return rows
    filled = {item.slot_id for item in items if item.slot_id}
    for slot in service.template.slots.all():
        if slot.pk in filled:
            continue
        index = next(
            (
                i
                for i, (kind, item) in enumerate(rows)
                if kind == "song"
                and (item.slot is None or item.slot.position > slot.position)
            ),
            len(rows),
        )
        rows.insert(index, ("empty", slot))
    return rows


class LineupView(ServiceMixin, TemplateView):
    """The Song Lineup step (Phase 9C; decision 0015): the lineup first,
    slot by slot, each empty slot with "Add a song"; the suggestions beside
    it, each with "Add"; the playlist preview. Before a lineup exists the
    slots are all empty. Team members see only a confirmed lineup."""

    template_name = "worship/lineup_detail.html"

    def has_permission(self):
        # People who may suggest songs, or start a lineup, work here even
        # before a lineup exists.
        user = self.request.user
        return (
            user.has_perm("worship.view_lineup") or can_suggest(user) or may_start(user)
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        service = self.service
        user = self.request.user
        lineup = Lineup.objects.filter(service=service).first()
        if lineup is not None and not user.has_perm("worship.view_lineup"):
            lineup = None
        if lineup is None:
            if not (can_suggest(user) or may_start(user)):
                raise Http404("This service has no lineup yet.")
            context.update(
                lineup=None,
                lineup_items=[],
                can_add_songs=may_start(user)
                and not suggesting.planning_closed(service),
            )
        elif not lineups.visible_to(lineup, user) and not lineup.is_being_revised:
            # A draft that was never confirmed doesn't exist for the team.
            raise Http404("This lineup isn't confirmed yet.")
        else:
            context.update(lineup_context(lineup, user))
            context["can_add_songs"] = context["can_change_lineup"]
        if lineup is None or context.get("lineup_visible"):
            context["slot_rows"] = slot_rows(
                service,
                context["lineup_items"],
                with_empty=lineup is None or context["sees_lineup_drafts"],
            )
        run = suggesting.latest_run(service)
        if can_suggest(user):
            context.update(panel_context(service, user))
            context.update(
                can_suggest=True,
                latest_run=run,
                ranked_count=run.suggestions.count()
                if run is not None and run.status == SearchRun.Status.DONE
                else 0,
                # A pop-up, not part of the page: the pool is empty, so
                # suggestions and Add a song need Find songs first.
                pool_empty_notice=not context["planning_closed"]
                and not (run is not None and run.is_active)
                and suggesting.pool_is_empty(service.church),
            )
        if plans(user):
            context.update(planning_context(service, user))
            context.update(
                step_here=SONGS,
                songs_label=songs_step_label(self.request.church.label_set),
            )
            if lineup is not None and context.get("lineup_visible"):
                context.update(playlist_preview(lineup, user, context["lineup_items"]))
        return context


# --- Making the lineup ----------------------------------------------------------


def _record(user, lineup, before):
    """The audit trail of a change to ``lineup`` (``before`` is None when it
    was just started)."""
    lineup = Lineup.objects.get(pk=lineup.pk)
    record_change(
        user,
        lineup,
        AuditEvent.Action.CREATED if before is None else AuditEvent.Action.CHANGED,
        diff(before or {}, snapshot(lineup, lineups.LINEUP_AUDIT_FIELDS)),
    )


def _start_and(request, service, action, *args):
    """Start the service's lineup if it has none, then run a rule from
    ``lineups`` on it and record the change. The rule's result, or None
    (with the reason shown) when it was refused."""
    try:
        lineup, started = lineups.start(service, request.user)
    except lineups.LineupRefused as refusal:
        messages.error(request, str(refusal))
        return None
    before = None if started else snapshot(lineup, lineups.LINEUP_AUDIT_FIELDS)
    try:
        result = action(lineup, *args, request.user)
    except lineups.LineupRefused as refusal:
        if started:
            lineup.delete()  # nothing was added: no empty lineup is left
        messages.error(request, str(refusal))
        return None
    _record(request.user, lineup, before)
    return result


class LineupCreateView(ServiceMixin, View):
    """Fill the empty slots with suggestions (decision 0015): the whole
    lineup when there is none yet, otherwise only the slots still empty."""

    permission_required = ("worship.add_lineup", "worship.suggest_songs")

    def post(self, request, public_id):
        service = self.service
        if not Lineup.objects.filter(service=service).exists():
            try:
                lineup = lineups.create_from_run(service, request.user)
            except lineups.LineupRefused as refusal:
                messages.error(request, str(refusal))
            else:
                _record(request.user, lineup, None)
                messages.success(request, "The slots were filled with suggested songs.")
            return redirect(lineup_url(service))
        result = _start_and(request, service, lineups.fill_from_suggestions)
        if result is not None:
            added = result[1]
            messages.success(
                request,
                f"{added} suggested song{'' if added == 1 else 's'} filled the "
                "empty slots.",
            )
        return redirect(lineup_url(service))


class AddSuggestionView(ServiceMixin, View):
    """Add one suggested song, picked by a person (decision 0015)."""

    permission_required = (CHANGE, "worship.suggest_songs")

    def post(self, request, public_id, pk):
        suggestion = get_object_or_404(
            Suggestion.objects.select_related("song", "slot", "run"),
            pk=pk,
            run__service=self.service,
        )
        item = _start_and(request, self.service, lineups.add_suggestion, suggestion)
        if item is not None:
            where = f"the {item.slot.name} slot" if item.slot else "the end"
            messages.success(request, f"{item.song.title} was added to {where}.")
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
        song = get_in_church(
            Song, request.church, public_id=request.POST.get("song") or None
        )
        if self.audited(lineups.swap, self.item, song):
            messages.success(request, f"{song.title} took its place.")
        return redirect(self.lineup_url())


class AddSongView(ServiceMixin, TemplateView):
    """Add a song of the person's own choosing (decision 0015): from the
    song pool, searching by title or artist, or from Spotify into the pool
    first. Adding the first song starts the lineup."""

    permission_required = CHANGE
    template_name = "worship/lineup_add.html"

    @cached_property
    def lineup(self):
        return Lineup.objects.filter(service=self.service).first()

    def get(self, request, *args, **kwargs):
        user = request.user
        lineup = self.lineup
        try:
            if lineup is not None:
                lineups.check_change(lineup, user)
            elif not may_start(user):
                raise lineups.LineupRefused("You may not start this lineup.")
        except lineups.LineupRefused as refusal:
            messages.error(request, str(refusal))
            return redirect(lineup_url(self.service))
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        query = self.request.GET.get("q", "").strip()[:100]
        slot = self.request.GET.get("slot", "")
        here = reverse(
            "worship:lineup_add", kwargs={"public_id": self.service.public_id}
        )
        if slot.isdigit():
            here += f"?{urlencode({'slot': slot})}"
        user = self.request.user
        context.update(
            q=query,
            songs=(
                _with_warnings(
                    lineups.addable_songs(self.service, self.lineup, query)[:25]
                )
                if query
                else None
            ),
            open_slots=lineups.open_slots(self.lineup, self.service),
            chosen_slot=int(slot) if slot.isdigit() else None,
            spotify_url=(
                f"{reverse('songs:spotify_search')}?"
                f"{urlencode({'q': query, 'next': here})}"
            )
            if user.has_perm("songs.add_song") and spotify_configured()
            else None,
        )
        return context

    def post(self, request, public_id):
        song = get_in_church(
            Song, request.church, public_id=request.POST.get("song") or None
        )
        slot = None
        if request.POST.get("slot"):
            slot = get_object_or_404(
                self.service.template.slots, pk=request.POST["slot"]
            )
        if _start_and(request, self.service, lineups.add_from_pool, song, slot):
            messages.success(request, f"{song.title} was added.")
        return redirect(lineup_url(self.service))


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
        # Without a service key, the sheet is shown in its own key.
        context["key_label"] = "Service key" if item.key else "Sheet's key"
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


def rundown_warnings(service, lineup, context):
    """What the rundown warns about before confirming (Phase 9C). Warnings
    never block confirming."""
    labels = service.church.label_set
    warnings = []
    if service.posted_theme is None:
        warnings.append("No theme is posted.")
    if context.get("show_team"):
        team = context["team"]
        team_word = labels.get("team")
        serving = [a for a in team if a.reply != "declined"]
        declined = len(team) - len(serving)
        pending = sum(a.reply == "pending" for a in serving)
        if not serving:
            warnings.append(f"Nobody is assigned to the {team_word} yet.")
        if declined:
            warnings.append(
                f"{declined} declined place{'' if declined == 1 else 's'} "
                f"need{'s' if declined == 1 else ''} filling."
            )
        if pending:
            warnings.append(
                f"{pending} {'person hasn' if pending == 1 else 'people haven'}'t "
                "replied yet."
            )
    items = context["lineup_items"]
    if not items:
        warnings.append(f"The {labels.get('lineup').lower()} has no songs.")
    slots = lineups.open_slots(lineup)
    if slots:
        warnings.append(f"Empty slots: {', '.join(slot.name for slot in slots)}.")
    no_sheet = [item.song.title for item in items if not item.has_sheet]
    if no_sheet:
        warnings.append(
            f"No chord sheet yet: {', '.join(no_sheet)}. Every song needs one "
            "once it is confirmed."
        )
    no_key = [item.song.title for item in items if not item.key]
    if no_key:
        warnings.append(f"No key set: {', '.join(no_key)}.")
    return warnings


class ConfirmView(LineupMixin, TemplateView):
    """The Confirm step (Phase 9C): a rundown of what will be confirmed,
    then the worship leader or anyone with the final say confirms."""

    template_name = "worship/lineup_confirm.html"

    def has_permission(self):
        user = self.request.user
        return user.has_perm(CHANGE) or user.has_perm(FINAL_SAY)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        service, lineup, user = self.service, self.lineup, self.request.user
        context.update(lineup_context(lineup, user))
        context.update(service_team_context(service, user))
        context.update(planning_context(service, user))
        context.update(playlist_preview(lineup, user, context["lineup_items"]))
        context.update(
            step_here=CONFIRM,
            songs_label=songs_step_label(self.request.church.label_set),
            theme=service.posted_theme,
            warnings=rundown_warnings(service, lineup, context),
            confirm_refused=service.is_cancelled
            and suggesting.planning_closed(service),
        )
        return context

    def post(self, request, public_id):
        if self.audited(lineups.confirm):
            messages.success(request, "Confirmed: the team can see it now.")
            # Saving to Spotify never undoes or delays the confirmation: it
            # fails fast and the page offers "Save to Spotify" instead.
            lineup = Lineup.objects.get(pk=self.lineup.pk)
            _report_playlist(request, playlists.save(lineup, request.user))
            return redirect(self.service_url())
        return redirect(
            reverse("worship:lineup_confirm", kwargs={"public_id": public_id})
        )


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
        elif connections.church_account(
            request.church
        ) is None and not connections.is_connected(request.user):
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
