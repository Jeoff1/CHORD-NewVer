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
