from itertools import groupby

from django.apps import apps as django_apps
from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth import views as auth_views
from django.contrib.auth.forms import SetPasswordForm
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Count, Prefetch
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.views import View
from django.views.generic import (
    CreateView,
    DeleteView,
    FormView,
    ListView,
    RedirectView,
    TemplateView,
    UpdateView,
)

from apps.audit.models import AuditEvent, SignInEvent
from apps.audit.services import diff, record_change, snapshot
from apps.core.views import FilteredListView, FormPageMixin

from . import role_changes
from .forms import (
    AddExistingAccountForm,
    AppearanceForm,
    ProfileForm,
    RoleForm,
    UserCreateForm,
    UserEditForm,
)
from .memberships import is_last_administrator, may_manage_account
from .models import Membership, Role, User
from .roles import managed_permissions


def user_audit_fields(church):
    """What the audit trail records about a user; their roles are those in
    ``church`` (decision 0014)."""
    return {
        "Username": "username",
        "First name": "first_name",
        "Last name": "last_name",
        "Email": "email",
        "Active": "is_active",
        "Roles": lambda user: [role.title for role in user.roles_in(church)],
    }


ROLE_AUDIT_FIELDS = {
    "Name": "title",
    "Description": "description",
    "Permissions": lambda role: [p.name for p in role.permissions.all()],
}
PASSWORD_CHANGE = {"Password": ["", "(new password set)"]}


def church_users(request):
    """Users with a Membership in the Current Church (active or not)."""
    return User.objects.filter(memberships__church=request.church).distinct()


class StaffMixin(LoginRequiredMixin, PermissionRequiredMixin):
    """Signed in and holding ``permission_required``; otherwise 403."""


# --- Own account -----------------------------------------------------------


class AppearanceView(LoginRequiredMixin, FormPageMixin, UpdateView):
    """The person's own light or dark mode (Phase 9A, A7). Anyone signed in
    may change their own; it is a preference, so it isn't audited."""

    form_class = AppearanceForm
    page_title = "Appearance"
    submit_label = "Save"
    success_url = reverse_lazy("accounts:appearance")

    def get_object(self, queryset=None):
        return self.request.user

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, "Your appearance was saved.")
        return response


class ProfileView(LoginRequiredMixin, FormPageMixin, UpdateView):
    form_class = ProfileForm
    page_title = "My profile"
    success_url = reverse_lazy("accounts:profile")

    def get_object(self, queryset=None):
        user = self.request.user
        self.before = snapshot(user, user_audit_fields(self.request.church))
        return user

    def get_links(self):
        return [("Change password", reverse("accounts:password_change"))]

    def form_valid(self, form):
        response = super().form_valid(form)
        record_change(
            self.request.user,
            self.object,
            AuditEvent.Action.CHANGED,
            diff(
                self.before,
                snapshot(self.object, user_audit_fields(self.request.church)),
            ),
        )
        messages.success(self.request, "Your profile was saved.")
        return response


class PasswordChangeView(FormPageMixin, auth_views.PasswordChangeView):
    page_title = "Change password"
    submit_label = "Change password"
    success_url = reverse_lazy("accounts:profile")
    cancel_url = reverse_lazy("accounts:profile")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.user.must_change_password:
            # A Temporary Password: the person can't go anywhere else yet.
            context.update(
                intro="Welcome! Your account started with a temporary password. "
                "Enter it as your old password, then choose your own to go on.",
                cancel_url=None,
            )
        return context

    def form_valid(self, form):
        response = super().form_valid(form)
        if self.request.user.must_change_password:
            self.request.user.must_change_password = False
            self.request.user.save(update_fields=["must_change_password"])
        record_change(
            self.request.user,
            self.request.user,
            AuditEvent.Action.CHANGED,
            PASSWORD_CHANGE,
        )
        messages.success(self.request, "Your password was changed.")
        return response


