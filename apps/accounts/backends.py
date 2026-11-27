"""Permissions per church (decision 0014).

A user's permissions are those of the roles in their active Membership in
the **Current Church**, and nothing else: not ``user.groups``, and not
permissions given straight to a user. Every ``has_perm``,
``PermissionRequiredMixin`` and template ``perms`` check stays Django's
own, and now answers for the Current Church. Active superusers hold every
permission (Django checks that before asking any backend).

``CurrentChurchMiddleware`` sets ``user.current_church`` on each request.
A user object loaded outside a request has none, so it holds no
permissions: code without a request asks ``users_with_perm(church, ...)``.
"""

from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend
from django.contrib.auth.models import Permission


def church_of(user):
    return getattr(user, "current_church", None)


class ChurchRoleBackend(ModelBackend):
    """Signs people in like ModelBackend, by username or by email (owner,
    27 Nov 2026); permissions come from the roles of their Membership in
    the Current Church."""

    def authenticate(self, request, username=None, password=None, **kwargs):
        # An email that is no account's username finds the one account with
        # that email (ignoring case). An email two accounts share finds
        # none, so the sign-in fails as for a wrong password.
        if username and "@" in username:
            User = get_user_model()
            text = username.strip()
            if not User._default_manager.filter(username=text).exists():
                found = list(User._default_manager.filter(email__iexact=text)[:2])
                if len(found) == 1:
                    username = found[0].get_username()
        return super().authenticate(
            request, username=username, password=password, **kwargs
        )

    def get_user_permissions(self, user_obj, obj=None):
        return set()

    def get_group_permissions(self, user_obj, obj=None):
        return self.get_all_permissions(user_obj, obj)

    def get_all_permissions(self, user_obj, obj=None):
        if not user_obj.is_active or user_obj.is_anonymous or obj is not None:
            return set()
        church = church_of(user_obj)
        if church is None:
            return set()
        cache = user_obj.__dict__.setdefault("_church_perm_cache", {})
        if church.pk not in cache:
            held = Permission.objects.filter(
                group__role__memberships__user=user_obj,
                group__role__memberships__church=church,
                group__role__memberships__is_active=True,
            ).values_list("content_type__app_label", "codename")
            cache[church.pk] = {f"{app}.{codename}" for app, codename in held}
        return cache[church.pk]
