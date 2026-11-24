from django.apps import AppConfig


class AuditConfig(AppConfig):
    """The shared audit trail: who changed what, and when."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.audit"
    verbose_name = "Audit Trail"

    def ready(self):
        from django.contrib.auth import signals

        from apps.core.settings_menu import SettingsPage, register

        from . import signins

        register(
            SettingsPage(
                "people", "Audit log", "audit:log", "audit.view_auditevent", order=30
            )
        )

        signals.user_logged_in.connect(
            signins.on_signed_in, dispatch_uid="audit_signed_in"
        )
        signals.user_logged_out.connect(
            signins.on_signed_out, dispatch_uid="audit_signed_out"
        )
        signals.user_login_failed.connect(
            signins.on_failed, dispatch_uid="audit_sign_in_failed"
        )
