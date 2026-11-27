"""What Occasions adds to the dashboard (Phase 9A, A7, part 3): waiting
requests for people who approve them, and the coming occasions for people
who may see them (decision 0013: everyone else sees none here); and the
pending requests and booked services among the overview figures. On screen
the Module is called Services: requests are "service requests" and
occasions "booked services"; its code keeps the name Occasions."""

from django.urls import reverse
from django.utils import timezone

from apps.church.dashboard import (
    Attention,
    ComingUp,
    Stat,
    stat_window,
    window_label,
)
from apps.church.modules import is_enabled

from . import rules
from .models import Occasion, OccasionRequest


def attention(request):
    user = request.user
    if not (
        is_enabled("occasions", getattr(request, "church", None))
        and user.has_perm(rules.APPROVE)
    ):
        return []
    pending = list(
        OccasionRequest.objects.for_church(request.church)
        .filter(status=OccasionRequest.Status.PENDING)
        .select_related("occasion_type")
        .order_by("starts_at")
    )
    if not pending:
        return []
    count = len(pending)
    kinds = sorted({record.occasion_type.name.lower() for record in pending})
    return [
        Attention(
            text=f"{count} service request{'s are' if count != 1 else ' is'} waiting",
            detail=", ".join(kinds).capitalize(),
            url=reverse("occasions:requests"),
            button="Open requests",
            sort_key=(1, 0),
        )
    ]


def coming_up(request):
    user = request.user
    if not (
        is_enabled("occasions", getattr(request, "church", None))
        and user.has_perm(rules.VIEW)
    ):
        return []
    occasions = (
        Occasion.objects.for_church(request.church)
        .filter(starts_at__gte=timezone.now())
        .select_related("occasion_type")
        .order_by("starts_at")[:5]
    )
    return [
        ComingUp(
            starts_at=occasion.starts_at,
            title=f"{occasion.occasion_type.name}: {occasion.occasion_for}",
            url=reverse("occasions:detail", kwargs={"public_id": occasion.public_id}),
            is_occasion=True,
            is_cancelled=occasion.is_cancelled,
        )
        for occasion in occasions
    ]


def stats(request):
    """All pending requests, for people who approve them, and the booked
    services in the window, for people who see them."""
    user = request.user
    if not is_enabled("occasions", getattr(request, "church", None)):
        return []
    found = []
    if user.has_perm(rules.APPROVE):
        found.append(
            Stat(
                label="Pending service requests",
                value=OccasionRequest.objects.for_church(request.church)
                .filter(status=OccasionRequest.Status.PENDING)
                .count(),
                period="All pending, any date",
                icon="inbox",
                url=reverse("occasions:requests"),
                order=20,
            )
        )
    if user.has_perm(rules.VIEW):
        start, end = stat_window()
        found.append(
            Stat(
                label="booked services",
                value=Occasion.objects.for_church(request.church)
                .filter(is_cancelled=False, starts_at__gte=start, starts_at__lt=end)
                .count(),
                period=window_label(),
                icon="flag",
                url=reverse("occasions:list"),
                primary=False,
                order=30,
            )
        )
    return found
