"""What Worship adds to the dashboard (Phase 9A, A7, part 3;
``apps/church/dashboard.py``): lineups to confirm, services with no theme
and chord sheets waiting for approval, for people who may act on them; and
the coming services."""

from django.db.models import Count, Q
from django.urls import reverse
from django.utils import timezone

from apps.church.dashboard import Attention, ComingUp
from apps.church.modules import is_enabled

from .models import Lineup, WorshipService
from .views.base import can_plan

THEMES_SHOWN = 3


def _labels(request):
    return request.church.label_set


def attention(request):
    user = request.user
    if not is_enabled("worship", getattr(request, "church", None)):
        return []
    now = timezone.now()
    items = []
    lineup_word = _labels(request).get("lineup")
    if user.has_perm("worship.change_lineup"):
        drafts = (
            Lineup.objects.filter(
                status=Lineup.Status.DRAFT,
                service__is_cancelled=False,
                service__starts_at__gte=now,
            )
            .select_related("service")
            .order_by("service__starts_at")
        )
        for lineup in drafts:
            service = lineup.service
            items.append(
                Attention(
                    text=f"Confirm the {lineup_word.lower()} for {service}",
                    detail=f"Saved {timezone.localtime(lineup.created_at):%b} "
                    f"{timezone.localtime(lineup.created_at).day}; the team sees it "
                    "once it is confirmed",
                    url=reverse(
                        "worship:lineup", kwargs={"public_id": service.public_id}
                    ),
                    button=f"Review {lineup_word.lower()}",
                    sort_key=(0, service.starts_at.timestamp()),
                )
            )
    if user.has_perm("worship.change_theme"):
        waiting = WorshipService.objects.filter(
            is_cancelled=False, starts_at__gte=now, theme__isnull=True
        ).order_by("starts_at")[:THEMES_SHOWN]
        for service in waiting:
            items.append(
                Attention(
                    text=f"Post the theme for {service}",
                    detail="Song suggestions start from it",
                    url=reverse(
                        "worship:theme", kwargs={"public_id": service.public_id}
                    ),
                    button="Post theme",
                    sort_key=(2, service.starts_at.timestamp()),
                )
            )
    if user.has_perm("songs.approve_chordsheet"):
        from apps.songs.models import ChordSheet

        pending = list(
            ChordSheet.objects.pending().select_related("song").order_by("created_at")
        )
        if pending:
            count = len(pending)
            titles = "; ".join(sorted({sheet.song.title for sheet in pending})[:3])
            items.append(
                Attention(
                    text=f"{count} chord sheet{'s' if count != 1 else ''} "
                    f"{'wait' if count != 1 else 'waits'} for approval",
                    detail=titles,
                    url=reverse(
                        "songs:detail", kwargs={"public_id": pending[0].song.public_id}
                    )
                    + "#chords",
                    button="Review sheet" if count == 1 else "Review sheets",
                    sort_key=(3, 0),
                )
            )
    return items


def coming_up(request):
    user = request.user
    if not (
        is_enabled("worship", getattr(request, "church", None))
        and user.has_perm("worship.view_worshipservice")
    ):
        return []
    services = (
        WorshipService.objects.filter(starts_at__gte=timezone.now())
        .select_related("theme", "lineup", "template")
        .order_by("starts_at")
    )
    show_lineup = user.has_perm("worship.view_lineup")
    plans = can_plan(user)
    show_team = is_enabled("teams") and user.has_perm("teams.view_assignment")
    if show_team:
        services = services.annotate(
            team_assigned=Count(
                "assignments",
                filter=Q(assignments__reply__in=("pending", "accepted")),
                distinct=True,
            ),
            team_accepted=Count(
                "assignments", filter=Q(assignments__reply="accepted"), distinct=True
            ),
        )
    rows = []
    for service in services[:5]:
        theme = service.posted_theme
        lineup = getattr(service, "lineup", None)
        status = None
        if show_lineup:
            if lineup is not None and lineup.is_confirmed:
                status = "confirmed"
            elif lineup is not None and plans:
                status = "draft"
            else:
                status = "none"
        team = None
        if show_team:
            team = (
                f"{service.team_accepted} of {service.team_assigned} accepted"
                if service.team_assigned
                else "No one yet"
            )
        rows.append(
            ComingUp(
                starts_at=service.starts_at,
                title=service.name,
                url=reverse("worship:service", kwargs={"public_id": service.public_id}),
                is_cancelled=service.is_cancelled,
                theme=theme.title if theme else "",
                passage=theme.scripture if theme else "",
                lineup=status,
                team=team,
            )
        )
    return rows
