from django.urls import path

from apps.core.setting_lists import SettingList, setting_list_urls

from . import views
from .models import ThemeTag, TrustedArtist

app_name = "songs"

THEME_TAGS = SettingList(
    model=ThemeTag,
    url_prefix="theme_tags",
    title="Theme tags",
    item_name="Theme tag",
    intro="The worship themes songs are tagged with. The analysis suggests "
    "tags from each song's lyrics, and suggestions for a service match its "
    "theme against them.",
    module="worship",
    fields=["name", "keywords", "description", "sort_order", "is_active"],
    columns=[("Name", "name"), ("Keywords", "keywords"), ("Active", "is_active")],
)
TRUSTED_ARTISTS = SettingList(
    model=TrustedArtist,
    url_prefix="trusted_artists",
    title="Trusted artists",
    item_name="Trusted artist",
    intro="Artists whose songs the church trusts as worship songs. Their "
    "songs pass the worship check more easily. Write each name as Spotify "
    "shows it.",
    module="worship",
    fields=["name", "description", "is_active"],
    columns=[("Name", "name"), ("Description", "description"), ("Active", "is_active")],
)

urlpatterns = [
    path("", views.SongListView.as_view(), name="list"),
    path("find/", views.SpotifySearchView.as_view(), name="spotify_search"),
    path("find/add/", views.SpotifyAddView.as_view(), name="spotify_add"),
    # Each person's own Spotify account, and playback in their browser
    path("spotify/", views.SpotifyAccountView.as_view(), name="spotify_account"),
    path(
        "spotify/connect/", views.SpotifyConnectView.as_view(), name="spotify_connect"
    ),
    path(
        "spotify/callback/",
        views.SpotifyCallbackView.as_view(),
        name="spotify_callback",
    ),
    path(
        "spotify/disconnect/",
        views.SpotifyDisconnectView.as_view(),
        name="spotify_disconnect",
    ),
    path("spotify/church/", views.ChurchSpotifyView.as_view(), name="church_spotify"),
    path(
        "spotify/church/connect/",
        views.ChurchSpotifyConnectView.as_view(),
        name="church_spotify_connect",
    ),
    path(
        "spotify/church/disconnect/",
        views.ChurchSpotifyDisconnectView.as_view(),
        name="church_spotify_disconnect",
    ),
    path(
        "spotify/player-token/",
        views.SpotifyPlayerTokenView.as_view(),
        name="spotify_player_token",
    ),
    path("<uuid:public_id>/", views.SongDetailView.as_view(), name="detail"),
    path("<uuid:public_id>/edit/", views.SongUpdateView.as_view(), name="update"),
    path(
        "<uuid:public_id>/check-again/",
        views.SongCheckAgainView.as_view(),
        name="check_again",
    ),
    path(
        "<uuid:public_id>/chords/",
        views.ChordSheetFormView.as_view(),
        name="chordsheet",
    ),
    path(
        "chords/<int:pk>/approve/",
        views.SheetApproveView.as_view(),
        name="chordsheet_approve",
    ),
    path(
        "chords/<int:pk>/discard/",
        views.SheetDiscardView.as_view(),
        name="chordsheet_discard",
    ),
    path(
        "settings/worship-check/",
        views.WorshipCheckSettingsView.as_view(),
        name="check_settings",
    ),
    *setting_list_urls(THEME_TAGS, route_prefix="settings/"),
    *setting_list_urls(TRUSTED_ARTISTS, route_prefix="settings/"),
]
