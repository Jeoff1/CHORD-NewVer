"""Teams pages: My schedule, Team Profiles, Blackout Dates, Swap Requests
and the service team (Design-Decisions, Phase 8)."""

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.utils.functional import cached_property
from django.views import View
from django.views.generic import FormView, ListView, TemplateView

from apps.church.modules import ModuleRequiredMixin, is_enabled
from apps.church.scoping import get_in_church
from apps.core.people import display_name
from apps.core.views import FormPageMixin
from apps.worship.models import WorshipService
from apps.worship.views.base import service_url

from . import rostering
from .forms import AssignForm, BlackoutForm, PartsForm, SwapRequestForm
from .models import Assignment, BlackoutDate, SwapRequest, TeamPart

MY_SCHEDULE = reverse_lazy("teams:my_schedule")
NOTIFICATIONS = reverse_lazy("notifications:list")


class TeamsMixin(ModuleRequiredMixin, LoginRequiredMixin):
    module = "teams"


class TeamMemberMixin(TeamsMixin, PermissionRequiredMixin):
    """Pages only people on the team use: their Team Profile, Blackout
    Dates and swaps. Being on the team is a permission, never a role."""

    permission_required = rostering.TEAM_PERMISSION


def teams_nav(request):
    """Tabs linking the Teams pages the user may open."""
    user = request.user
    links = []
    if user.has_perm(rostering.TEAM_PERMISSION):
        links.append(("My schedule", reverse("teams:my_schedule")))
    if user.has_perm("teams.view_teamprofile"):
        links.append(("Roster", reverse("teams:roster")))
    if user.has_perm("teams.view_teampart"):
        links.append(("Team parts", reverse("teams:parts_list")))
    return links


class TeamsPageMixin(TeamsMixin):
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["nav_links"] = teams_nav(self.request)
        return context


# --- My schedule --------------------------------------------------------------


class MyScheduleView(TeamsPageMixin, TemplateView):
    """The module's page. People who aren't on the team see their
    notifications instead."""

    template_name = "teams/my_schedule.html"

    def get(self, request, *args, **kwargs):
        if not rostering.may_serve(request.user):
            return redirect(NOTIFICATIONS)
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        context.update(
            assignments=[
                (
                    assignment,
                    rostering.roster_closed(assignment.service),
                    rostering.open_swap(assignment),
                )
                for assignment in rostering.upcoming_assignments(user)
            ],
            parts=rostering.parts_of(user),
            blackouts=rostering.upcoming_blackouts(user),
            open_swaps=rostering.swaps_open_to(user),
        )
        return context


class MyPartsView(TeamMemberMixin, FormPageMixin, FormView):
    form_class = PartsForm
    page_title = "My team parts"
    intro = (
        "The voices and instruments you can take. Only these can be assigned to you."
    )
    success_url = MY_SCHEDULE
    cancel_url = MY_SCHEDULE

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["current"] = rostering.parts_of(self.request.user)
        return kwargs

    def form_valid(self, form):
        rostering.set_parts(
            self.request.user, form.cleaned_data["parts"], self.request.user
        )
        messages.success(self.request, "Your team parts were saved.")
        return super().form_valid(form)


class BlackoutCreateView(TeamMemberMixin, FormPageMixin, FormView):
    form_class = BlackoutForm
    page_title = "Add blackout dates"
    intro = (
        "Days you can't serve, from the first to the last. Nobody can assign "
        "you on them."
    )
    submit_label = "Add"
    success_url = MY_SCHEDULE
    cancel_url = MY_SCHEDULE
    conflict = None

    def get_links(self):
        """After a refusal over an assignment: where to free that day."""
        assignment = self.conflict
        if assignment is None:
            return []
        if assignment.reply == Assignment.Reply.PENDING:
            return [("Decline it on My schedule", str(MY_SCHEDULE))]
        if rostering.open_swap(assignment):
            return [("Your swap request is open on My schedule", str(MY_SCHEDULE))]
        return [
            (
                f"Ask for a swap: {assignment.part} at {assignment.service}",
                rostering.swap_url(assignment),
            )
        ]

    def form_valid(self, form):
        data = form.cleaned_data
        try:
            blackout = rostering.add_blackout(
                self.request.user, data["starts_on"], data["ends_on"], data["note"]
            )
        except rostering.RosterRefused as refused:
            self.conflict = refused.assignment
            form.add_error(None, str(refused))
            return self.form_invalid(form)
        messages.success(
            self.request, f"Blackout dates added: {blackout.date_range()}."
        )
        return super().form_valid(form)