class PasswordResetView(FormPageMixin, auth_views.PasswordResetView):
    page_title = "Reset your password"
    intro = (
        "Enter the email address on your account. If it matches an account, "
        "we'll send a link to set a new password."
    )
    submit_label = "Send reset link"
    cancel_url = reverse_lazy("accounts:login")
    email_template_name = "accounts/email/password_reset_email.txt"
    subject_template_name = "accounts/email/password_reset_subject.txt"
    success_url = reverse_lazy("accounts:password_reset_done")


class PasswordResetConfirmView(FormPageMixin, auth_views.PasswordResetConfirmView):
    template_name = "accounts/password_reset_confirm.html"
    page_title = "Set a new password"
    submit_label = "Set password"
    success_url = reverse_lazy("accounts:password_reset_complete")

    def form_valid(self, form):
        # The person chose this password, so a Temporary Password is gone.
        form.user.must_change_password = False
        return super().form_valid(form)


# --- Users -------------------------------------------------------------------


class UserListView(StaffMixin, FilteredListView):
    permission_required = "accounts.view_user"
    model = User
    template_name = "accounts/user_list.html"
    search_fields = ("username", "first_name", "last_name", "email")
    STATUSES = {"active": True, "inactive": False}

    def get_status(self):
        status = self.request.GET.get("status", "active")
        return status if status in (*self.STATUSES, "all") else "active"

    def get_queryset(self):
        queryset = (
            super()
            .get_queryset()
            .filter(memberships__church=self.request.church)
            .prefetch_related(
                Prefetch(
                    "memberships",
                    queryset=Membership.objects.filter(
                        church=self.request.church
                    ).prefetch_related("roles"),
                    to_attr="church_memberships",
                )
            )
            .order_by("username")
        )
        status = self.get_status()
        if status != "all":
            queryset = queryset.filter(is_active=self.STATUSES[status])
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["status"] = self.get_status()
        return context


class UserCreateView(StaffMixin, FormPageMixin, CreateView):
    permission_required = "accounts.add_user"
    form_class = UserCreateForm
    page_title = "Add user"
    submit_label = "Add user"
    success_url = reverse_lazy("accounts:user_list")
    cancel_url = reverse_lazy("accounts:user_list")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["church"] = self.request.church
        return kwargs

    def form_valid(self, form):
        response = super().form_valid(form)
        record_change(
            self.request.user,
            self.object,
            AuditEvent.Action.CREATED,
            diff({}, snapshot(self.object, user_audit_fields(self.request.church))),
        )
        messages.success(self.request, f"User {self.object.username} was added.")
        return response


HISTORY_FIELDS = ("Roles", "Active")


def role_history(user, church):
    """The user's role and active-status changes in ``church`` from the
    Audit Trail, newest first: (event, [(label, before, after), ...])."""
    events = (
        AuditEvent.objects.for_church(church)
        .filter(
            content_type=ContentType.objects.get_for_model(User),
            object_id=str(user.pk),
        )
        .select_related("actor")
    )
    history = []
    for event in events:
        rows = [
            (label, *event.changes[label])
            for label in HISTORY_FIELDS
            if label in event.changes
        ]
        if rows:
            history.append((event, rows))
    return history


