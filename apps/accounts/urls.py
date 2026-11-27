from django.contrib.auth import views as auth_views
from django.urls import path, reverse_lazy
from django.views.generic import TemplateView

from . import views
from .forms import EmailOrUsernameAuthenticationForm

app_name = "accounts"


def notice(title, message, link_label=None, link_url=None):
    return TemplateView.as_view(
        template_name="accounts/notice.html",
        extra_context={
            "title": title,
            "message": message,
            "link_label": link_label,
            "link_url": link_url,
        },
    )


urlpatterns = [
    # Signing in and own account
    path(
        "login/",
        auth_views.LoginView.as_view(
            template_name="accounts/login.html",
            authentication_form=EmailOrUsernameAuthenticationForm,
            redirect_authenticated_user=True,
        ),
        name="login",
    ),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    # Signing up is registering a church; the old address goes there.
    path("signup/", views.SignUpRedirectView.as_view(), name="signup"),
    path("profile/", views.ProfileView.as_view(), name="profile"),
    path("appearance/", views.AppearanceView.as_view(), name="appearance"),
    path(
        "password/change/",
        views.PasswordChangeView.as_view(),
        name="password_change",
    ),
    path("password/reset/", views.PasswordResetView.as_view(), name="password_reset"),
    path(
        "password/reset/sent/",
        notice(
            "Check your email",
            "If the address matches an account, a link to set a new password "
            "is on its way. The link works once and expires after a few days.",
            "Back to sign in",
            reverse_lazy("accounts:login"),
        ),
        name="password_reset_done",
    ),
    path(
        "password/reset/<uidb64>/<token>/",
        views.PasswordResetConfirmView.as_view(),
        name="password_reset_confirm",
    ),
    path(
        "password/reset/complete/",
        notice(
            "Password set",
            "Your new password is ready to use.",
            "Sign in",
            reverse_lazy("accounts:login"),
        ),
        name="password_reset_complete",
    ),
    # Users
    path("users/", views.UserListView.as_view(), name="user_list"),
    path("users/new/", views.UserCreateView.as_view(), name="user_create"),
    path(
        "users/add-existing/",
        views.AddExistingAccountView.as_view(),
        name="user_add_existing",
    ),
    path(
        "users/<int:pk>/remove/",
        views.RemoveMembershipView.as_view(),
        name="user_remove",
    ),
    path("users/<int:pk>/", views.UserUpdateView.as_view(), name="user_update"),
    path(
        "users/<int:pk>/history/",
        views.UserHistoryView.as_view(),
        name="user_history",
    ),
    path(
        "users/<int:pk>/password/",
        views.UserSetPasswordView.as_view(),
        name="user_password",
    ),
    # Roles
    path("roles/", views.RoleListView.as_view(), name="role_list"),
    path("roles/new/", views.RoleCreateView.as_view(), name="role_create"),
    path(
        "roles/permissions/",
        views.PermissionMatrixView.as_view(),
        name="permission_matrix",
    ),
    path("roles/<int:pk>/", views.RoleUpdateView.as_view(), name="role_update"),
    path("roles/<int:pk>/delete/", views.RoleDeleteView.as_view(), name="role_delete"),
]
