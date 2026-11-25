"""Occasions on the platform's public pages, under /churches/ (Phase 9B).

Included before ``apps.church.public_urls``, whose ``<slug>/`` would
otherwise catch "my-requests" (a reserved word no church can take)."""

from django.urls import path

from . import public_views

app_name = "public_requests"

urlpatterns = [
    path(
        "my-requests/",
        public_views.MyRequestsEverywhereView.as_view(),
        name="my_requests",
    ),
    path(
        "my-requests/<uuid:public_id>/withdraw/",
        public_views.WithdrawEverywhereView.as_view(),
        name="withdraw",
    ),
    path(
        "<slug:slug>/request/<int:type_pk>/",
        public_views.PublicRequestView.as_view(),
        name="request",
    ),
]
