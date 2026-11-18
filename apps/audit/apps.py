from django.apps import AppConfig


class AuditConfig(AppConfig):
    """The shared audit trail: who changed what, and when."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.audit"
    verbose_name = "Audit Trail"
