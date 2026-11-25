"""Pages about the platform's churches, under /churches/ (Phase 9B).

A church's own address is /churches/<slug>/; the words used here are in
``models.RESERVED_SLUGS``, so no church can take them.
"""

from django.urls import path

from . import views

app_name = "churches"

urlpatterns = [
    path("register/", views.RegisterChurchView.as_view(), name="register"),
]
