from django.urls import path
from django.views.generic import RedirectView

from . import views

app_name = "church"

urlpatterns = [
    path(
        "settings/",
        RedirectView.as_view(pattern_name="church:settings"),
        {"section": "details"},
        name="settings_home",
    ),
    path(
        "settings/<slug:section>/",
        views.ProfileSectionView.as_view(),
        name="settings",
    ),
    path(
        "setup/<slug:section>/",
        views.ProfileSectionView.as_view(wizard=True),
        name="setup",
    ),
]
