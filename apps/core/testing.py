"""Test-data builders shared by every module's tests."""

from itertools import count

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission

TEST_PASSWORD = "test-only-Pass-8472"

_sequence = count(1)


def make_user(*, roles=(), perms=(), **fields):
    """Create a user with unique defaults; any field can be overridden.

    ``roles`` takes default-role keys (e.g. "administrator"); ``perms`` takes
    "app_label.codename" strings granted directly to the user.
    """
    from apps.accounts.models import Role

    n = next(_sequence)
    fields.setdefault("username", f"user{n}")
    fields.setdefault("email", f"user{n}@example.com")
    password = fields.pop("password", TEST_PASSWORD)
    user = get_user_model().objects.create_user(password=password, **fields)
    if roles:
        user.groups.add(*Role.objects.filter(key__in=roles))
    for name in perms:
        app_label, codename = name.split(".")
        user.user_permissions.add(
            Permission.objects.get(content_type__app_label=app_label, codename=codename)
        )
    return user


def make_administrator(**fields):
    return make_user(roles=["administrator"], **fields)


def complete_setup(**profile_fields):
    """Mark church setup as finished, optionally changing profile fields."""
    from apps.church.models import ChurchProfile

    profile = ChurchProfile.load()
    profile.setup_completed = True
    for name, value in profile_fields.items():
        setattr(profile, name, value)
    profile.save()
    return profile


def make_member(**fields):
    """Create a member with unique defaults and the default status."""
    from apps.members.models import Member, MembershipStatus

    n = next(_sequence)
    fields.setdefault("first_name", f"Person{n}")
    fields.setdefault("last_name", "Tester")
    fields.setdefault("status", MembershipStatus.default())
    return Member.objects.create(**fields)


def make_service(**fields):
    """Create a worship service a week from now, on the default template."""
    import datetime

    from django.utils import timezone

    from apps.worship.models import ServiceTemplate, WorshipService

    n = next(_sequence)
    if "template" not in fields:
        fields["template"] = ServiceTemplate.objects.active().first()
    fields.setdefault("name", fields["template"].name)
    fields.setdefault(
        "starts_at", timezone.now() + datetime.timedelta(days=7, minutes=n)
    )
    return WorshipService.objects.create(**fields)


def make_theme(service=None, **fields):
    """Post a theme on a service (a new one unless given)."""
    from apps.worship.models import Theme

    fields.setdefault("title", "Grace that forgives")
    return Theme.objects.create(service=service or make_service(), **fields)


def close_file_response(response):
    """Close a FileResponse in a test without closing the test database.

    Closing a response sends ``request_finished``, which normally closes the
    database connection; Django's test client avoids that the same way.
    """
    from django.core.signals import request_finished
    from django.db import close_old_connections

    request_finished.disconnect(close_old_connections)
    try:
        response.close()
    finally:
        request_finished.connect(close_old_connections)
