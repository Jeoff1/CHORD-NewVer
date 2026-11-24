"""The signed-in person's own Notifications. Anyone signed in may open them,
whichever Modules are switched on."""

from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.utils.http import url_has_allowed_host_and_scheme
from django.views import View
from django.views.generic import ListView

from . import services
from .models import Notification

NOTIFICATIONS = reverse_lazy("notifications:list")


class NotificationListView(LoginRequiredMixin, ListView):
    template_name = "notifications/list.html"
    paginate_by = 25

    def get_queryset(self):
        return Notification.objects.filter(recipient=self.request.user)


class NotificationOpenView(LoginRequiredMixin, View):
    """Mark one of your own Notifications read and go where it points."""

    def post(self, request, pk):
        notification = get_object_or_404(Notification, pk=pk, recipient=request.user)
        services.mark_read(notification)
        url = notification.url
        if url and url_has_allowed_host_and_scheme(url, allowed_hosts=None):
            return redirect(url)
        return redirect(NOTIFICATIONS)


class NotificationsReadView(LoginRequiredMixin, View):
    def post(self, request):
        services.mark_all_read(request.user)
        return redirect(NOTIFICATIONS)
