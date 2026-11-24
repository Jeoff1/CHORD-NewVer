"""Occasion pages (Phase 9A, A5; decision 0012): request an occasion,
follow your own requests, and approve or decline them."""

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.views import View
from django.views.generic import FormView, ListView

from apps.core.views import FormPageMixin

from .. import occasions
from ..forms import ApproveOccasionForm, DeclineOccasionForm, OccasionRequestForm
from ..models import OccasionRequest
from .base import WorshipMixin, service_url

MY_OCCASIONS = reverse_lazy("worship:my_occasions")
Status = OccasionRequest.Status


class OccasionRequestCreateView(WorshipMixin, FormPageMixin, FormView):
    permission_required = occasions.REQUEST
    form_class = OccasionRequestForm
    page_title = "Request an occasion"
    intro = (
        "Ask the church for a special service, such as a wedding or a funeral. "
        "It stays Pending until someone approves or declines it, and you get a "
        "notification either way."
    )
    submit_label = "Send request"
    cancel_url = MY_OCCASIONS

    def get(self, request, *args, **kwargs):
        if not occasions.occasion_templates().exists():
            messages.info(request, "The church hasn't set up any occasions yet.")
            return redirect(MY_OCCASIONS)
        return super().get(request, *args, **kwargs)

    def form_valid(self, form):
        data = form.cleaned_data
        try:
            occasions.request_occasion(
                self.request.user,
                data["template"],
                data["starts_at"],
                data["occasion_for"],
                data["note"],
            )
        except occasions.OccasionRefused as refusal:
            form.add_error("starts_at", str(refusal))
            return self.form_invalid(form)
        messages.success(self.request, "Your request was sent.")
        return redirect(MY_OCCASIONS)


class MyOccasionsView(WorshipMixin, ListView):
    """The person's own requests, newest first."""

    permission_required = occasions.REQUEST
    template_name = "worship/my_occasions.html"
    paginate_by = 25

    def get_queryset(self):
        return OccasionRequest.objects.filter(
            requester=self.request.user
        ).select_related("template", "service")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["can_request"] = occasions.occasion_templates().exists()
        return context


class OccasionWithdrawView(WorshipMixin, View):
    permission_required = occasions.REQUEST

    def post(self, request, public_id):
        occasion = get_object_or_404(
            OccasionRequest, public_id=public_id, requester=request.user
        )
        try:
            occasions.withdraw(occasion, request.user)
        except occasions.OccasionRefused as refusal:
            messages.error(request, str(refusal))
        else:
            messages.success(request, "Your request was withdrawn.")
        return redirect(MY_OCCASIONS)


class OccasionRequestListView(WorshipMixin, ListView):
    """Every request: the Pending ones first, soonest first, then the
    latest decided ones."""

    permission_required = occasions.APPROVE
    template_name = "worship/occasion_requests.html"
    DECIDED_SHOWN = 50

    def get_queryset(self):
        return (
            OccasionRequest.objects.filter(status=Status.PENDING)
            .select_related("template", "requester")
            .order_by("starts_at", "pk")
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            decided=OccasionRequest.objects.exclude(status=Status.PENDING)
            .select_related("template", "requester", "decided_by", "service")
            .order_by("-updated_at")[: self.DECIDED_SHOWN],
            decided_shown=self.DECIDED_SHOWN,
        )
        return context


class OccasionDecideView(WorshipMixin, View):
    """One request: approve it (which creates the service) or decline it."""

    permission_required = occasions.APPROVE
    template_name = "worship/occasion_decide.html"

    def get_occasion(self):
        return get_object_or_404(
            OccasionRequest.objects.select_related("template", "requester", "service"),
            public_id=self.kwargs["public_id"],
        )

    def render_page(self, occasion, approve_form=None, decline_form=None, error=""):
        clash = ""
        if occasion.is_pending:
            found = occasions.clashes(
                occasion.starts_at,
                occasions.ends_at(occasion.template, occasion.starts_at),
            )
            clash = occasions.clash_message(found, self.request.user) if found else ""
        return render(
            self.request,
            self.template_name,
            {
                "occasion": occasion,
                "approve_form": approve_form
                or ApproveOccasionForm(initial={"starts_at": occasion.starts_at}),
                "decline_form": decline_form or DeclineOccasionForm(),
                "clash": clash,
                "error": error,
                "ends_at": occasions.ends_at(occasion.template, occasion.starts_at),
            },
        )

    def get(self, request, public_id):
        return self.render_page(self.get_occasion())

    def post(self, request, public_id):
        occasion = self.get_occasion()
        if request.POST.get("action") == "decline":
            return self.decline(occasion)
        return self.approve(occasion)

    def approve(self, occasion):
        form = ApproveOccasionForm(self.request.POST)
        if not form.is_valid():
            return self.render_page(occasion, approve_form=form)
        try:
            service = occasions.approve(
                occasion, self.request.user, **form.cleaned_data
            )
        except occasions.OccasionRefused as refusal:
            return self.render_page(occasion, approve_form=form, error=str(refusal))
        messages.success(self.request, f"Approved. {service} is on the schedule.")
        return redirect(service_url(service))

    def decline(self, occasion):
        form = DeclineOccasionForm(self.request.POST)
        if not form.is_valid():
            return self.render_page(occasion, decline_form=form)
        try:
            occasions.decline(occasion, self.request.user, form.cleaned_data["reason"])
        except occasions.OccasionRefused as refusal:
            return self.render_page(occasion, decline_form=form, error=str(refusal))
        messages.success(self.request, "The request was declined.")
        return redirect(reverse("worship:occasion_requests"))
