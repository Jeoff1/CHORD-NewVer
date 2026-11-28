"""Occasions on the public pages (Phase 9B, decision 0014).

- **Request this service** (``/churches/<slug>/request/<type>/``): anyone
  signed in may request an Occasion Type a public church offers publicly;
  someone outside the church only while it accepts requests from outside.
  There, a visitor without an account fills in the form and makes their
  account in a pop-up, proving their email with a code (28 Nov 2026); at a
  church that takes requests from its own people only, they sign in first.
- **My requests** (``/churches/my-requests/``): a person's own requests at
  every church, with Withdraw while one is Pending.

The church, the type and the Occasions Module are checked before anything
else, so a hidden church, a type not offered publicly, or a switched-off
Module is 404 to everyone. Times are in the requested church's time zone.
"""

import datetime

from django import forms
from django.contrib import messages
from django.contrib.auth import authenticate, login
from django.contrib.auth.hashers import make_password
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import redirect_to_login
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.http import require_POST
from django.views.generic import FormView, ListView

from apps.accounts import verification
from apps.accounts.forms import EmailCodeForm, PasswordOnlyForm, VisitorAccountForm
from apps.accounts.models import Membership
from apps.accounts.visitors import create_account
from apps.church.homepage import Section
from apps.church.middleware import SESSION_KEY as CHURCH_SESSION_KEY
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
        slot="tab",
        label="Available services",
        count=len(offered),
        icon="calendar",
    )


class PublicRequestForm(forms.ModelForm):
    starts_at = moment_field(label="Preferred date and start time")

    class Meta:
        model = OccasionRequest
        fields = ["starts_at", "occasion_for", "note"]
        widgets = {"note": forms.Textarea(attrs={"rows": 3})}


PENDING_KEY = "pending_service_request"


