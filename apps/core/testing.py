"""Test-data builders and stand-ins shared by every module's tests."""

import json
import urllib.parse
from itertools import count

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test.runner import DiscoverRunner

from . import http

TEST_PASSWORD = "test-only-Pass-8472"

_sequence = count(1)


# --- Outside services --------------------------------------------------------


def _no_network(method, url, **kwargs):
    raise AssertionError(
        f"A test tried to reach {url}. Tests must not use the network: wrap "
        "the code in FakeHttp (apps/core/testing.py)."
    )


class ChordTestRunner(DiscoverRunner):
    """Runs the tests with the network blocked and the keyword ML engine,
    so no test depends on Spotify, LRCLIB or downloaded model files."""

    def setup_test_environment(self, **kwargs):
        from django.conf import settings

        super().setup_test_environment(**kwargs)
        settings.ML_ENGINE = "keyword"
        settings.SPOTIFY_CLIENT_ID = ""
        settings.SPOTIFY_CLIENT_SECRET = ""
        self._real_transport = http.set_transport(_no_network)

    def teardown_test_environment(self, **kwargs):
        http.set_transport(self._real_transport)
        super().teardown_test_environment(**kwargs)


class FakeHttp:
    """A stand-in for the network. Use it as a context manager::

        with FakeHttp() as web:
            web.reply("GET", "https://lrclib.net/api/get", {"plainLyrics": "..."})
            ...
        web.calls  # every request made, in order

    A reply is matched by method and URL prefix; the first match wins, and
    replies added later come first. ``reply`` takes JSON data, or a function
    ``(call) -> (status, data)``. A request nothing matches fails the test.
    """

    def __init__(self):
        self.calls = []
        self._replies = []
        self._context = None

    def reply(self, method, url_prefix, data=None, *, status=200, headers=None):
        self._replies.insert(0, (method, url_prefix, data, status, headers or {}))
        return self

    def __call__(self, method, url, *, headers, body, timeout):
        parts = urllib.parse.urlsplit(url)
        call = {
            "method": method,
            "url": url,
            "path": f"{parts.scheme}://{parts.netloc}{parts.path}",
            "params": dict(urllib.parse.parse_qsl(parts.query)),
            "headers": headers,
            "body": body.decode("utf-8") if body else "",
        }
        self.calls.append(call)
        for reply_method, prefix, data, status, reply_headers in self._replies:
            if reply_method == method and url.startswith(prefix):
                if callable(data):
                    status, data = data(call)
                text = "" if data is None else json.dumps(data)
                return http.Response(
                    status=status, data=data, headers=reply_headers, text=text
                )
        raise AssertionError(f"FakeHttp has no reply for {method} {url}")

    def __enter__(self):
        self._context = http.use_transport(self)
        self._context.__enter__()
        return self

    def __exit__(self, *exc_info):
        return self._context.__exit__(*exc_info)

    def paths(self):
        return [call["path"] for call in self.calls]


# --- Builders ----------------------------------------------------------------


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
