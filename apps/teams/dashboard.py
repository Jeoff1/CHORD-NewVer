"""What Teams adds to the dashboard (Phase 9A, A7, part 3): the person's
next assignment, while Teams is on, for people on the team."""

from django.urls import reverse
from django.utils import timezone

from apps.church.dashboard import Panel
from apps.church.modules import is_enabled

from . import rostering


def my_schedule(request):
    user = request.user
    if not (
        is_enabled("teams", getattr(request, "church", None))
        and user.has_perm(rostering.TEAM_PERMISSION)
    ):
        return None
    upcoming = rostering.upcoming_assignments(user).filter(
        service__is_cancelled=False, service__starts_at__gte=timezone.now()
    )
    lines = []
    assignment = upcoming.first()
    if assignment is not None:
        when = timezone.localtime(assignment.service.starts_at)
        lines.append(
            (
                f"{when:%a, %b} {when.day} · {assignment.part}",
                assignment.service.name,
                assignment.reply,
            )
        )
    return Panel(
        title="My schedule",
        link_label="Open my schedule",
        link_url=reverse("teams:my_schedule"),
        lines=lines,
        empty="You have no coming assignments.",
    )
