from django.urls import path

from apps.core.setting_lists import SettingList, setting_list_urls

from .forms import SeasonForm
from .models import Season, SermonSeries
from .views import lineups, reports, schedule, suggestions
from .views.base import settings_nav

app_name = "worship"

SERIES_LIST = SettingList(
    model=SermonSeries,
    url_prefix="series",
    title=lambda request: f"{request.church.label_set.get('sermon')} series",
    item_name="Series",
    intro="Groups of services whose themes belong together. Choose a series "
    "when posting a service's theme.",
    module="worship",
    nav=settings_nav,
)


def _season_dates(season):
    dates = f"{season.starts_on:%b} {season.starts_on.day} to "
    dates += f"{season.ends_on:%b} {season.ends_on.day}"
    if season.repeats_yearly:
        return f"{dates}, every year"
    return f"{dates}, {season.ends_on.year}"


SEASONS_LIST = SettingList(
    model=Season,
    url_prefix="seasons",
    title="Seasons",
    item_name="Season",
    intro="Times of the church's year, each with the theme tags that suit it. "
    "Songs with those tags rank higher for services in the season. With no "
    "seasons, season fit plays no part in suggestions.",
    module="worship",
    fields=[
        "name",
        "starts_on",
        "ends_on",
        "repeats_yearly",
        "tags",
        "description",
        "sort_order",
        "is_active",
    ],
    form_class=SeasonForm,
    columns=[
        ("Name", "name"),
        ("Dates", _season_dates),
        ("Theme tags", lambda season: ", ".join(t.name for t in season.tags.all())),
        ("Active", "is_active"),
    ],
    nav=settings_nav,
)

urlpatterns = [
    # The schedule
    path("", schedule.ServiceListView.as_view(), name="home"),
    path("calendar/", schedule.CalendarView.as_view(), name="calendar"),
    path("services/new/", schedule.ServiceCreateView.as_view(), name="service_create"),
    path(
        "services/schedule-ahead/",
        schedule.ScheduleAheadView.as_view(),
        name="schedule_ahead",
    ),
    path(
        "services/<uuid:public_id>/",
        schedule.ServiceDetailView.as_view(),
        name="service",
    ),
    path(
        "services/<uuid:public_id>/edit/",
        schedule.ServiceUpdateView.as_view(),
        name="service_update",
    ),
    path(
        "services/<uuid:public_id>/theme/",
        schedule.ThemeView.as_view(),
        name="theme",
    ),
    path(
        "services/<uuid:public_id>/attendance/",
        schedule.AttendanceView.as_view(),
        name="attendance",
    ),
    # Song suggestions
    path(
        "services/<uuid:public_id>/suggest/",
        suggestions.SuggestView.as_view(),
        name="suggest",
    ),
    path(
        "services/<uuid:public_id>/suggestions/",
        suggestions.SuggestionPanelView.as_view(),
        name="suggestions",
    ),
    path(
        "services/<uuid:public_id>/suggestions/<int:pk>/feel/",
        suggestions.SuggestionFeelView.as_view(),
        name="suggestion_feel",
    ),
    path(
        "services/<uuid:public_id>/suggestions/<int:pk>/not-worship/",
        suggestions.NotWorshipView.as_view(),
        name="suggestion_not_worship",
    ),
    # The lineup
    path(
        "services/<uuid:public_id>/lineup/",
        lineups.LineupView.as_view(),
        name="lineup",
    ),
    path(
        "services/<uuid:public_id>/lineup/new/",
        lineups.LineupCreateView.as_view(),
        name="lineup_create",
    ),
    path(
        "services/<uuid:public_id>/lineup/add/",
        lineups.AddSongView.as_view(),
        name="lineup_add",
    ),
    path(
        "services/<uuid:public_id>/lineup/regenerate/",
        lineups.RegenerateView.as_view(),
        name="lineup_regenerate",
    ),
    path(
        "services/<uuid:public_id>/lineup/confirm/",
        lineups.ConfirmView.as_view(),
        name="lineup_confirm",
    ),
    path(
        "services/<uuid:public_id>/lineup/reopen/",
        lineups.ReopenView.as_view(),
        name="lineup_reopen",
    ),
    path(
        "services/<uuid:public_id>/lineup/send-back/",
        lineups.SendBackView.as_view(),
        name="lineup_send_back",
    ),
    path(
        "services/<uuid:public_id>/lineup/songs/<int:pk>/swap/",
        lineups.SwapView.as_view(),
        name="lineup_swap",
    ),
    path(
        "services/<uuid:public_id>/lineup/songs/<int:pk>/edit/",
        lineups.ItemDetailsView.as_view(),
        name="lineup_item",
    ),
    path(
        "services/<uuid:public_id>/lineup/songs/<int:pk>/<slug:action>/",
        lineups.ItemActionView.as_view(),
        name="lineup_item_action",
    ),
    # Reports
    path("reports/", reports.ReportsView.as_view(), name="reports"),
    path(
        "reports/song-usage/",
        reports.SongUsageReportView.as_view(),
        name="report_song_usage",
    ),
    path(
        "reports/attendance/",
        reports.AttendanceReportView.as_view(),
        name="report_attendance",
    ),
    # Settings
    path(
        "settings/templates/",
        schedule.TemplateListView.as_view(),
        name="template_list",
    ),
    path(
        "settings/templates/new/",
        schedule.TemplateCreateView.as_view(),
        name="template_create",
    ),
    path(
        "settings/templates/<int:pk>/",
        schedule.TemplateUpdateView.as_view(),
        name="template_update",
    ),
    path(
        "settings/suggestions/",
        suggestions.SuggestionSettingsView.as_view(),
        name="suggestion_settings",
    ),
    *setting_list_urls(SERIES_LIST, route_prefix="settings/"),
    *setting_list_urls(SEASONS_LIST, route_prefix="settings/"),
]