class UserUpdateView(StaffMixin, FormPageMixin, UpdateView):
    """Edit a user. A change of roles or active status never deletes what
    they did before. When it takes away something a Module ties to a
    permission (such as their places on coming services' teams), the form
    lists it first, and the editor chooses to end or keep it (Phase 9A, A2).
    """

    permission_required = "accounts.change_user"
    model = User
    form_class = UserEditForm
    template_name = "accounts/user_form.html"
    success_url = reverse_lazy("accounts:user_list")
    cancel_url = reverse_lazy("accounts:user_list")
    CHOICES = {"end": "Ended", "keep": "Kept"}

    def get_page_title(self):
        return f"Edit user: {self.object.username}"

    def get_links(self):
        links = []
        if may_manage_account(self.object, self.request.church):
            url = reverse("accounts:user_password", kwargs={"pk": self.object.pk})
            links.append(("Set a new password", url))
        if self.request.user.has_perm(HISTORY_PERMISSION):
            history = reverse("accounts:user_history", kwargs={"pk": self.object.pk})
            links.append(("History", history))
        return links

    def get_queryset(self):
        return church_users(self.request)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["editor"] = self.request.user
        kwargs["church"] = self.request.church
        self.before = snapshot(self.object, user_audit_fields(self.request.church))
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["role_history"] = role_history(self.object, self.request.church)
        return context

    def form_valid(self, form):
        found = role_changes.consequences(
            form.instance,
            church=self.request.church,
            roles=list(form.cleaned_data["roles"]),
            is_active=form.cleaned_data["is_active"],
        )
        choice = self.request.POST.get("after_change")
        if found and choice not in self.CHOICES:
            # Show what the change takes away, and ask; nothing is saved yet.
            return self.render_to_response(
                self.get_context_data(
                    form=form,
                    consequences=found,
                    choice_missing="after_change_shown" in self.request.POST,
                )
            )
        with transaction.atomic():
            response = super().form_valid(form)
            changes = diff(
                self.before,
                snapshot(self.object, user_audit_fields(self.request.church)),
            )
            for consequence in found:
                if choice == "end":
                    consequence.end(self.request.user)
                changes[consequence.title] = [
                    "",
                    f"{self.CHOICES[choice]} ({len(consequence.items)})",
                ]
            record_change(
                self.request.user, self.object, AuditEvent.Action.CHANGED, changes
            )
        messages.success(self.request, f"User {self.object.username} was saved.")
        return response


HISTORY_PERMISSION = "audit.view_auditevent"
HISTORY_LENGTH = 50


class UserHistoryView(StaffMixin, TemplateView):
    """A user's History (Phase 9A, A3): their latest sign-ins, sign-outs and
    failed sign-ins, and the latest changes they made, from the Audit
    Trail. Needs the permission that shows the audit log."""

    permission_required = HISTORY_PERMISSION
    template_name = "accounts/user_history.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        person = get_object_or_404(church_users(self.request), pk=self.kwargs["pk"])
        # Owner, 2026-11-26 (option a): sign-ins belong to the account, so a
        # church sees them only for an account that is its alone, by the
        # same test as editing it. A shared or superuser account's sign-ins
        # aren't even read.
        shows_sign_ins = may_manage_account(person, self.request.church)
        context.update(
            person=person,
            shows_sign_ins=shows_sign_ins,
            sign_ins=(
                SignInEvent.objects.filter(user=person)[:HISTORY_LENGTH]
                if shows_sign_ins
                else []
            ),
            changes=AuditEvent.objects.for_church(self.request.church)
            .filter(actor=person)
            .select_related("content_type")[:HISTORY_LENGTH],
            history_length=HISTORY_LENGTH,
            can_edit=self.request.user.has_perm("accounts.change_user"),
        )
        return context


class UserSetPasswordView(StaffMixin, FormPageMixin, FormView):
    permission_required = "accounts.change_user"
    form_class = SetPasswordForm
    submit_label = "Set password"
    success_url = reverse_lazy("accounts:user_list")
    cancel_url = reverse_lazy("accounts:user_list")

    def dispatch(self, request, *args, **kwargs):
        self.target = get_object_or_404(church_users(request), pk=kwargs["pk"])
        return super().dispatch(request, *args, **kwargs)

    def has_permission(self):
        # Phase 9B: never the password of an account another church (or a
        # superuser) relies on; its owner changes it.
        return super().has_permission() and may_manage_account(
            self.target, self.request.church
        )

    def get_page_title(self):
        return f"Set a new password for {self.target.username}"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.target
        return kwargs

    def form_valid(self, form):
        form.save()
        if self.target == self.request.user:
            update_session_auth_hash(self.request, self.target)
        record_change(
            self.request.user, self.target, AuditEvent.Action.CHANGED, PASSWORD_CHANGE
        )
        messages.success(
            self.request, f"A new password was set for {self.target.username}."
        )
        return super().form_valid(form)