class BlackoutDeleteView(TeamMemberMixin, View):
    def post(self, request, pk):
        blackout = get_object_or_404(BlackoutDate, pk=pk, person=request.user)
        rostering.remove_blackout(blackout, request.user)
        messages.success(request, f"Blackout dates removed: {blackout.date_range()}.")
        return redirect(MY_SCHEDULE)


class ReplyView(TeamsMixin, View):
    """The assigned person accepts or declines. Other people get a 404."""

    def post(self, request, public_id):
        assignment = get_object_or_404(
            Assignment.objects.select_related("service", "part"),
            public_id=public_id,
            person=request.user,
        )
        try:
            rostering.reply(assignment, request.user, request.POST.get("reply", ""))
        except rostering.RosterRefused as refused:
            messages.error(request, str(refused))
        else:
            messages.success(
                request,
                f"You {assignment.get_reply_display().lower()} {assignment.part} "
                f"at {assignment.service}.",
            )
        if request.POST.get("back") == "service":
            return redirect(service_url(assignment.service))
        return redirect(MY_SCHEDULE)


# --- Swap Requests --------------------------------------------------------------


class SwapRequestView(TeamMemberMixin, FormPageMixin, FormView):
    """Ask to be replaced in one of your own assignments."""

    form_class = SwapRequestForm
    page_title = "Ask for a swap"
    submit_label = "Ask for a swap"
    success_url = MY_SCHEDULE
    cancel_url = MY_SCHEDULE

    @cached_property
    def assignment(self):
        return get_object_or_404(
            Assignment.objects.select_related("service", "part").prefetch_related(
                "swap_requests"
            ),
            public_id=self.kwargs["public_id"],
            person=self.request.user,
        )

    def get_context_data(self, **kwargs):
        assignment = self.assignment
        refusal = rostering.swap_refusal(assignment, self.request.user)
        self.intro = refusal or (
            f"{assignment.part} at {assignment.service}. Anyone who has the part, "
            "isn't blacked out that day and isn't already on it can take your "
            "place; the first to take it gets it. You can withdraw until then."
        )
        return super().get_context_data(**kwargs)

    def form_valid(self, form):
        try:
            rostering.request_swap(self.assignment, self.request.user)
        except rostering.RosterRefused as refused:
            messages.error(self.request, str(refused))
        else:
            messages.success(
                self.request,
                f"You asked for a swap: {self.assignment.part} at "
                f"{self.assignment.service}.",
            )
        return redirect(MY_SCHEDULE)


class SwapActionView(TeamMemberMixin, View):
    """Withdraw your own open request, or take someone else's."""

    def post(self, request, public_id, action):
        swap = get_object_or_404(
            SwapRequest.objects.select_related("service", "part"), public_id=public_id
        )
        try:
            if action == "withdraw":
                rostering.withdraw_swap(swap, request.user)
                done = f"You withdrew your swap request for {swap.part}."
            elif action == "take":
                rostering.take_swap(swap, request.user)
                done = f"You took {swap.part} at {swap.service}."
            else:
                raise Http404("Unknown action.")
        except rostering.RosterRefused as refused:
            messages.error(request, str(refused))
        else:
            messages.success(request, done)
        return redirect(MY_SCHEDULE)


# --- The service team ---------------------------------------------------------


class ServiceTeamMixin(TeamsMixin, PermissionRequiredMixin):
    @cached_property
    def service(self):
        return get_in_church(
            WorshipService.objects.select_related("template"),
            self.request.church,
            public_id=self.kwargs["public_id"],
        )


