"""Occasions on the public pages (Phase 9B, decision 0014).

- **Request this service** (``/churches/<slug>/request/<type>/``): anyone
  signed in may request an Occasion Type a public church offers publicly;
  someone outside the church only while it accepts requests from outside.
  A visitor signs in first and comes back to the form.
- **My requests** (``/churches/my-requests/``): a person's own requests at
  every church, with Withdraw while one is Pending.

The church, the type and the Occasions Module are checked before anything
else, so a hidden church, a type not offered publicly, or a switched-off
Module is 404 to everyone. Times are in the requested church's time zone.
"""

from django import forms
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.http import require_POST
from django.views.generic import FormView, ListView

from apps.accounts.models import Membership
from apps.church.homepage import Section
from apps.church.modules import is_enabled
from apps.church.views import public_churches
from apps.worship.forms import moment_field
from apps.worship.scheduling import church_time_zone

from . import rules
from .models import OccasionRequest, OccasionType


def public_types(church):
    """The Occasion Types ``church`` offers on its homepage: active, offered
    publicly, and only while Occasions is switched on."""
    if not is_enabled("occasions", church):
        return OccasionType.objects.none()
    return OccasionType.objects.for_church(church).filter(
        is_active=True, offered_publicly=True
    )


def is_member(user, church):
    return (
        user.is_authenticated
        and Membership.objects.filter(user=user, church=church, is_active=True).exists()
    )


def may_request(user, church):
    """Whether ``user`` may request from ``church``'s homepage: its own
    people always; anyone else only while it accepts requests from outside."""
    return church.accept_outside_requests or is_member(user, church)


def homepage_section(church, request):
    """The homepage's offered occasions, each with its Request button."""
    offered = list(public_types(church))
    if not offered:
        return None
    return Section(
        template="occasions/includes/homepage_offered.html",
        context={
            "offered": offered,
            "may_request": may_request(request.user, church),
            "signed_in": request.user.is_authenticated,
        },
        order=20,
    )


class PublicRequestForm(forms.ModelForm):
    starts_at = moment_field(label="Preferred date and start time")

    class Meta:
        model = OccasionRequest
        fields = ["starts_at", "occasion_for", "note"]
        widgets = {"note": forms.Textarea(attrs={"rows": 3})}


class PublicRequestView(LoginRequiredMixin, FormView):
    template_name = "occasions/public_request.html"
    form_class = PublicRequestForm

    def dispatch(self, request, *args, **kwargs):
        # Before signing in: what doesn't exist publicly is 404 to everyone.
        self.public_church = get_object_or_404(public_churches(), slug=kwargs["slug"])
        self.occasion_type = get_object_or_404(
            public_types(self.public_church), pk=kwargs["type_pk"]
        )
        with timezone.override(church_time_zone(self.public_church)):
            return super().dispatch(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        return self.refuse_outsider() or super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        return self.refuse_outsider() or super().post(request, *args, **kwargs)

    def refuse_outsider(self):
        if may_request(self.request.user, self.public_church):
            return None
        return render(
            self.request,
            "occasions/public_request_closed.html",
            {"public_church": self.public_church},
            status=403,
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            public_church=self.public_church, occasion_type=self.occasion_type
        )
        return context

    def form_valid(self, form):
        data = form.cleaned_data
        try:
            rules.request_occasion(
                self.request.user,
                self.occasion_type,
                data["starts_at"],
                data["occasion_for"],
                data["note"],
            )
        except rules.OccasionRefused as refusal:
            form.add_error("starts_at", str(refusal))
            return self.form_invalid(form)
        messages.success(
            self.request,
            f"Your request was sent to {self.public_church.name}. You'll get a "
            "notification when they decide.",
        )
        return redirect("public_requests:my_requests")


class MyRequestsEverywhereView(LoginRequiredMixin, ListView):
    """The person's own Occasion Requests at every church."""

    template_name = "occasions/my_requests_everywhere.html"
    paginate_by = 25

    def get_queryset(self):
        return (
            OccasionRequest.objects.filter(requester=self.request.user)
            .select_related("church", "occasion_type")
            .order_by("-created_at", "-pk")
        )


@method_decorator(require_POST, name="dispatch")
class WithdrawEverywhereView(LoginRequiredMixin, View):
    """Withdraw one's own Pending request, at whichever church."""

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
        return redirect("public_requests:my_requests")
