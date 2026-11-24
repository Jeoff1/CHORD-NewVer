"""Occasion pages (Phase 9A, A5; decision 0013): the list of Occasions,
adding and editing one, requests, and the church's occasion types."""

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.functional import cached_property
from django.views import View
from django.views.generic import CreateView, DetailView, FormView, UpdateView

from apps.audit.services import snapshot
from apps.church.modules import ModuleRequiredMixin
from apps.core.views import FilteredListView, FormPageMixin

from . import rules
from .forms import ApproveForm, DeclineForm, OccasionForm, OccasionRequestForm
from .models import Occasion, OccasionRequest

MY_REQUESTS = reverse_lazy("occasions:my_requests")
REQUESTS = reverse_lazy("occasions:requests")
Status = OccasionRequest.Status


def occasions_nav(request):
    """Tabs linking the Occasions pages the user may open."""
    user = request.user
    links = []
    if user.has_perm(rules.VIEW):
        links.append(("Occasions", reverse("occasions:list")))
    if user.has_perm(rules.APPROVE):
        links.append(("Requests", reverse("occasions:requests")))
    if user.has_perm(rules.REQUEST):
        links.append(("My requests", reverse("occasions:my_requests")))
    if user.has_perm("occasions.view_occasiontype"):
        links.append(("Settings", reverse("occasions:types_list")))
    return links


class OccasionsMixin(ModuleRequiredMixin, LoginRequiredMixin, PermissionRequiredMixin):
    module = "occasions"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["nav_links"] = occasions_nav(self.request)
        return context


class HomeView(ModuleRequiredMixin, LoginRequiredMixin, View):
    """The Module's page: the Occasions for people who see them, otherwise
    the person's own requests."""

    module = "occasions"

    def get(self, request):
        if request.user.has_perm(rules.VIEW):
            return redirect("occasions:list")
        if request.user.has_perm(rules.REQUEST):
            return redirect("occasions:my_requests")
        raise PermissionDenied


# --- Occasions ------------------------------------------------------------------


class OccasionListView(OccasionsMixin, FilteredListView):
    permission_required = rules.VIEW
    model = Occasion
    template_name = "occasions/list.html"
    search_fields = ("occasion_for", "venue", "occasion_type__name")
    WHEN = {"upcoming": "Upcoming", "past": "Past"}

    def get_when(self):
        when = self.request.GET.get("when", "upcoming")
        return when if when in self.WHEN else "upcoming"

    def get_queryset(self):
        queryset = super().get_queryset().select_related("occasion_type", "officiant")
        today = timezone.localtime().replace(hour=0, minute=0, second=0, microsecond=0)
        if self.get_when() == "past":
            return queryset.filter(starts_at__lt=today).order_by("-starts_at")
        return queryset.filter(starts_at__gte=today)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(when=self.get_when(), when_choices=self.WHEN.items())
        return context


class OccasionMixin(OccasionsMixin):
    @cached_property
    def occasion(self):
        return get_object_or_404(
            Occasion.objects.select_related("occasion_type", "officiant"),
            public_id=self.kwargs["public_id"],
        )


class OccasionDetailView(OccasionMixin, DetailView):
    permission_required = rules.VIEW
    template_name = "occasions/detail.html"

    def get_object(self, queryset=None):
        return self.occasion

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["request_record"] = getattr(self.occasion, "request", None)
        return context


class OccasionFormMixin(OccasionsMixin, FormPageMixin):
    model = Occasion
    form_class = OccasionForm

    def form_valid(self, form):
        occasion = form.save(commit=False)
        try:
            rules.save_occasion(occasion, self.request.user, before=self.before)
        except rules.OccasionRefused as refusal:
            form.add_error("starts_at", str(refusal))
            return self.form_invalid(form)
        self.object = occasion
        messages.success(self.request, f"{occasion} was saved.")
        return redirect("occasions:detail", public_id=occasion.public_id)


class OccasionCreateView(OccasionFormMixin, CreateView):
    permission_required = "occasions.add_occasion"
    page_title = "Add an occasion"
    intro = (
        "A special service such as a wedding, a baptism or a funeral. It books "
        "its time on the calendar; a time that overlaps a worship service or "
        "another occasion is refused."
    )
    cancel_url = reverse_lazy("occasions:list")
    before = None


class OccasionUpdateView(OccasionFormMixin, UpdateView):
    permission_required = "occasions.change_occasion"
    slug_field = "public_id"
    slug_url_kwarg = "public_id"

    def get_page_title(self):
        return f"Edit {self.object}"

    def get_cancel_url(self):
        return reverse("occasions:detail", kwargs={"public_id": self.object.public_id})

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        self.before = snapshot(self.object, rules.OCCASION_AUDIT_FIELDS)
        return kwargs


# --- Requests -------------------------------------------------------------------


