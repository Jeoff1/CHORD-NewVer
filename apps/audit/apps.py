from django.apps import AppConfig


class AuditConfig(AppConfig):
    """The shared audit trail: who changed what, and when."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.audit"
    verbose_name = "Audit Trail"

    def ready(self):
        from django.contrib.auth import signals

        from . import signins

        # The Audit log is a page of its own, under Members in the sidebar
        # (apps/church/navigation.py), not a settings page.
        signals.user_logged_in.connect(
            signins.on_signed_in, dispatch_uid="audit_signed_in"
        )
        signals.user_logged_out.connect(
            signins.on_signed_out, dispatch_uid="audit_signed_out"
        )
        signals.user_login_failed.connect(
            signins.on_failed, dispatch_uid="audit_sign_in_failed"
        )
