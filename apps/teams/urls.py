from django.urls import path

from apps.core.setting_lists import SettingList, setting_list_urls

from . import views
from .models import TeamPart

app_name = "teams"

PARTS_LIST = SettingList(
    model=TeamPart,
    url_prefix="parts",
    title="Team parts",
    item_name="Team part",
    intro="The voices and instruments people can take at a service. People "
    "choose theirs in their Team Profile; only they can be assigned to it.",
    module="teams",
    nav=views.teams_nav,
)

urlpatterns = [
    path("", views.MyScheduleView.as_view(), name="my_schedule"),
    path("my-parts/", views.MyPartsView.as_view(), name="my_parts"),
    path("blackouts/new/", views.BlackoutCreateView.as_view(), name="blackout_create"),
    path(
        "blackouts/<int:pk>/remove/",
        views.BlackoutDeleteView.as_view(),
        name="blackout_delete",
    ),
    path(
        "assignments/<uuid:public_id>/reply/",
        views.ReplyView.as_view(),
        name="reply",
    ),
    path(
        "services/<uuid:public_id>/assign/",
        views.AssignView.as_view(),
        name="assign",
    ),
    path(
        "services/<uuid:public_id>/assignments/<uuid:assignment_id>/remove/",
        views.RemoveAssignmentView.as_view(),
        name="assignment_remove",
    ),
    path(
        "assignments/<uuid:public_id>/swap/",
        views.SwapRequestView.as_view(),
        name="swap_request",
    ),
    path(
        "swaps/<uuid:public_id>/<slug:action>/",
        views.SwapActionView.as_view(),
        name="swap_action",
    ),
    path("notifications/", views.NotificationListView.as_view(), name="notifications"),
    path(
        "notifications/<int:pk>/open/",
        views.NotificationOpenView.as_view(),
        name="notification_open",
    ),
    path(
        "notifications/read/",
        views.NotificationsReadView.as_view(),
        name="notifications_read",
    ),
    path("roster/", views.RosterView.as_view(), name="roster"),
    path("roster/<int:pk>/", views.PersonPartsView.as_view(), name="person_parts"),
    *setting_list_urls(PARTS_LIST, route_prefix="settings/"),
]
