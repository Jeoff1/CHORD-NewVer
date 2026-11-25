"""Reports pages: song usage (with CSV export) and attendance."""

from django import forms
from django.http import Http404, HttpResponse
from django.urls import reverse
from django.views.generic import TemplateView

from .. import reports
from ..models import SuggestionSettings
from .base import WorshipMixin

USAGE = "worship.view_song_usage"
ATTENDANCE = "worship.record_attendance"


class PeriodForm(forms.Form):
    start = forms.DateField(
        label="From", required=False, widget=forms.DateInput(attrs={"type": "date"})
    )
    end = forms.DateField(
        label="To", required=False, widget=forms.DateInput(attrs={"type": "date"})
    )

    def period(self):
        if not self.is_valid():
            return None, None
        return self.cleaned_data["start"], self.cleaned_data["end"]


def report_links(user):
    """(label, URL) for each report ``user`` may open. The attendance report
    exists only once a headcount has been recorded."""
    links = []
    if user.has_perm(USAGE):
        links.append(("Song usage", reverse("worship:report_song_usage")))
    if user.has_perm(ATTENDANCE) and reports.has_attendance(user.current_church):
        links.append(("Attendance", reverse("worship:report_attendance")))
    return links


class ReportsView(WorshipMixin, TemplateView):
    """The reports the user may open."""

    template_name = "worship/reports.html"

    def has_permission(self):
        user = self.request.user
        return user.has_perm(USAGE) or user.has_perm(ATTENDANCE)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["reports"] = report_links(self.request.user)
        return context


class SongUsageReportView(WorshipMixin, TemplateView):
    permission_required = USAGE
    template_name = "worship/report_song_usage.html"

    def get(self, request, *args, **kwargs):
        form = PeriodForm(request.GET or None)
        start, end = form.period()
        window = SuggestionSettings.load(request.church).repeat_window_weeks
        rows = reports.song_usage(request.church, start, end, window_weeks=window)
        if request.GET.get("format") == "csv":
            response = HttpResponse(
                reports.song_usage_csv(rows, window), content_type="text/csv"
            )
            response["Content-Disposition"] = 'attachment; filename="song-usage.csv"'
            return response
        context = self.get_context_data(
            form=form,
            rows=rows,
            window_weeks=window,
            sung_again=sum(1 for row in rows if row.sung_again),
            links=report_links(request.user),
            query=request.GET.urlencode(),
        )
        return self.render_to_response(context)


class AttendanceReportView(WorshipMixin, TemplateView):
    permission_required = ATTENDANCE
    template_name = "worship/report_attendance.html"

    def get(self, request, *args, **kwargs):
        if not reports.has_attendance(request.church):
            # A church that never records a headcount has no such report.
            raise Http404("No headcount has been recorded yet.")
        form = PeriodForm(request.GET or None)
        services = reports.attendance(request.church, *form.period())
        counts = [service.attendance for service in services]
        context = self.get_context_data(
            form=form,
            services=services,
            average=round(sum(counts) / len(counts)) if counts else None,
            links=report_links(request.user),
        )
        return self.render_to_response(context)
