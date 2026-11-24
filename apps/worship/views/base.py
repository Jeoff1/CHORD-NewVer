"""Shared pieces for the worship views."""

from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils.functional import cached_property

from apps.church.modules import ModuleRequiredMixin

from ..models import WorshipService
from ..occasions import can_see_occasions

# Settings pages of the Worship Module: (label, permission, URL name). Labels
# may contain "{sermon}", filled in with the church's word.
SETTINGS_PAGES = [
    ("Service templates", "worship.view_servicetemplate", "worship:template_list"),
    ("{sermon} series", "worship.view_sermonseries", "worship:series_list"),
    ("Theme tags", "songs.view_themetag", "songs:theme_tags_list"),
    ("Trusted artists", "songs.view_trustedartist", "songs:trusted_artists_list"),
    ("Worship check", "songs.change_worshipchecksettings", "songs:check_settings"),
    ("Seasons", "worship.view_season", "worship:seasons_list"),
    (
        "Suggestion settings",
        "worship.change_suggestionsettings",
        "worship:suggestion_settings",
    ),
]


class WorshipMixin(ModuleRequiredMixin, LoginRequiredMixin, PermissionRequiredMixin):
    module = "worship"


class ServiceMixin(WorshipMixin):
    """Gives the service named in the URL as ``self.service``."""

    @cached_property
    def service(self):
        service = get_object_or_404(
            WorshipService.objects.select_related("template"),
            public_id=self.kwargs["public_id"],
        )
        # An occasion's pages are hidden from people who see only "Booked"
        # (Phase 9A, A5).
        if service.is_occasion and not can_see_occasions(self.request.user):
            raise Http404
        return service

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["service"] = self.service
        return context

    def service_url(self):
        return service_url(self.service)


def service_url(service):
    return reverse("worship:service", kwargs={"public_id": service.public_id})


def settings_nav(request):
    """Tabs linking the Worship settings pages the user may open."""
    sermon = request.church.label_set.get("sermon")
    return [
        (label.format(sermon=sermon), reverse(url_name))
        for label, permission, url_name in SETTINGS_PAGES
        if request.user.has_perm(permission)
    ]


def can_plan(user):
    """Whether the user plans services: they see the notes behind a theme."""
    return user.has_perm("worship.change_theme") or user.has_perm(
        "worship.change_lineup"
    )
