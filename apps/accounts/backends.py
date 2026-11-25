"""Permissions per church (decision 0014).

A user's permissions are those of the roles in their active Membership in
the **Current Church**, and nothing else: not ``user.groups``, and not
permissions given straight to a user. Every ``has_perm``,
``PermissionRequiredMixin`` and template ``perms`` check stays Django's
own, and now answers for the Current Church. Active superusers hold every
permission (Django checks that before asking any backend).

``CurrentChurchMiddleware`` sets ``user.current_church`` on each request.
A user object loaded outside a request has none yet; until Phase 9B slice b
moves that code to ``users_with_perm(church, ...)``, it is answered for the
first church.
"""

from django.contrib.auth.backends import ModelBackend
from django.contrib.auth.models import Permission


def church_of(user):
    church = getattr(user, "current_church", None)
    if church is None and not hasattr(user, "current_church"):
        # Phase 9B, slice a only: no request set it (see the module note).
        from apps.church.models import ChurchProfile

        church = ChurchProfile.load()
    return church


class ChurchRoleBackend(ModelBackend):
    """Signs people in like ModelBackend; permissions come from the roles
    of their Membership in the Current Church."""

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
