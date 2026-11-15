"""Test-data builders shared by every module's tests."""

from itertools import count

from django.contrib.auth import get_user_model

TEST_PASSWORD = "test-only-Pass-8472"

_sequence = count(1)


def make_user(**fields):
    """Create a user with unique defaults; any field can be overridden."""
    n = next(_sequence)
    fields.setdefault("username", f"user{n}")
    fields.setdefault("email", f"user{n}@example.com")
    password = fields.pop("password", TEST_PASSWORD)
    return get_user_model().objects.create_user(password=password, **fields)