class RequestCreateView(OccasionsMixin, FormPageMixin, FormView):
    permission_required = rules.REQUEST
    form_class = OccasionRequestForm
    page_title = "Request an occasion"
    intro = (
        "Ask the church for a special service, such as a wedding, a baptism or a "
        "funeral. It stays Pending until someone approves or declines it, and "
        "you get a notification either way."
    )
    submit_label = "Send request"
    cancel_url = MY_REQUESTS

    def get(self, request, *args, **kwargs):
        if not rules.requestable_types().exists():
            messages.info(request, "The church hasn't set up any occasions yet.")
            return redirect(MY_REQUESTS)
        return super().get(request, *args, **kwargs)

    def form_valid(self, form):
        data = form.cleaned_data
        try:
            rules.request_occasion(
                self.request.user,
                data["occasion_type"],
                data["starts_at"],
                data["occasion_for"],
                data["note"],
            )
        except rules.OccasionRefused as refusal:
            form.add_error("starts_at", str(refusal))
            return self.form_invalid(form)
        messages.success(self.request, "Your request was sent.")
        return redirect(MY_REQUESTS)


class MyRequestsView(OccasionsMixin, FilteredListView):
    permission_required = rules.REQUEST
    model = OccasionRequest
    template_name = "occasions/my_requests.html"

    def get_queryset(self):
        return OccasionRequest.objects.filter(
            requester=self.request.user
        ).select_related("occasion_type", "occasion")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["can_request"] = rules.requestable_types().exists()
        return context


class WithdrawView(OccasionsMixin, View):
    permission_required = rules.REQUEST

    def post(self, request, public_id):
        record = get_object_or_404(
            OccasionRequest, public_id=public_id, requester=request.user
        )
        try:
            rules.withdraw(record, request.user)
        except rules.OccasionRefused as refusal:
            messages.error(request, str(refusal))
        else:
            messages.success(request, "Your request was withdrawn.")
        return redirect(MY_REQUESTS)


class RequestListView(OccasionsMixin, FilteredListView):
    """Pending requests, soonest first, then the latest decided ones."""

    permission_required = rules.APPROVE
    model = OccasionRequest
    template_name = "occasions/requests.html"
    DECIDED_SHOWN = 50

    def get_queryset(self):
        return (
            OccasionRequest.objects.filter(status=Status.PENDING)
            .select_related("occasion_type", "requester")
            .order_by("starts_at", "pk")
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            decided=OccasionRequest.objects.exclude(status=Status.PENDING)
            .select_related("occasion_type", "requester", "decided_by", "occasion")
            .order_by("-updated_at")[: self.DECIDED_SHOWN],
            decided_shown=self.DECIDED_SHOWN,
        )
        return context


class DecideView(OccasionsMixin, View):
    """One request: approve it (which books the Occasion) or decline it."""

    permission_required = rules.APPROVE
    template_name = "occasions/decide.html"

    def get_record(self):
        return get_object_or_404(
            OccasionRequest.objects.select_related(
                "occasion_type", "requester", "occasion"
            ),
            public_id=self.kwargs["public_id"],
        )

    def render_page(self, record, approve_form=None, decline_form=None, error=""):
        clash = ""
        if record.is_pending:
            found = rules.clashes(record.starts_at, record.ends_at)
            clash = rules.clash_message(found, self.request.user) if found else ""
        return render(
            self.request,
            self.template_name,
            {
                "record": record,
                "approve_form": approve_form
                or ApproveForm(initial={"starts_at": record.starts_at}),
                "decline_form": decline_form or DeclineForm(),
                "clash": clash,
                "error": error,
                "nav_links": occasions_nav(self.request),
            },
        )

    def get(self, request, public_id):
        return self.render_page(self.get_record())

    def post(self, request, public_id):
        record = self.get_record()
        if request.POST.get("action") == "decline":
            return self.decline(record)
        return self.approve(record)

    def approve(self, record):
        form = ApproveForm(self.request.POST)
        if not form.is_valid():
            return self.render_page(record, approve_form=form)
        try:
            occasion = rules.approve(record, self.request.user, **form.cleaned_data)
        except rules.OccasionRefused as refusal:
            return self.render_page(record, approve_form=form, error=str(refusal))
        messages.success(self.request, f"Approved. {occasion} is booked.")
        return redirect("occasions:detail", public_id=occasion.public_id)

    def decline(self, record):
        form = DeclineForm(self.request.POST)
        if not form.is_valid():
            return self.render_page(record, decline_form=form)
        try:
            rules.decline(record, self.request.user, form.cleaned_data["reason"])
        except rules.OccasionRefused as refusal:
            return self.render_page(record, decline_form=form, error=str(refusal))
        messages.success(self.request, "The request was declined.")
        return redirect(REQUESTS)
