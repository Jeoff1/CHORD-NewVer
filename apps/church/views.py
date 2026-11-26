from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.db.models import Q
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
from apps.core.views import FilteredListView

from . import dashboard, homepage
from .forms import SECTION_ORDER, SECTIONS, ChurchRegistrationForm
from .labels import LABEL_DEFINITIONS, Labels
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


SHOWCASE_SIZE = 12
LISTED_FIELDS = ("name", "slug", "address", "logo")


def listed_churches():
    """The churches the landing page and the Directory list: public ones that
    have also finished their setup (the owner's rule, 2026-11-27). Only what a
    card shows is read: name, page address, street address and logo."""
    return public_churches().filter(setup_completed=True).only(*LISTED_FIELDS)


def with_place(churches):
    """Each church's address on one line, for a card, as ``place``."""
    churches = list(churches)
    for listed in churches:
        listed.place = ", ".join(
            line.strip() for line in listed.address.splitlines() if line.strip()
        )
    return churches


def showcase_churches():
    """The landing page's "United in Worship" carousel: the newest listed
    churches, at most ``SHOWCASE_SIZE``."""
    return with_place(listed_churches().order_by("-created_at", "-pk")[:SHOWCASE_SIZE])


class LandingView(TemplateView):
    """The public front page: what CHORD does, the public churches, and the
    ways to sign in or sign up.

    It is the platform's page (decision 0014), so its wording is the neutral
    default Labels, whatever any church calls things."""

    template_name = "church/landing.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["showcase"] = showcase_churches()
        context["members_label"] = Labels({}).get("member", plural=True)
        return context


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
        if not request.church.setup_completed and self.sets_up(request):
            return redirect("church:setup", section=SECTION_ORDER[0])
        return super().get(request, *args, **kwargs)

    @staticmethod
    def sets_up(request):
        """Whether the person finishes this church's setup: a holder of its
        Administrator role, such as whoever registered it. Not a superuser
        looking in for support, nor anyone else with the permission."""
        from apps.accounts.roles import ADMINISTRATOR

        return request.user.roles_in(request.church).filter(key=ADMINISTRATOR).exists()


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


def public_churches():
    """The churches that chose to be public: in the directory, with a
    homepage. Every other church is absent, and its pages are 404."""
    return ChurchProfile.objects.filter(show_in_directory=True)


DIRECTORY_SORTS = {
    "newest": ("Newest", ("-created_at", "-pk")),
    "name": ("Name, A to Z", ("name", "pk")),
    "-name": ("Name, Z to A", ("-name", "-pk")),
}
SUGGESTION_SIZE = 6
SUGGESTION_MIN_LENGTH = 2


class DirectoryView(FilteredListView):
    """The public list of churches (redesigned 27 Nov 2026): the listed
    churches, searchable by name and address, newest first or by name.

    An HTMX request (the search, the sort, a page link, Back to all
    churches) gets only the results part; any other request, the page."""

    template_name = "church/directory.html"
    results_template = "church/includes/directory_results.html"
    search_fields = ("name", "address")
    paginate_by = 24  # rows of 4, 3, 2 and 1 cards come out even

    def get_sort(self):
        sort = self.request.GET.get("sort", "")
        return sort if sort in DIRECTORY_SORTS else "newest"

    def get_template_names(self):
        if self.request.headers.get("HX-Request"):
            return [self.results_template]
        return [self.template_name]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["object_list"] = with_place(context["object_list"])
        context["sort"] = self.get_sort()
        context["sorts"] = [(key, label) for key, (label, _) in DIRECTORY_SORTS.items()]
        return context

    def get_queryset(self):
        self.queryset = listed_churches().order_by(*DIRECTORY_SORTS[self.get_sort()][1])
        return super().get_queryset()


class ChurchSuggestView(TemplateView):
    """The Directory's suggestions as a visitor types (an HTMX fragment): up to
    ``SUGGESTION_SIZE`` listed churches whose name or address contains the
    text, names starting with it first. Nothing for fewer than
    ``SUGGESTION_MIN_LENGTH`` characters."""

    template_name = "church/includes/directory_suggestions.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        q = self.request.GET.get("q", "").strip()
        churches = []
        if len(q) >= SUGGESTION_MIN_LENGTH:
            matches = listed_churches().filter(
                Q(name__icontains=q) | Q(address__icontains=q)
            )
            starts = list(matches.filter(name__istartswith=q).order_by("name", "pk"))
            rest = matches.exclude(pk__in=[c.pk for c in starts]).order_by("name", "pk")
            churches = with_place(
                (starts + list(rest[:SUGGESTION_SIZE]))[:SUGGESTION_SIZE]
            )
            for listed in churches:
                listed.name_parts = split_match(listed.name, q)
                listed.place_parts = split_match(listed.place, q)
        context.update(q=q, churches=churches, searched=len(q) >= SUGGESTION_MIN_LENGTH)
        return context


def split_match(text, q):
    """``(before, match, after)``: the first place ``q`` appears in ``text``,
    ignoring case, so a template can mark it; ``(text, "", "")`` if nowhere."""
    at = text.lower().find(q.lower())
    if at < 0:
        return (text, "", "")
    return (text[:at], text[at : at + len(q)], text[at + len(q) :])


class ChurchHomepageView(TemplateView):
    """A church's public profile (redesigned 27 Nov 2026): only what it chose
    to publish, the same for everyone, no sign-in needed to view it.

    The Modules' sections go in the sidebar (``slot="side"``) or become the
    main area's tabs."""

    template_name = "church/homepage.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        public_church = get_object_or_404(public_churches(), slug=self.kwargs["slug"])
        sections = homepage.sections(public_church, self.request)
        context.update(
            public_church=public_church,
            sections=sections,
            side_sections=[s for s in sections if s.slot == "side"],
            tab_sections=[s for s in sections if s.slot != "side"],
        )
        return context
