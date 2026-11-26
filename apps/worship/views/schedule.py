"""The worship schedule: services, their themes, attendance and templates."""

import datetime

from django.contrib import messages
from django.db import transaction
from django.db.models import Count, Q
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.utils import timezone
from django.views import View
from django.views.generic import (
    CreateView,
    DetailView,
    FormView,
    ListView,
    TemplateView,
    UpdateView,
)

from apps.audit.models import AuditEvent
from apps.audit.services import diff, record_change, snapshot
from apps.church.modules import is_enabled
from apps.church.scoping import ChurchFormKwargsMixin, ChurchScopedMixin
from apps.core.views import FilteredListView, FormPageMixin
from apps.teams.views import service_team_context

from .. import bookings, scheduling
from ..forms import (
    AttendanceForm,
    ScheduleAheadForm,
    ServiceForm,
    SlotFormSet,
    TemplateForm,
    ThemeForm,
)
from ..models import Lineup, ServiceTemplate, Theme, WorshipService
from ..planning import planning_context
from .base import ServiceMixin, WorshipMixin, can_plan, service_url
from .lineups import lineup_context
from .suggestions import can_suggest

# --- Services ----------------------------------------------------------------


class ServiceListView(ChurchScopedMixin, WorshipMixin, FilteredListView):
    permission_required = "worship.view_worshipservice"
    model = WorshipService
    template_name = "worship/service_list.html"
    search_fields = ("name", "theme__title", "theme__scripture")
    WHEN = {"upcoming": "Upcoming", "past": "Past"}

    def get_when(self):
        when = self.request.GET.get("when", "upcoming")
        return when if when in self.WHEN else "upcoming"

    def get_queryset(self):
        queryset = super().get_queryset().select_related("template", "theme", "lineup")
        if show_team(self.request.user):
            # The Team column: who accepted, of the people assigned (Pending
            # or Accepted). Phase 9A, A7.
            queryset = queryset.annotate(
                team_assigned=Count(
                    "assignments",
                    filter=Q(assignments__reply__in=("pending", "accepted")),
                    distinct=True,
                ),
                team_accepted=Count(
                    "assignments",
                    filter=Q(assignments__reply="accepted"),
                    distinct=True,
                ),
            )
        if self.get_when() == "past":
            return queryset.past().order_by("-starts_at")
        return queryset.upcoming()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        context.update(
            when=self.get_when(),
            when_choices=self.WHEN.items(),
            can_schedule_ahead=can_schedule_ahead(self.request),
            show_lineup=user.has_perm("worship.view_lineup"),
            show_team=show_team(user),
            can_plan=can_plan(user),
        )
        return context


def can_schedule_ahead(request):
    """Whether "Schedule weeks ahead" has anything to offer this person."""
    return (
        request.user.has_perm("worship.add_worshipservice")
        and ServiceTemplate.objects.for_church(request.church)
        .active()
        .filter(weekday__isnull=False, start_time__isnull=False)
        .exists()
    )


def show_team(user):
    """The schedule's Team column: while Teams is on, for people who may
    see each service's team."""
    return is_enabled("teams", user.current_church) and user.has_perm(
        "teams.view_assignment"
    )


class CalendarView(WorshipMixin, TemplateView):
    permission_required = "worship.view_worshipservice"
    template_name = "worship/calendar.html"

    def get_month(self):
        today = timezone.localdate()
        try:
            year, month = self.request.GET.get("month", "").split("-")
            first = datetime.date(int(year), int(month), 1)
        except ValueError:
            first = today.replace(day=1)
        return first.year, first.month

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        year, month = self.get_month()
        church = self.request.church
        start, end = scheduling.month_bounds(year, month, church)
        services = (
            WorshipService.objects.for_church(church)
            .filter(starts_at__gte=start, starts_at__lt=end)
            .select_related("theme", "template")
        )
        context.update(
            month=datetime.date(year, month, 1),
            weeks=scheduling.month_grid(
                year,
                month,
                services,
                church,
                bookings=bookings.calendar_bookings(
                    start, end, church, self.request.user
                ),
            ),
            previous_month="{}-{:02d}".format(*scheduling.shift_month(year, month, -1)),
            next_month="{}-{:02d}".format(*scheduling.shift_month(year, month, 1)),
            weekday_names=["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"],
            can_schedule_ahead=can_schedule_ahead(self.request),
        )
        return context


