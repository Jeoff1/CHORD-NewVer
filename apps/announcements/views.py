from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import FormView, ListView

from apps.church.modules import ModuleRequiredMixin
from apps.church.scoping import ChurchFormKwargsMixin, get_in_church
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
        return services.visible_to(self.request.user, self.request.church)


class AnnouncementCreateView(
    ChurchFormKwargsMixin,
    AnnouncementsMixin,
    PermissionRequiredMixin,
    FormPageMixin,
    FormView,
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
                self.request.church,
                title=data["title"],
                body=data["body"],
                audience=data["audience"],
                service=data.get("service"),
                visibility=(
                    Announcement.Visibility.PUBLIC
                    if data.get("public")
                    else Announcement.Visibility.INTERNAL
                ),
            )
        except services.AnnouncementRefused as refused:
            form.add_error(None, str(refused))
            return self.form_invalid(form)
        messages.success(self.request, "The announcement was posted.")
        return super().form_valid(form)


class ArchiveView(AnnouncementsMixin, View):
    """Only the author archives; anyone else gets a 404."""

    def post(self, request, public_id):
        announcement = get_in_church(
            Announcement.objects.filter(author=request.user),
            request.church,
            public_id=public_id,
        )
        services.archive(announcement, request.user)
        messages.success(request, f"“{announcement.title}” was archived.")
        return redirect(LIST)