class AssignView(ServiceTeamMixin, TemplateView):
    """Choose a part, then one of the people who may take it."""

    permission_required = "teams.add_assignment"
    template_name = "teams/assign.html"

    @cached_property
    def part(self):
        pk = self.request.POST.get("part") or self.request.GET.get("part")
        if not pk:
            return None
        try:
            return TeamPart.objects.active().get(pk=pk)
        except (TeamPart.DoesNotExist, ValueError) as error:
            raise Http404("No such team part.") from error

    def candidates(self):
        return rostering.candidates(self.service, self.part) if self.part else []

    def get_form(self, data=None):
        available = [person for person, reason in self.candidates() if not reason]
        return AssignForm(data, available=available)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        people = self.candidates()
        context.update(
            service=self.service,
            closed=rostering.roster_closed(self.service),
            parts=TeamPart.objects.active(),
            part=self.part,
            form=kwargs.get("form") or self.get_form(),
            unavailable=[(person, reason) for person, reason in people if reason],
            team=rostering.service_team(self.service),
        )
        return context

    def post(self, request, public_id):
        if self.part is None:
            raise Http404("Choose a team part.")
        form = self.get_form(request.POST)
        if form.is_valid():
            person = form.cleaned_data["person"]
            try:
                rostering.assign(self.service, self.part, person, request.user)
            except rostering.RosterRefused as refused:
                form.add_error(None, str(refused))
            else:
                messages.success(
                    request, f"{display_name(person)} was assigned to {self.part}."
                )
                return redirect(service_url(self.service))
        return self.render_to_response(self.get_context_data(form=form))


class RemoveAssignmentView(ServiceTeamMixin, View):
    permission_required = "teams.delete_assignment"

    def post(self, request, public_id, assignment_id):
        assignment = get_object_or_404(
            Assignment.objects.select_related("person", "part", "service"),
            public_id=assignment_id,
            service=self.service,
        )
        try:
            rostering.remove(assignment, request.user)
        except rostering.RosterRefused as refused:
            messages.error(request, str(refused))
        else:
            messages.success(
                request,
                f"{display_name(assignment.person)} was taken off {assignment.part}.",
            )
        return redirect(service_url(self.service))


def service_team_context(service, user):
    """What the service page shows of the team: for people who may see the
    team, while Teams is switched on."""
    if not is_enabled("teams", service.church) or not user.has_perm(
        "teams.view_assignment"
    ):
        return {}
    team = list(rostering.service_team(service))
    serving = [a for a in team if a.reply in rostering.SERVING]
    return {
        "team": team,
        "team_closed": rostering.roster_closed(service),
        "show_team": True,
        # The card's count (Phase 9A, A7): who accepted, of those serving.
        "team_assigned": len(serving),
        "team_accepted": sum(a.reply == "accepted" for a in serving),
    }


# --- The roster -----------------------------------------------------------------


class RosterView(TeamsPageMixin, PermissionRequiredMixin, ListView):
    """Everyone active, with the parts in their Team Profile."""

    permission_required = "teams.view_teamprofile"
    template_name = "teams/roster.html"

    def get_queryset(self):
        return (
            rostering.team_people()
            .select_related("team_profile")
            .prefetch_related("team_profile__parts")
            .order_by("first_name", "last_name", "username")
        )


class PersonPartsView(TeamsMixin, PermissionRequiredMixin, FormPageMixin, FormView):
    permission_required = "teams.change_teamprofile"
    form_class = PartsForm
    success_url = reverse_lazy("teams:roster")
    cancel_url = reverse_lazy("teams:roster")

    @cached_property
    def person(self):
        return get_object_or_404(rostering.team_people(), pk=self.kwargs["pk"])

    def get_page_title(self):
        return f"Team parts: {display_name(self.person)}"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["current"] = rostering.parts_of(self.person)
        return kwargs

    def form_valid(self, form):
        rostering.set_parts(self.person, form.cleaned_data["parts"], self.request.user)
        messages.success(
            self.request, f"{display_name(self.person)}'s team parts were saved."
        )
        return super().form_valid(form)
