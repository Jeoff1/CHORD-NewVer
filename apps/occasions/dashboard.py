"""What Occasions adds to the dashboard (Phase 9A, A7, part 3): waiting
requests for people who approve them, and the coming occasions for people
who may see them (decision 0013: everyone else sees none here)."""

from django.urls import reverse
from django.utils import timezone

from apps.church.dashboard import Attention, ComingUp
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
        OccasionRequest.objects.filter(status=OccasionRequest.Status.PENDING)
        .select_related("occasion_type")
        .order_by("starts_at")
    )
    if not pending:
        return []
    count = len(pending)
    kinds = sorted({record.occasion_type.name.lower() for record in pending})
    return [
        Attention(
            text=f"{count} occasion request{'s are' if count != 1 else ' is'} waiting",
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
        Occasion.objects.filter(starts_at__gte=timezone.now())
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
