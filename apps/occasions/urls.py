from django.urls import path

from apps.core.setting_lists import SettingList, setting_list_urls

from . import views
from .models import OccasionType

app_name = "occasions"

TYPES_LIST = SettingList(
    model=OccasionType,
    url_prefix="types",
    title="Occasion types",
    item_name="Occasion type",
    intro="The special services the church holds, such as a wedding, a baptism "
    "or a funeral, each with how long it usually takes. People may request the "
    "active ones.",
    module="occasions",
    fields=["name", "description", "length_minutes", "sort_order", "is_active"],
    columns=[
        ("Name", "name"),
        ("Usual length", lambda item: f"{item.length_minutes} min"),
        ("Description", "description"),
        ("Active", "is_active"),
    ],
    nav=views.occasions_nav,
)

urlpatterns = [
    path("", views.HomeView.as_view(), name="home"),
    path("list/", views.OccasionListView.as_view(), name="list"),
    path("new/", views.OccasionCreateView.as_view(), name="create"),
    path("<uuid:public_id>/", views.OccasionDetailView.as_view(), name="detail"),
    path("<uuid:public_id>/edit/", views.OccasionUpdateView.as_view(), name="update"),
    path("requests/", views.RequestListView.as_view(), name="requests"),
    path("requests/new/", views.RequestCreateView.as_view(), name="request"),
    path("requests/mine/", views.MyRequestsView.as_view(), name="my_requests"),
    path(
        "requests/<uuid:public_id>/",
        views.DecideView.as_view(),
        name="decide",
    ),
    path(
        "requests/<uuid:public_id>/withdraw/",
        views.WithdrawView.as_view(),
        name="withdraw",
    ),
    *setting_list_urls(TYPES_LIST, route_prefix="settings/"),
]