# --- Roles -------------------------------------------------------------------


class RoleListView(StaffMixin, ListView):
    permission_required = "accounts.view_role"
    template_name = "accounts/role_list.html"

    def get_queryset(self):
        return Role.objects.filter(church=self.request.church).annotate(
            user_count=Count("memberships", distinct=True)
        )


class RoleCreateView(StaffMixin, FormPageMixin, CreateView):
    permission_required = "accounts.add_role"
    form_class = RoleForm
    page_title = "Add role"
    intro = "After adding the role, choose its permissions in the permission matrix."
    submit_label = "Add role"
    success_url = reverse_lazy("accounts:role_list")
    cancel_url = reverse_lazy("accounts:role_list")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["church"] = self.request.church
        return kwargs

    def form_valid(self, form):
        response = super().form_valid(form)
        record_change(
            self.request.user,
            self.object,
            AuditEvent.Action.CREATED,
            diff({}, snapshot(self.object, ROLE_AUDIT_FIELDS)),
        )
        messages.success(self.request, f"Role {self.object.title} was added.")
        return response


class RoleUpdateView(StaffMixin, FormPageMixin, UpdateView):
    permission_required = "accounts.change_role"
    model = Role
    form_class = RoleForm
    success_url = reverse_lazy("accounts:role_list")
    cancel_url = reverse_lazy("accounts:role_list")

    def get_page_title(self):
        return f"Edit role: {self.object.title}"

    def get_queryset(self):
        return Role.objects.filter(church=self.request.church)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["church"] = self.request.church
        self.before = snapshot(self.object, ROLE_AUDIT_FIELDS)
        return kwargs

    def form_valid(self, form):
        response = super().form_valid(form)
        record_change(
            self.request.user,
            self.object,
            AuditEvent.Action.CHANGED,
            diff(self.before, snapshot(self.object, ROLE_AUDIT_FIELDS)),
        )
        messages.success(self.request, f"Role {self.object.title} was saved.")
        return response


class RoleDeleteView(StaffMixin, DeleteView):
    permission_required = "accounts.delete_role"
    model = Role
    template_name = "accounts/role_confirm_delete.html"
    success_url = reverse_lazy("accounts:role_list")

    def get_queryset(self):
        return Role.objects.filter(church=self.request.church)

    def get_object(self, queryset=None):
        role = super().get_object(queryset)
        if role.is_administrator:
            raise PermissionDenied("The Administrator role can't be deleted.")
        return role

    def form_valid(self, form):
        role = self.object
        record_change(
            self.request.user,
            role,
            AuditEvent.Action.DELETED,
            diff(snapshot(role, ROLE_AUDIT_FIELDS), {}),
        )
        messages.success(self.request, f"Role {role.title} was deleted.")
        return super().form_valid(form)


