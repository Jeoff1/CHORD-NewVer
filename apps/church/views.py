from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.http import require_POST
from django.views.generic import FormView, TemplateView

from apps.accounts.forms import SignUpForm
from apps.audit.models import AuditEvent
from apps.audit.services import diff, record_change, snapshot

from . import dashboard
from .forms import SECTION_ORDER, SECTIONS, ChurchRegistrationForm
from .labels import LABEL_DEFINITIONS
from .middleware import SESSION_KEY
from .models import ChurchProfile
from .modules import MODULES_BY_CODE
from .registration import register_church

MANAGE_PERMISSION = "church.change_churchprofile"


def profile_audit_fields():
    """What the audit trail records about the Church Profile."""
    fields = {
        "Church name": "name",
        "Address": "address",
        "Phone": "phone",
        "Email": "email",
        "Website": "website",
        "Logo": "logo",
        "Currency": "currency",
        "Time zone": "time_zone",
        "Switched-off modules": lambda p: [
            MODULES_BY_CODE[c].name for c in p.disabled_modules if c in MODULES_BY_CODE
        ],
        "Setup completed": "setup_completed",
    }
    for d in LABEL_DEFINITIONS:
        fields[f"Label: {d.singular}"] = lambda p, key=d.key: (
            f"{p.label_set.get(key)} / {p.label_set.get(key, plural=True)}"
        )
    return fields


class LandingView(TemplateView):
    """The public front page: what CHORD does, and the way to sign in.

    Its feature list shows only the switched-on Modules, and its wording
    uses the church's Labels."""

    template_name = "church/landing.html"


class DashboardView(LoginRequiredMixin, TemplateView):
    """What needs the person now (Phase 9A, A7): what to act on, what is
    coming up, and the Modules' side cards. Each Module adds its own
    through ``apps/church/dashboard.py``.

    A visitor who isn't signed in sees the landing page instead."""

    template_name = "church/dashboard.html"

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return LandingView.as_view()(request, *args, **kwargs)
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        context.update(
            greeting=dashboard.greeting(),
            first_name=user.first_name or user.get_username(),
            today=timezone.localdate(),
            attention=dashboard.attention(self.request),
            coming_up=dashboard.coming_up(self.request),
            panels=dashboard.panels(self.request),
        )
        return context

    def get(self, request, *args, **kwargs):
        if not request.church.setup_completed and request.user.has_perm(
            MANAGE_PERMISSION
        ):
            return redirect("church:setup", section=SECTION_ORDER[0])
        return super().get(request, *args, **kwargs)


class ProfileSectionView(LoginRequiredMixin, PermissionRequiredMixin, FormView):
    """One Church Profile section, on the settings pages or in the wizard."""

    permission_required = MANAGE_PERMISSION
    template_name = "church/profile_section.html"
    wizard = False

    def dispatch(self, request, *args, **kwargs):
        self.section = kwargs["section"]
        if self.section not in SECTIONS:
            raise Http404("Unknown settings section.")
        return super().dispatch(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        if self.wizard and request.church.setup_completed:
            return redirect("church:settings", section=self.section)
        return super().get(request, *args, **kwargs)

    def get_form_class(self):
        return SECTIONS[self.section][1]

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        # A fresh copy: a form that doesn't validate mustn't change
        # request.church for the rest of the request.
        kwargs["instance"] = profile = ChurchProfile.objects.get(
            pk=self.request.church.pk
        )
        self.before = snapshot(profile, profile_audit_fields())
        return kwargs

    @property
    def is_last_step(self):
        return self.section == SECTION_ORDER[-1]

    def form_valid(self, form):
        profile = form.instance
        form.save()
        if self.wizard and self.is_last_step:
            profile.setup_completed = True
            profile.save(update_fields=["setup_completed", "updated_at"])
        record_change(
            self.request.user,
            profile,
            AuditEvent.Action.CHANGED,
            diff(self.before, snapshot(profile, profile_audit_fields())),
        )
        if self.wizard and self.is_last_step:
            messages.success(self.request, "Church setup is complete.")
        elif not self.wizard:
            messages.success(self.request, f"{SECTIONS[self.section][0]} saved.")
        return super().form_valid(form)

    def get_success_url(self):
        if not self.wizard:
            return reverse("church:settings", kwargs={"section": self.section})
        if self.is_last_step:
            return reverse("home")
        next_section = SECTION_ORDER[SECTION_ORDER.index(self.section) + 1]
        return reverse("church:setup", kwargs={"section": next_section})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            wizard=self.wizard,
            section=self.section,
            section_title=SECTIONS[self.section][0],
            sections=[(key, SECTIONS[key][0]) for key in SECTION_ORDER],
            step_number=SECTION_ORDER.index(self.section) + 1,
            is_last_step=self.is_last_step,
        )
        if self.wizard and self.section != SECTION_ORDER[0]:
            previous = SECTION_ORDER[SECTION_ORDER.index(self.section) - 1]
            context["previous_url"] = reverse(
                "church:setup", kwargs={"section": previous}
            )
        return context


# --- Churches on the platform (Phase 9B, decision 0014) ------------------------


class RegisterChurchView(TemplateView):
    """Sign in your church: its name, plus a new account for a visitor who
    isn't signed in. The person becomes its first Administrator and goes
    on to the setup wizard."""

    template_name = "church/register.html"

    def forms(self, data=None):
        church_form = ChurchRegistrationForm(data, prefix="church")
        account_form = None if self.request.user.is_authenticated else SignUpForm(data)
        return church_form, account_form

    def get(self, request, *args, **kwargs):
        church_form, account_form = self.forms()
        return self.render_to_response(
            self.get_context_data(church_form=church_form, account_form=account_form)
        )

    def post(self, request, *args, **kwargs):
        church_form, account_form = self.forms(request.POST)
        valid = church_form.is_valid()
        valid = (account_form is None or account_form.is_valid()) and valid
        if not valid:
            return self.render_to_response(
                self.get_context_data(
                    church_form=church_form, account_form=account_form
                )
            )
        church, user = register_church(
            church_form.cleaned_data["name"],
            user=request.user if request.user.is_authenticated else None,
            account_form=account_form,
        )
        if not request.user.is_authenticated:
            login(request, user, backend=settings.AUTHENTICATION_BACKENDS[0])
        request.session[SESSION_KEY] = church.pk
        messages.success(request, f"{church.name} is registered. Let's set it up.")
        return redirect("church:setup", section=SECTION_ORDER[0])


@method_decorator(require_POST, name="dispatch")
class SwitchChurchView(LoginRequiredMixin, View):
    """Work in another of the person's churches (POST only, with the CSRF
    token). A church they have no active Membership in is 404; a superuser
    may switch to any church, for support."""

    def post(self, request, slug):
        churches = ChurchProfile.objects.all()
        if not request.user.is_superuser:
            churches = churches.filter(
                memberships__user=request.user, memberships__is_active=True
            )
        church = get_object_or_404(churches.distinct(), slug=slug)
        request.session[SESSION_KEY] = church.pk
        messages.info(request, f"You're now working in {church.name}.")
        return redirect("home")
