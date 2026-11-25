import zoneinfo

from django.shortcuts import render
from django.utils import timezone

from .models import ChurchProfile

SESSION_KEY = "church_id"

# URL namespaces a signed-in person with no church may still open: their
# own account, their notifications, and the platform's church pages, such
# as registering a church (decision 0014).
OPEN_WITHOUT_CHURCH = {
    "accounts",
    "notifications",
    "admin",
    "churches",
    "public_requests",
}


def current_church_for(request):
    """The church this request works in (decision 0014), or None.

    A signed-in person works in the church kept in their session while
    they still have an active Membership there (a superuser may work in
    any church); otherwise in their oldest membership's church. Visitors
    who aren't signed in, and people with no membership, have none.
    """
    user = request.user
    if not user.is_authenticated:
        return None
    member_of = ChurchProfile.objects.filter(
        memberships__user=user, memberships__is_active=True
    )
    may_choose = ChurchProfile.objects.all() if user.is_superuser else member_of
    chosen = request.session.get(SESSION_KEY)
    church = may_choose.filter(pk=chosen).first() if chosen else None
    if chosen and church is None:
        # The membership was removed or deactivated since it was chosen.
        del request.session[SESSION_KEY]
    return church or member_of.order_by("memberships__created_at", "pk").first()


class CurrentChurchMiddleware:
    """Puts the Current Church on ``request.church`` and
    ``request.user.current_church`` (which permissions follow), and uses
    its time zone. A signed-in person with no church sees only their own
    account pages and a page saying so."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.church = current_church_for(request)
        if request.user.is_authenticated:
            request.user.current_church = request.church
        if request.church is not None:
            timezone.activate(zoneinfo.ZoneInfo(request.church.time_zone))
        try:
            return self.get_response(request)
        finally:
            timezone.deactivate()

    def process_view(self, request, view_func, view_args, view_kwargs):
        if request.church is not None or not request.user.is_authenticated:
            return None
        match = request.resolver_match
        if match and OPEN_WITHOUT_CHURCH.intersection(match.namespaces):
            return None
        return render(request, "church/no_church.html")
