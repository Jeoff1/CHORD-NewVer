from django.conf import settings
from django.shortcuts import redirect
from django.urls import reverse

# Pages a person who must change their password may still open.
ALLOWED = ("accounts:password_change", "accounts:logout")


class PasswordChangeRequiredMiddleware:
    """Sends a signed-in person whose account still has its Temporary
    Password to Change password, from every other page (Phase 9A, A4)."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        if user is not None and user.is_authenticated and user.must_change_password:
            allowed = {reverse(name) for name in ALLOWED}
            # Static files and public media (the church logo) still load.
            prefixes = tuple(
                "/" + url.strip("/") + "/"
                for url in (settings.STATIC_URL, settings.MEDIA_URL)
                if url and url.strip("/")
            )
            if request.path not in allowed and not request.path.startswith(prefixes):
                return redirect("accounts:password_change")
        return self.get_response(request)