class ServiceDetailView(ServiceMixin, DetailView):
    permission_required = "worship.view_worshipservice"
    template_name = "worship/service_detail.html"

    def get_object(self, queryset=None):
        return self.service

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        service = self.service
        user = self.request.user
        context.update(
            theme=service.posted_theme,
            can_plan=can_plan(user),
            attendance_form=AttendanceForm(instance=service),
            # Suggestions live on the Song Lineup page since Phase 9C.
            can_suggest=can_suggest(user),
        )
        # The service's team, while Teams is on (Phase 8).
        context.update(service_team_context(service, user))
        # The lineup itself: team members get it only once it is confirmed.
        lineup = Lineup.objects.filter(service=service).first()
        if user.has_perm("worship.view_lineup"):
            context.update(lineup_context(lineup, user))
        # The step bar and the next-step panel, for people who plan
        # (Phase 9C).
        if context["can_plan"]:
            context.update(planning_context(service, user))
        return context


class ServiceFormMixin(
    ChurchScopedMixin, ChurchFormKwargsMixin, WorshipMixin, FormPageMixin
):
    model = WorshipService
    form_class = ServiceForm

    def worship_service_label(self):
        return self.request.church.label_set.get("worship_service").lower()

    def get_success_url(self):
        return service_url(self.object)


class ServiceCreateView(ServiceFormMixin, CreateView):
    permission_required = "worship.add_worshipservice"
    cancel_url = reverse_lazy("worship:home")

    def get_page_title(self):
        return f"Add {self.worship_service_label()}"

    def form_valid(self, form):
        response = super().form_valid(form)
        record_change(
            self.request.user,
            self.object,
            AuditEvent.Action.CREATED,
            diff({}, snapshot(self.object, scheduling.SERVICE_AUDIT_FIELDS)),
        )
        messages.success(self.request, f"{self.object} was added.")
        return response


class ServiceUpdateView(ServiceFormMixin, UpdateView):
    permission_required = "worship.change_worshipservice"
    slug_field = "public_id"
    slug_url_kwarg = "public_id"

    def get_page_title(self):
        return f"Edit {self.object}"

    def get_cancel_url(self):
        return self.get_success_url()

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        self.before = snapshot(self.object, scheduling.SERVICE_AUDIT_FIELDS)
        return kwargs

    def form_valid(self, form):
        response = super().form_valid(form)
        record_change(
            self.request.user,
            self.object,
            AuditEvent.Action.CHANGED,
            diff(self.before, snapshot(self.object, scheduling.SERVICE_AUDIT_FIELDS)),
        )
        messages.success(self.request, f"{self.object} was saved.")
        return response


class ThemeView(ServiceMixin, FormPageMixin, UpdateView):
    """Post a service's theme, or edit the one already posted."""

    permission_required = "worship.change_theme"
    form_class = ThemeForm
    submit_label = "Save theme"

    def get_object(self, queryset=None):
        return self.service.posted_theme or Theme(service=self.service)

    def get_page_title(self):
        verb = "Edit the" if self.object.pk else "Post the"
        return f"{verb} theme for {self.service}"

    def get_cancel_url(self):
        return self.service_url()

    def get_success_url(self):
        return self.service_url()

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["labels"] = self.request.church.label_set
        kwargs["church"] = self.request.church
        self.is_new = not self.object.pk
        self.before = (
            {} if self.is_new else snapshot(self.object, scheduling.THEME_AUDIT_FIELDS)
        )
        return kwargs

    def form_valid(self, form):
        if self.is_new:
            form.instance.posted_by = self.request.user
        response = super().form_valid(form)
        record_change(
            self.request.user,
            self.object,
            AuditEvent.Action.CREATED if self.is_new else AuditEvent.Action.CHANGED,
            diff(self.before, snapshot(self.object, scheduling.THEME_AUDIT_FIELDS)),
        )
        messages.success(self.request, "The theme was saved.")
        return response


