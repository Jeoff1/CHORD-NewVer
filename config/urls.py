from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from apps.church.views import DashboardView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("apps.accounts.urls")),
    path("audit/", include("apps.audit.urls")),
    path("church/", include("apps.church.urls")),
    path("members/", include("apps.members.urls")),
    path("worship/songs/", include("apps.songs.urls")),
    path("worship/", include("apps.worship.urls")),
    path("teams/", include("apps.teams.urls")),
    path("announcements/", include("apps.announcements.urls")),
    path("", DashboardView.as_view(), name="home"),
]

if settings.DEBUG:
    # Uploaded files such as the church logo; a web server serves them in
    # production.
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
