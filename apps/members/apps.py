from django.apps import AppConfig


class MembersConfig(AppConfig):
    """Members: people and households in the church."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.members"
    verbose_name = "Members"
