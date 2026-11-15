from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.contrib.contenttypes.models import ContentType

from apps.core.views import FilteredListView

from .models import AuditEvent


class AuditLogView(LoginRequiredMixin, PermissionRequiredMixin, FilteredListView):
    permission_required = "audit.view_auditevent"
    model = AuditEvent
    paginate_by = 50
    search_fields = ("object_repr", "actor__username")

    def get_type_filter(self):
        return self.request.GET.get("type", "")

    def get_queryset(self):
        queryset = super().get_queryset().select_related("actor", "content_type")
        type_filter = self.get_type_filter()
        if type_filter.isdigit():
            queryset = queryset.filter(content_type_id=int(type_filter))
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        used = AuditEvent.objects.values_list("content_type", flat=True).distinct()
        context["type_choices"] = sorted(
            ContentType.objects.filter(pk__in=used),
            key=lambda ct: ct.name,
        )
        context["type_filter"] = self.get_type_filter()
        return context