class PublicRequestView(FormView):
    """Request a service from a church's public page.

    Signed in, the form sends the request as before. A visitor without an
    account at a church that takes requests from outside fills in the same
    form; pressing Send keeps it in their session and opens a pop-up
    (28 Nov 2026) that asks their name, email and a password, emails a
    6-digit code, and on the right code makes their account (a Church Member
    of that church), signs them in and sends the request. An email that is
    an account's already signs in right there instead. A visitor at a church
    that takes requests from its own people only signs in first, as before.
    """

    template_name = "occasions/public_request.html"
    form_class = PublicRequestForm

    def dispatch(self, request, *args, **kwargs):
        # What doesn't exist publicly is 404 to everyone, signed in or not.
        self.public_church = get_object_or_404(public_churches(), slug=kwargs["slug"])
        self.occasion_type = get_object_or_404(
            public_types(self.public_church), pk=kwargs["type_pk"]
        )
        if (
            not request.user.is_authenticated
            and not self.public_church.accept_outside_requests
        ):
            return redirect_to_login(request.get_full_path())
        with timezone.override(church_time_zone(self.public_church)):
            return super().dispatch(request, *args, **kwargs)

    # --- Signed in -------------------------------------------------------------

    def get(self, request, *args, **kwargs):
        return self.refuse_outsider() or super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.visitor_post()
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
        return self.send(
            data["starts_at"], data["occasion_for"], data["note"], form=form
        )

    def send(self, starts_at, occasion_for, note, *, form=None):
        """Send the request as the signed-in person."""
        try:
            rules.request_occasion(
                self.request.user, self.occasion_type, starts_at, occasion_for, note
            )
        except rules.OccasionRefused as refusal:
            if form is None:
                # A request kept for a visitor: show it as they filled it in.
                local = timezone.localtime(starts_at)
                form = self.get_form_class()(
                    data={
                        "starts_at": f"{local:%Y-%m-%d %H:%M}",
                        "occasion_for": occasion_for,
                        "note": note,
                    }
                )
                form.is_valid()
            form.add_error("starts_at", str(refusal))
            return self.form_invalid(form)
        messages.success(
            self.request,
            f"Your request was sent to {self.public_church.name}. You'll get a "
            "notification when they decide.",
        )
        return redirect("public_requests:my_requests")

    # --- A visitor without an account ------------------------------------------

    def pending(self):
        """The visitor's request waiting for their account, if it is for this
        church and service."""
        pending = self.request.session.get(PENDING_KEY) or {}
        if (
            pending.get("church") == self.public_church.pk
            and pending.get("type") == self.occasion_type.pk
        ):
            return pending
        return None

    def keep(self, pending):
        self.request.session[PENDING_KEY] = pending

    def visitor_post(self):
        step = self.request.POST.get("step", "")
        if step == "":
            return self.visitor_request()
        pending = self.pending()
        if pending is None:
            # The session ended or is for another service: start again.
            messages.info(self.request, "Fill in your request again, then send it.")
            return redirect(self.request.path)
        handler = {
            "account": self.visitor_account,
            "signin": self.visitor_signin,
            "code": self.visitor_code,
            "resend": self.visitor_resend,
            "change": self.visitor_change,
        }.get(step)
        if handler is None:
            return redirect(self.request.path)
        return handler(pending)

    def visitor_request(self):
        form = self.get_form()
        if not form.is_valid():
            return self.form_invalid(form)
        data = form.cleaned_data
        if data["starts_at"] <= timezone.now():
            form.add_error(
                "starts_at", "Choose a date and time that hasn't passed yet."
            )
            return self.form_invalid(form)
        self.keep(
            {
                "church": self.public_church.pk,
                "type": self.occasion_type.pk,
                "starts_at": data["starts_at"].isoformat(),
                "occasion_for": data["occasion_for"],
                "note": data["note"],
            }
        )
        return self.show_step("account", VisitorAccountForm())

    def show_step(self, step, step_form=None, *, notice="", status=200):
        """The page, with the request form as the visitor filled it in and
        the pop-up open at ``step``."""
        pending = self.pending() or {}
        form = self.get_form_class()(
            initial={
                "starts_at": pending.get("starts_at", ""),
                "occasion_for": pending.get("occasion_for", ""),
                "note": pending.get("note", ""),
            }
        )
        context = self.get_context_data(form=form)
        context.update(
            signup_step=step,
            signup_form=step_form,
            signup_email=pending.get("email", ""),
            signup_notice=notice,
            resend_wait=verification.seconds_until_resend(pending.get("email", ""))
            if pending.get("email")
            else 0,
        )
        return self.render_to_response(context, status=status)

    def visitor_account(self, pending):
        form = VisitorAccountForm(self.request.POST)
        if not form.is_valid():
            return self.show_step("account", form)
        data = form.cleaned_data
        pending["email"] = data["email"]
        self.keep(pending)
        if form.has_account:
            return self.show_step(
                "signin",
                PasswordOnlyForm(),
                notice="You already have a CHORD account with this email. Sign in "
                "to send your request.",
            )
        try:
            verification.start(
                data["email"],
                {
                    "email": data["email"],
                    "first_name": data["first_name"],
                    "last_name": data["last_name"],
                    "password": make_password(data["password"]),
                },
            )
        except verification.CodeRefused as refusal:
            return self.show_step("code", EmailCodeForm(), notice=str(refusal))
        return self.show_step("code", EmailCodeForm())

    def visitor_signin(self, pending):
        form = PasswordOnlyForm(self.request.POST)
        user = None
        if form.is_valid():
            user = authenticate(
                self.request,
                username=pending.get("email", ""),
                password=form.cleaned_data["password"],
            )
        if user is None:
            if form.is_valid():
                form.add_error("password", "That password isn't right.")
            return self.show_step("signin", form)
        login(self.request, user)
        return self.send_pending(pending)

    def visitor_code(self, pending):
        form = EmailCodeForm(self.request.POST)
        if not form.is_valid():
            return self.show_step("code", form)
        try:
            account = verification.check(pending["email"], form.cleaned_data["code"])
            user = create_account(account, self.public_church)
        except verification.CodeRefused as refusal:
            form.add_error("code", str(refusal))
            return self.show_step("code", form)
        login(self.request, user, backend="apps.accounts.backends.ChurchRoleBackend")
        # They work in the church they just joined.
        self.request.session[CHURCH_SESSION_KEY] = self.public_church.pk
        messages.success(
            self.request,
            f"Your CHORD account is ready, and you're part of {self.public_church.name}.",
        )
        return self.send_pending(pending)

    def visitor_resend(self, pending):
        try:
            verification.resend(pending.get("email", ""))
        except verification.CodeRefused as refusal:
            return self.show_step("code", EmailCodeForm(), notice=str(refusal))
        return self.show_step(
            "code", EmailCodeForm(), notice="A new code is on its way."
        )

    def visitor_change(self, pending):
        return self.show_step(
            "account",
            VisitorAccountForm(initial={"email": pending.get("email", "")}),
        )

    def send_pending(self, pending):
        """Send the waiting request now that the visitor is signed in."""
        self.request.session.pop(PENDING_KEY, None)
        self.request.user.current_church = self.public_church
        if not may_request(self.request.user, self.public_church):
            return self.refuse_outsider()
        return self.send(
            datetime.datetime.fromisoformat(pending["starts_at"]),
            pending["occasion_for"],
            pending["note"],
        )


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