class PermissionMatrixView(StaffMixin, TemplateView):
    """Every managed permission against every role, as checkboxes.

    Anyone who can view roles sees it; saving needs ``change_role``. The
    Administrator column is fixed: it always has every permission.
    """

    permission_required = "accounts.view_role"
    template_name = "accounts/permission_matrix.html"

    def get_roles(self):
        return list(
            Role.objects.filter(church=self.request.church).prefetch_related(
                "permissions"
            )
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        roles = self.get_roles()
        held = {role.pk: {p.pk for p in role.permissions.all()} for role in roles}
        sections = []
        for app_label, perms in groupby(
            managed_permissions(), key=lambda p: p.content_type.app_label
        ):
            rows = [
                (
                    perm,
                    [
                        (role, role.is_administrator or perm.pk in held[role.pk])
                        for role in roles
                    ],
                )
                for perm in perms
            ]
            sections.append((django_apps.get_app_config(app_label).verbose_name, rows))
        context.update(
            roles=roles,
            sections=sections,
            can_edit=self.request.user.has_perm("accounts.change_role"),
        )
        return context

    def post(self, request, *args, **kwargs):
        if not request.user.has_perm("accounts.change_role"):
            raise PermissionDenied
        managed = {p.pk: p for p in managed_permissions()}
        changed = []
        for role in self.get_roles():
            if role.is_administrator:
                continue
            before = snapshot(role, ROLE_AUDIT_FIELDS)
            selected = {
                int(pk)
                for pk in request.POST.getlist(f"role-{role.pk}")
                if pk.isdigit() and int(pk) in managed
            }
            current = {p.pk for p in role.permissions.all() if p.pk in managed}
            if selected == current:
                continue
            role.permissions.add(*[managed[pk] for pk in selected - current])
            role.permissions.remove(*[managed[pk] for pk in current - selected])
            role = Role.objects.prefetch_related("permissions").get(pk=role.pk)
            record_change(
                request.user,
                role,
                AuditEvent.Action.CHANGED,
                diff(before, snapshot(role, ROLE_AUDIT_FIELDS)),
            )
            changed.append(role.title)
        if changed:
            messages.success(request, f"Permissions saved for: {', '.join(changed)}.")
        else:
            messages.info(request, "No permissions changed.")
        return redirect("accounts:permission_matrix")


# --- Accounts and churches (Phase 9B, decision 0014) ---------------------------


class SignUpRedirectView(RedirectView):
    """The old personal sign-up address (owner, 27 Nov 2026): signing up for
    CHORD is registering a church, whose first step makes the person's
    account (``SignUpForm``), so old links and bookmarks go there, keeping
    any query string."""

    pattern_name = "churches:register"
    query_string = True
    permanent = False


class AddExistingAccountView(StaffMixin, FormPageMixin, FormView):
    """Add someone who already has an account to this church, by their
    exact username or email, with the roles they get here."""

    permission_required = "accounts.add_user"
    form_class = AddExistingAccountForm
    page_title = "Add an existing account"
    intro = (
        "For someone who already has a CHORD account, for example one they "
        "made themselves or use in another church. They keep their own "
        "password; this church gives them roles."
    )
    submit_label = "Add to this church"
    success_url = reverse_lazy("accounts:user_list")
    cancel_url = reverse_lazy("accounts:user_list")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["church"] = self.request.church
        return kwargs

    def form_valid(self, form):
        membership = form.save()
        user = membership.user
        record_change(
            self.request.user,
            user,
            AuditEvent.Action.CHANGED,
            {
                "Membership": ["", "Added to this church"],
                "Roles": ["", [role.title for role in membership.roles.all()]],
            },
            church=self.request.church,
        )
        messages.success(self.request, f"{user.username} was added to this church.")
        return super().form_valid(form)


class RemoveMembershipView(StaffMixin, View):
    """Take someone out of this church (POST). Their account and history
    stay; only their place and roles here go. Never the last
    administrator, and never yourself."""

    permission_required = "accounts.change_user"

    def post(self, request, pk):
        person = get_object_or_404(church_users(request), pk=pk)
        back = redirect("accounts:user_update", pk=person.pk)
        church = request.church
        if person.pk == request.user.pk:
            messages.error(request, "You can't remove yourself from the church.")
            return back
        if is_last_administrator(person, church):
            messages.error(
                request,
                "This is the only active administrator. Make someone else an "
                "administrator first.",
            )
            return back
        if role_changes.consequences(person, church=church, roles=[], is_active=False):
            messages.error(
                request,
                "They still hold places on coming services. Take away their "
                "roles first; that page lets you end or keep those places.",
            )
            return back
        roles = [role.title for role in person.roles_in(church)]
        person.memberships.filter(church=church).delete()
        record_change(
            request.user,
            person,
            AuditEvent.Action.CHANGED,
            {"Membership": ["In this church", "Removed"], "Roles": [roles, []]},
            church=church,
        )
        messages.success(request, f"{person.username} was removed from this church.")
        return redirect("accounts:user_list")
