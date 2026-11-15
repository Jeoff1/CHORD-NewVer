from django.urls import path, reverse

from apps.core.setting_lists import SettingList, setting_list_urls

from . import views
from .models import MemberField, MembershipStatus, RelationshipType

app_name = "members"


def settings_nav(request):
    """Tabs linking the Members settings lists the user may see."""
    links = [
        ("Membership statuses", "members.view_membershipstatus", "status_list"),
        ("Household roles", "members.view_relationshiptype", "relationship_list"),
        ("Custom fields", "members.view_memberfield", "field_list"),
    ]
    return [
        (label, reverse(f"members:{name}"))
        for label, perm, name in links
        if request.user.has_perm(perm)
    ]


STATUS_LIST = SettingList(
    model=MembershipStatus,
    url_prefix="status",
    title="Membership statuses",
    item_name="Status",
    intro="The statuses a person in the directory can have. Statuses that "
    "count as active are counted as active members.",
    module="members",
    fields=["name", "description", "counts_as_active", "sort_order", "is_active"],
    columns=[
        ("Name", "name"),
        ("Description", "description"),
        ("Counts as active", "counts_as_active"),
        ("Order", "sort_order"),
        ("Active", "is_active"),
    ],
    nav=settings_nav,
)
RELATIONSHIP_LIST = SettingList(
    model=RelationshipType,
    url_prefix="relationship",
    title="Household roles",
    item_name="Household role",
    intro="The roles people can have in a household.",
    module="members",
    nav=settings_nav,
)
FIELD_LIST = SettingList(
    model=MemberField,
    url_prefix="field",
    title="Custom fields",
    item_name="Custom field",
    intro="Extra information your church keeps about each person. Private "
    "fields are shown only to people allowed to see private details.",
    module="members",
    fields=[
        "label",
        "field_type",
        "choices",
        "help_text",
        "required",
        "is_private",
        "sort_order",
        "is_active",
    ],
    columns=[
        ("Label", "label"),
        ("Type", "field_type"),
        ("Required", "required"),
        ("Private", "is_private"),
        ("Order", "sort_order"),
        ("Active", "is_active"),
    ],
    nav=settings_nav,
)

urlpatterns = [
    path("", views.MemberListView.as_view(), name="list"),
    path("new/", views.MemberCreateView.as_view(), name="create"),
    path("export/", views.MemberExportView.as_view(), name="export"),
    path("me/", views.MyRecordView.as_view(), name="me"),
    path("me/photo/", views.MyFileView.as_view(), {"kind": "photo"}, name="my_photo"),
    path(
        "me/files/<slug:key>/",
        views.MyFileView.as_view(),
        {"kind": "file"},
        name="my_file",
    ),
    path("import/", views.ImportUploadView.as_view(), name="import"),
    path("import/preview/", views.ImportPreviewView.as_view(), name="import_preview"),
    path(
        "import/problems/", views.ImportProblemsView.as_view(), name="import_problems"
    ),
    path(
        "import/template/", views.ImportTemplateView.as_view(), name="import_template"
    ),
    path("import/cancel/", views.ImportCancelView.as_view(), name="import_cancel"),
    path("households/", views.HouseholdListView.as_view(), name="household_list"),
    path(
        "households/new/",
        views.HouseholdCreateView.as_view(),
        name="household_create",
    ),
    path(
        "households/<uuid:public_id>/",
        views.HouseholdDetailView.as_view(),
        name="household_detail",
    ),
    path(
        "households/<uuid:public_id>/edit/",
        views.HouseholdUpdateView.as_view(),
        name="household_update",
    ),
    *setting_list_urls(STATUS_LIST, route_prefix="settings/"),
    *setting_list_urls(RELATIONSHIP_LIST, route_prefix="settings/"),
    *setting_list_urls(FIELD_LIST, route_prefix="settings/"),
    path("<uuid:public_id>/", views.MemberDetailView.as_view(), name="detail"),
    path("<uuid:public_id>/edit/", views.MemberUpdateView.as_view(), name="update"),
    path(
        "<uuid:public_id>/archive/", views.MemberArchiveView.as_view(), name="archive"
    ),
    path("<uuid:public_id>/photo/", views.MemberPhotoView.as_view(), name="photo"),
    path(
        "<uuid:public_id>/files/<slug:key>/",
        views.MemberFileView.as_view(),
        name="file",
    ),
]
