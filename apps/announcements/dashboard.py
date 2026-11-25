"""What Announcements adds to the dashboard (Phase 9A, A7, part 3): the
latest two the person may see."""

from django.urls import reverse
from django.utils.timesince import timesince

from apps.church.dashboard import Panel
from apps.church.modules import is_enabled

from .services import audience_label, visible_to

SHOWN = 2


def latest(request):
    if not is_enabled("announcements", getattr(request, "church", None)):
        return None
    lines = [
        (
            announcement.title,
            f"{audience_label(announcement)} · {timesince(announcement.created_at)} ago",
            None,
        )
        for announcement in visible_to(request.user, request.church)[:SHOWN]
    ]
    return Panel(
        title="Announcements",
        link_label="All announcements",
        link_url=reverse("announcements:list"),
        lines=lines,
        empty="No announcements yet.",
    )
