from itertools import groupby

from django.apps import apps as django_apps
from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth import views as auth_views
from django.contrib.auth.forms import SetPasswordForm
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.core.exceptions import PermissionDenied
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.views.generic import (
    CreateView,
    DeleteView,
    FormView,
    ListView,
    TemplateView,
    UpdateView,
)

from apps.audit.models import AuditEvent
from apps.audit.services import diff, record_change, snapshot
from apps.core.views import FilteredListView, FormPageMixin

from .forms import ProfileForm, RoleForm, UserCreateForm, UserEditForm
from .models import Role, User
from .roles import managed_permissions

USER_AUDIT_FIELDS = {
    "Username": "username",
    "First name": "first_name",
    "Last name": "last_name",
    "Email": "email",
    "Active": "is_active",
    "Roles": lambda user: [role.name for role in user.roles],
}
ROLE_AUDIT_FIELDS = {
    "Name": "name",
    "Description": "description",
    "Permissions": lambda role: [p.name for p in role.permissions.all()],
}
PASSWORD_CHANGE = {"Password": ["", "(new password set)"]}


class StaffMixin(LoginRequiredMixin, PermissionRequiredMixin):
    """Signed in and holding ``permission_required``; otherwise 403."""


# --- Own account -----------------------------------------------------------


class ProfileView(LoginRequiredMixin, FormPageMixin, UpdateView):
    form_class = ProfileForm
    page_title = "My profile"
    success_url = reverse_lazy("accounts:profile")

    def get_object(self, queryset=None):
        user = self.request.user
        self.before = snapshot(user, USER_AUDIT_FIELDS)
        return user

    def get_links(self):
        return [("Change password", reverse("accounts:password_change"))]

    def form_valid(self, form):
        response = super().form_valid(form)
        record_change(
            self.request.user,
            self.object,
            AuditEvent.Action.CHANGED,
            diff(self.before, snapshot(self.object, USER_AUDIT_FIELDS)),
        )
        messages.success(self.request, "Your profile was saved.")
        return response


class PasswordChangeView(FormPageMixin, auth_views.PasswordChangeView):
    page_title = "Change password"
    submit_label = "Change password"
    success_url = reverse_lazy("accounts:profile")
    cancel_url = reverse_lazy("accounts:profile")

    def form_valid(self, form):
        response = super().form_valid(form)
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
            super().get_queryset().prefetch_related("groups").order_by("username")
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

    def form_valid(self, form):
        response = super().form_valid(form)
        record_change(
            self.request.user,
            self.object,
            AuditEvent.Action.CREATED,
            diff({}, snapshot(self.object, USER_AUDIT_FIELDS)),
        )
        messages.success(self.request, f"User {self.object.username} was added.")
        return response


class UserUpdateView(StaffMixin, FormPageMixin, UpdateView):
    permission_required = "accounts.change_user"
    model = User
    form_class = UserEditForm
    success_url = reverse_lazy("accounts:user_list")
    cancel_url = reverse_lazy("accounts:user_list")

    def get_page_title(self):
        return f"Edit user: {self.object.username}"

    def get_links(self):
        url = reverse("accounts:user_password", kwargs={"pk": self.object.pk})
        return [("Set a new password", url)]

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["editor"] = self.request.user
        self.before = snapshot(self.object, USER_AUDIT_FIELDS)
        return kwargs

    def form_valid(self, form):
        response = super().form_valid(form)
        record_change(
            self.request.user,
            self.object,
            AuditEvent.Action.CHANGED,
            diff(self.before, snapshot(self.object, USER_AUDIT_FIELDS)),
        )
        messages.success(self.request, f"User {self.object.username} was saved.")
        return response


class UserSetPasswordView(StaffMixin, FormPageMixin, FormView):
    permission_required = "accounts.change_user"
    form_class = SetPasswordForm
    submit_label = "Set password"
    success_url = reverse_lazy("accounts:user_list")
    cancel_url = reverse_lazy("accounts:user_list")

    def dispatch(self, request, *args, **kwargs):
        self.target = get_object_or_404(User, pk=kwargs["pk"])
        return super().dispatch(request, *args, **kwargs)

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
        return Role.objects.annotate(user_count=Count("user", distinct=True))


class RoleCreateView(StaffMixin, FormPageMixin, CreateView):
    permission_required = "accounts.add_role"
    form_class = RoleForm
    page_title = "Add role"
    intro = "After adding the role, choose its permissions in the permission matrix."
    submit_label = "Add role"
    success_url = reverse_lazy("accounts:role_list")
    cancel_url = reverse_lazy("accounts:role_list")

    def form_valid(self, form):
        response = super().form_valid(form)
        record_change(
            self.request.user,
            self.object,
            AuditEvent.Action.CREATED,
            diff({}, snapshot(self.object, ROLE_AUDIT_FIELDS)),
        )
        messages.success(self.request, f"Role {self.object.name} was added.")
        return response


class RoleUpdateView(StaffMixin, FormPageMixin, UpdateView):
    permission_required = "accounts.change_role"
    model = Role
    form_class = RoleForm
    success_url = reverse_lazy("accounts:role_list")
    cancel_url = reverse_lazy("accounts:role_list")

    def get_page_title(self):
        return f"Edit role: {self.object.name}"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
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
        messages.success(self.request, f"Role {self.object.name} was saved.")
        return response


class RoleDeleteView(StaffMixin, DeleteView):
    permission_required = "accounts.delete_role"
    model = Role
    template_name = "accounts/role_confirm_delete.html"
    success_url = reverse_lazy("accounts:role_list")

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
        messages.success(self.request, f"Role {role.name} was deleted.")
        return super().form_valid(form)


class PermissionMatrixView(StaffMixin, TemplateView):
    """Every managed permission against every role, as checkboxes.

    Anyone who can view roles sees it; saving needs ``change_role``. The
    Administrator column is fixed: it always has every permission.
    """

    permission_required = "accounts.view_role"
    template_name = "accounts/permission_matrix.html"

    def get_roles(self):
        return list(Role.objects.prefetch_related("permissions"))

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
            changed.append(role.name)
        if changed:
            messages.success(request, f"Permissions saved for: {', '.join(changed)}.")
        else:
            messages.info(request, "No permissions changed.")
        return redirect("accounts:permission_matrix")
