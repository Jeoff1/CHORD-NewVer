"""What Teams adds to the dashboard (Phase 9A, A7, part 3): the person's
next assignment, while Teams is on, for people on the team; and how many
assignments they have in the dashboard's window."""

from django.urls import reverse
from django.utils import timezone

from apps.church.dashboard import Panel, Stat, stat_window, window_label
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


def my_assignments(request):
    """The person's assignments in the window they haven't declined."""
    user = request.user
    if not (
        is_enabled("teams", getattr(request, "church", None))
        and user.has_perm(rostering.TEAM_PERMISSION)
    ):
        return []
    start, end = stat_window()
    count = (
        rostering.upcoming_assignments(user)
        .filter(
            service__is_cancelled=False,
            service__starts_at__gte=start,
            service__starts_at__lt=end,
        )
        .exclude(reply="declined")
        .count()
    )
    return [
        Stat(
            label=f"upcoming assignment{'s' if count != 1 else ''} for you",
            value=count,
            period=window_label(),
            icon="clock",
            url=reverse("teams:my_schedule"),
            primary=False,
            order=20,
        )
    ]
