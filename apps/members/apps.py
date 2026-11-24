from django.apps import AppConfig


class MembersConfig(AppConfig):
    """Members: people and households in the church."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.members"
    verbose_name = "Members"

    def ready(self):
        from apps.core.settings_menu import SettingsPage, register

        register(
            *(
                SettingsPage(
                    "members", label, f"members:{name}", perm, "members", order=order
                )
                for order, (label, name, perm) in enumerate(
                    (
                        (
                            "Membership statuses",
                            "status_list",
                            "members.view_membershipstatus",
                        ),
                        (
                            "Household roles",
                            "relationship_list",
                            "members.view_relationshiptype",
                        ),
                        ("Custom fields", "field_list", "members.view_memberfield"),
                    )
                )
            )
        )
