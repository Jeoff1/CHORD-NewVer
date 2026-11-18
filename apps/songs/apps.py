from django.apps import AppConfig
from django.db.models.signals import post_save


def recheck_after_trusted_artist_change(sender, **kwargs):
    """A change to the Trusted Artists list changes Worship Checks."""
    from .analysis import apply_check_rules

    apply_check_rules()


class SongsConfig(AppConfig):
    """The song pool: songs found on Spotify, their lyrics and analysis.

    Part of the Worship Module (apps/church/modules.py).
    """

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.songs"
    verbose_name = "Songs"

    def ready(self):
        from .models import TrustedArtist

        post_save.connect(
            recheck_after_trusted_artist_change,
            sender=TrustedArtist,
            dispatch_uid="songs.recheck_after_trusted_artist_change",
        )
