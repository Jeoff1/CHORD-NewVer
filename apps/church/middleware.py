import zoneinfo

from django.utils import timezone

from .models import ChurchProfile

SESSION_KEY = "church_id"


def current_church_for(request):
    """The church this request works in (decision 0014).

    A signed-in person works in the church kept in their session, if they
    still have an active Membership there (a superuser may work in any
    church); otherwise in their first membership's church. Others, and
    people with no membership, see the first church until Phase 9B, slice c
    gives them their own pages.
    """
    user = request.user
    if user.is_authenticated:
        churches = ChurchProfile.objects.all()
        if not user.is_superuser:
            churches = churches.filter(
                memberships__user=user, memberships__is_active=True
            )
        chosen = request.session.get(SESSION_KEY)
        church = churches.filter(pk=chosen).first() if chosen else None
        if church is None and not user.is_superuser:
            church = churches.order_by("memberships__created_at", "pk").first()
        if church is not None:
            return church
    return ChurchProfile.load()


class CurrentChurchMiddleware:
    """Puts the Current Church on ``request.church`` and
    ``request.user.current_church`` (which permissions follow), and uses
    its time zone."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.church = current_church_for(request)
        if request.user.is_authenticated:
            request.user.current_church = request.church
        timezone.activate(zoneinfo.ZoneInfo(request.church.time_zone))
        try:
            return self.get_response(request)
        finally:
            timezone.deactivate()
