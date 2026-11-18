from django.urls import path

from apps.core.setting_lists import SettingList, setting_list_urls

from .models import SermonSeries
from .views import schedule
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
    *setting_list_urls(SERIES_LIST, route_prefix="settings/"),
]