class AttendanceView(ServiceMixin, View):
    permission_required = "worship.record_attendance"

    def post(self, request, public_id):
        service = self.service
        before = snapshot(service, scheduling.SERVICE_AUDIT_FIELDS)
        form = AttendanceForm(request.POST, instance=service)
        if form.is_valid():
            form.save()
            record_change(
                request.user,
                service,
                AuditEvent.Action.CHANGED,
                diff(before, snapshot(service, scheduling.SERVICE_AUDIT_FIELDS)),
            )
            messages.success(request, "The headcount was saved.")
        else:
            messages.error(request, "Enter the headcount as a whole number.")
        return redirect(self.service_url())


class ScheduleAheadView(ChurchFormKwargsMixin, WorshipMixin, FormPageMixin, FormView):
    permission_required = "worship.add_worshipservice"
    form_class = ScheduleAheadForm
    page_title = "Schedule weeks ahead"
    intro = (
        "Adds the chosen template's service on its usual day and time for the "
        "coming weeks. Dates that already have it are left as they are."
    )
    submit_label = "Schedule"
    success_url = reverse_lazy("worship:home")
    cancel_url = reverse_lazy("worship:home")

    def form_valid(self, form):
        created = scheduling.schedule_ahead(
            form.cleaned_data["template"], form.cleaned_data["weeks"], self.request.user
        )
        count = len(created)
        if count:
            noun = "service was" if count == 1 else "services were"
            messages.success(self.request, f"{count} {noun} added to the schedule.")
        else:
            messages.info(self.request, "Those weeks were already scheduled.")
        return super().form_valid(form)


# --- Service templates -------------------------------------------------------


class TemplateListView(WorshipMixin, ListView):
    permission_required = "worship.view_servicetemplate"
    template_name = "worship/template_list.html"

    def get_queryset(self):
        return ServiceTemplate.objects.for_church(self.request.church).prefetch_related(
            "slots"
        )


class TemplateFormMixin(ChurchScopedMixin, ChurchFormKwargsMixin, WorshipMixin):
    model = ServiceTemplate
    form_class = TemplateForm
    template_name = "worship/template_form.html"
    success_url = reverse_lazy("worship:template_list")

    def get_slot_formset(self):
        kwargs = {"instance": self.object, "prefix": "slots"}
        if self.request.method == "POST":
            return SlotFormSet(self.request.POST, **kwargs)
        return SlotFormSet(**kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.setdefault("slots", self.get_slot_formset())
        context.update(
            page_title=self.get_page_title(),
            cancel_url=self.success_url,
        )
        return context

    def post(self, request, *args, **kwargs):
        self.object = self.get_object() if self.is_edit else None
        before = (
            snapshot(self.object, scheduling.TEMPLATE_AUDIT_FIELDS)
            if self.is_edit
            else {}
        )
        form = self.get_form()
        slots = self.get_slot_formset()
        if not (form.is_valid() and slots.is_valid()):
            return self.render_to_response(
                self.get_context_data(form=form, slots=slots)
            )
        with transaction.atomic():
            self.object = form.save()
            slots.instance = self.object
            slots.save()
        template = ServiceTemplate.objects.prefetch_related("slots").get(
            pk=self.object.pk
        )
        record_change(
            request.user,
            template,
            AuditEvent.Action.CHANGED if self.is_edit else AuditEvent.Action.CREATED,
            diff(before, snapshot(template, scheduling.TEMPLATE_AUDIT_FIELDS)),
        )
        messages.success(request, f"{template.name} was saved.")
        return redirect(self.success_url)


class TemplateCreateView(TemplateFormMixin, CreateView):
    permission_required = "worship.add_servicetemplate"
    is_edit = False

    def get_page_title(self):
        return "Add service template"


class TemplateUpdateView(TemplateFormMixin, UpdateView):
    permission_required = "worship.change_servicetemplate"
    is_edit = True

    def get_page_title(self):
        return f"Edit service template: {self.object}"
