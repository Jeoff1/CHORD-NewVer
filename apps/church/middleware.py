import zoneinfo

from django.utils import timezone

from .models import ChurchProfile


class ChurchProfileMiddleware:
    """Puts the Church Profile on ``request.church`` and uses its time zone."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.church = ChurchProfile.load()
        timezone.activate(zoneinfo.ZoneInfo(request.church.time_zone))
        try:
            return self.get_response(request)
        finally:
            timezone.deactivate()
