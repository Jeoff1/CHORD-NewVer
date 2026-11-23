from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import FormView, ListView

from apps.church.modules import ModuleRequiredMixin
from apps.core.views import FormPageMixin

from . import services
from .forms import AnnouncementForm
from .models import Announcement

LIST = reverse_lazy("announcements:list")


class AnnouncementsMixin(ModuleRequiredMixin, LoginRequiredMixin):
    module = "announcements"


class AnnouncementListView(AnnouncementsMixin, ListView):
    template_name = "announcements/list.html"
    paginate_by = 25

    def get_queryset(self):
        return services.visible_to(self.request.user)


class AnnouncementCreateView(
    AnnouncementsMixin, PermissionRequiredMixin, FormPageMixin, FormView
):
    permission_required = "announcements.add_announcement"
    form_class = AnnouncementForm
    page_title = "Post an announcement"
    submit_label = "Post"
    success_url = LIST
    cancel_url = LIST

    def form_valid(self, form):
        data = form.cleaned_data
        try:
            services.post(
                self.request.user,
                title=data["title"],
                body=data["body"],
                audience=data["audience"],
                service=data.get("service"),
            )
        except services.AnnouncementRefused as refused:
            form.add_error(None, str(refused))
            return self.form_invalid(form)
        messages.success(self.request, "The announcement was posted.")
        return super().form_valid(form)


class ArchiveView(AnnouncementsMixin, View):
    """Only the author archives; anyone else gets a 404."""

    def post(self, request, public_id):
        announcement = get_object_or_404(
            Announcement, public_id=public_id, author=request.user
        )
        services.archive(announcement, request.user)
        messages.success(request, f"“{announcement.title}” was archived.")
        return redirect(LIST)
