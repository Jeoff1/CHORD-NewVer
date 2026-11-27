"""What Members adds to the dashboard (dashboard redesign): how many people
the directory holds, archived ones left out, for people who may open it."""

from django.urls import reverse

from apps.church.dashboard import Stat
from apps.church.modules import is_enabled

from .models import Member


def active_members(request):
    user = request.user
    if not (
        is_enabled("members", getattr(request, "church", None))
        and user.has_perm("members.view_member")
    ):
        return []
    label = request.church.label_set.get("member", plural=True).lower()
    return [
        Stat(
            label=f"active {label}",
            value=Member.objects.current().count(),
            period="Total, archived ones left out",
            icon="people",
            url=reverse("members:list"),
            primary=False,
            order=10,
        )
    ]
