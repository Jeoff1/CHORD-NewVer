from django.urls import path
from django.views.generic import RedirectView

from . import views

app_name = "church"

urlpatterns = [
    path("switch/<slug:slug>/", views.SwitchChurchView.as_view(), name="switch"),
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
    # The church page's editor and its camera buttons (Church CMS, 28 Nov 2026).
    path(
        "profile/edit/",
        views.ChurchProfileEditView.as_view(),
        name="profile_edit",
    ),
    path(
        "setup/<slug:section>/",
        views.ProfileSectionView.as_view(wizard=True),
        name="setup",
    ),
]
