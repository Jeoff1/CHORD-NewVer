from django.apps import AppConfig


class SongsConfig(AppConfig):
    """The song pool: songs found on Spotify, their lyrics and analysis.

    Part of the Worship Module (apps/church/modules.py).
    """

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.songs"
    verbose_name = "Songs"
