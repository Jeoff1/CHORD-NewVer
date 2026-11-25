"""Shared pieces for the worship views."""

from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.urls import reverse
from django.utils.functional import cached_property

from apps.church.modules import ModuleRequiredMixin
from apps.church.scoping import get_in_church

from ..models import WorshipService

# Settings pages of the Worship Module: (label, permission, URL name). Labels
# may contain "{sermon}", filled in with the church's word.
SETTINGS_PAGES = [
    ("Service templates", "worship.view_servicetemplate", "worship:template_list"),
    ("{sermon} series", "worship.view_sermonseries", "worship:series_list"),
    ("Seasons", "worship.view_season", "worship:seasons_list"),
    ("Theme tags", "songs.view_themetag", "songs:theme_tags_list"),
    ("Trusted artists", "songs.view_trustedartist", "songs:trusted_artists_list"),
    ("Worship check", "songs.change_worshipchecksettings", "songs:check_settings"),
    (
        "Suggestion settings",
        "worship.change_suggestionsettings",
        "worship:suggestion_settings",
    ),
]
# Their groups in the Settings hub's Worship category (Phase 9A, A7).
SETTINGS_GROUPS = {
    "worship:template_list": "Services",
    "worship:series_list": "Services",
    "worship:seasons_list": "Services",
    "songs:theme_tags_list": "Songs and suggestions",
    "songs:trusted_artists_list": "Songs and suggestions",
    "songs:check_settings": "Songs and suggestions",
    "worship:suggestion_settings": "Songs and suggestions",
}


class WorshipMixin(ModuleRequiredMixin, LoginRequiredMixin, PermissionRequiredMixin):
    module = "worship"


class ServiceMixin(WorshipMixin):
    """Gives the service named in the URL as ``self.service``."""

    @cached_property
    def service(self):
        return get_in_church(
            WorshipService.objects.select_related("template"),
            self.request.church,
            public_id=self.kwargs["public_id"],
        )

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
