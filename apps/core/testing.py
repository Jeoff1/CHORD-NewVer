"""Test-data builders and stand-ins shared by every module's tests."""

import json
import logging
import urllib.parse
from itertools import count

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test.runner import DiscoverRunner

from . import http, test_environment

TEST_PASSWORD = "test-only-Pass-8472"

_sequence = count(1)


# --- Outside services --------------------------------------------------------


def quiet_logger(test, name="apps.songs.spotify"):
    """Silence a logger for the rest of ``test`` (by default the Spotify
    client's 429 warnings, which tests meet on purpose)."""
    logger = logging.getLogger(name)
    test.addCleanup(setattr, logger, "disabled", logger.disabled)
    logger.disabled = True


class ChordTestRunner(DiscoverRunner):
    """Runs the tests with the network blocked and the keyword ML engine,
    so no test depends on Spotify, LRCLIB or downloaded model files. Parallel
    workers get the same setup (see ``apps/core/test_environment.py``)."""

    parallel_test_suite = test_environment.ChordParallelTestSuite

    def setup_test_environment(self, **kwargs):
        super().setup_test_environment(**kwargs)
        self._real_transport = test_environment.install()

    def teardown_test_environment(self, **kwargs):
        http.set_transport(self._real_transport)
        super().teardown_test_environment(**kwargs)


# A made-up Fernet key for tests; real keys live only in .env.
TEST_TOKEN_KEY = "dGVzdC1vbmx5LWtleS1kby1ub3QtdXNlLTAxMjM0NTY="
# Use with override_settings(**SPOTIFY_TEST_SETTINGS): Spotify set up, with
# made-up credentials, so connecting and playlists are available.
SPOTIFY_TEST_SETTINGS = {
    "SPOTIFY_CLIENT_ID": "test-client",
    "SPOTIFY_CLIENT_SECRET": "test-secret",
    "SPOTIFY_TOKEN_KEY": TEST_TOKEN_KEY,
    "SPOTIFY_REDIRECT_URI": "",
}


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


def make_user(*, roles=(), perms=(), church=None, **fields):
    """Create a user with unique defaults and a Membership in ``church`` (the
    first church by default); any field can be overridden.

    ``roles`` takes default-role keys (e.g. "administrator") of that church's
    roles; ``perms`` takes "app_label.codename" strings, put on a role of the
    user's own in that church (permissions come only from roles, decision
    0014). ``church=False`` makes a user with no membership.

    The user comes back as a request in that church would see them: with
    ``current_church`` set, so tests may call the rules with it directly. A
    user loaded again from the database has no Current Church, and so no
    permissions, as outside any request.
    """
    from apps.accounts.models import Membership, Role

    n = next(_sequence)
    fields.setdefault("username", f"user{n}")
    fields.setdefault("email", f"user{n}@example.com")
    password = fields.pop("password", TEST_PASSWORD)
    user = get_user_model().objects.create_user(password=password, **fields)
    if church is False:
        user.current_church = None
        return user
    church = church or first_church()
    user.current_church = church
    membership = Membership.objects.create(user=user, church=church)
    if roles:
        membership.roles.add(*Role.objects.filter(church=church, key__in=roles))
    if perms:
        own_role = Role.objects.create(church=church, title=f"Test role {n}")
        for name in perms:
            app_label, codename = name.split(".")
            own_role.permissions.add(
                Permission.objects.get(
                    content_type__app_label=app_label, codename=codename
                )
            )
        membership.roles.add(own_role)
    return user


def first_church():
    """The church every installation starts with, which the builders use
    unless given another. Tests about other churches make one with
    ``make_church`` and pass it explicitly; the app itself never falls back
    to any church."""
    from apps.church.models import ChurchProfile

    return ChurchProfile.objects.order_by("pk").first()


def make_church(name="Other Church", **fields):
    """Create a church with its defaults (roles, theme tags, template,
    settings rows), as registering one does."""
    from apps.church.models import ChurchProfile
    from apps.church.seeding import seed_church

    church = ChurchProfile.objects.create(name=name, **fields)
    seed_church(church)
    return church


def make_administrator(**fields):
    return make_user(roles=["administrator"], **fields)


def complete_setup(church=None, **profile_fields):
    """Mark church setup as finished (the first church's, unless given),
    optionally changing profile fields."""
    profile = church or first_church()
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


def make_service(*, church=None, **fields):
    """Create a worship service a week from now, on the church's default
    template (the template's church when a template is given)."""
    import datetime

    from django.utils import timezone

    from apps.worship.models import ServiceTemplate, WorshipService

    n = next(_sequence)
    if "template" in fields:
        church = church or fields["template"].church
    else:
        church = church or first_church()
        fields["template"] = ServiceTemplate.objects.for_church(church).active().first()
    fields["church"] = church
    fields.setdefault("name", fields["template"].name)
    fields.setdefault(
        "starts_at", timezone.now() + datetime.timedelta(days=7, minutes=n)
    )
    return WorshipService.objects.create(**fields)


def make_occasion_type(*, church=None, **fields):
    """An active Occasion Type (Phase 9A, A5) with a unique name, 120
    minutes long."""
    from apps.occasions.models import OccasionType

    n = next(_sequence)
    fields["church"] = church or first_church()
    fields.setdefault("name", f"Occasion type {n}")
    fields.setdefault("length_minutes", 120)
    return OccasionType.objects.create(**fields)


def make_occasion(occasion_type=None, **fields):
    """An Occasion two weeks from now, stored directly (no clash check)."""
    import datetime

    from django.utils import timezone

    from apps.occasions.models import Occasion

    occasion_type = occasion_type or make_occasion_type(
        church=fields.pop("church", None)
    )
    fields["church"] = occasion_type.church
    fields.setdefault("starts_at", timezone.now() + datetime.timedelta(days=14))
    fields.setdefault("length_minutes", occasion_type.length_minutes)
    fields.setdefault("occasion_for", "Ana and Ben")
    return Occasion.objects.create(occasion_type=occasion_type, **fields)


def make_theme(service=None, **fields):
    """Post a theme on a service (a new one unless given)."""
    from apps.worship.models import Theme

    fields.setdefault("title", "Grace that forgives")
    return Theme.objects.create(service=service or make_service(), **fields)


def make_song(*, tags=(), church=None, **fields):
    """Create a song in the church's pool (the first church's by default)
    with a unique Spotify ID.

    Lyrics in tests must be invented or public domain (AGENTS.md).
    """
    from apps.songs.models import Song

    n = next(_sequence)
    fields["church"] = church or first_church()
    fields.setdefault("title", f"Song {n}")
    fields.setdefault("artist", "Test Artist")
    fields.setdefault("spotify_id", f"track{n:017d}")
    song = Song.objects.create(**fields)
    if tags:
        song.tags.set(tags)
    return song


def make_search_run(service, songs, *, placed=None):
    """A finished Search Run for ``service`` that ranked ``songs`` in order.
    The first ``placed`` songs (default: one per slot) are placed in the
    template's slots in order; the rest are other choices."""
    from django.utils import timezone

    from apps.worship.models import SearchRun, Suggestion

    slots = list(service.template.slots.all())
    placed = len(slots) if placed is None else placed
    run = SearchRun.objects.create(
        service=service,
        status=SearchRun.Status.DONE,
        message="Ranked songs from the pool.",
        started_at=timezone.now(),
        finished_at=timezone.now(),
    )
    for rank, song in enumerate(songs, 1):
        slot = slots[rank - 1] if rank <= min(placed, len(slots)) else None
        Suggestion.objects.create(
            run=run,
            song=song,
            rank=rank,
            score=round(1 - rank / 100, 4),
            relevance=1.0,
            familiarity=0,
            season=0,
            recency=0,
            slot=slot,
            reasons=[f"Reason for {song.title}."],
        )
    return run


def make_lineup(service, songs, *, keys=(), confirmed=True):
    """A lineup for ``service`` holding ``songs`` in order, stored directly
    (the rules refuse past services). ``keys`` gives the service keys."""
    from apps.worship.models import Lineup, LineupItem

    lineup = Lineup.objects.create(
        service=service,
        status=Lineup.Status.CONFIRMED if confirmed else Lineup.Status.DRAFT,
    )
    keys = list(keys) + [""] * len(songs)
    for position, (song, key) in enumerate(zip(songs, keys)):
        LineupItem.objects.create(lineup=lineup, song=song, position=position, key=key)
    return lineup


# Public domain (Amazing Grace, John Newton, 1779), in G.
HYMN_SHEET = (
    "{title: Amazing Grace}\n"
    "[G]Amazing [G/B]grace, how [C]sweet the [G]sound\n"
    "That [G]saved a wretch like [D]me\n"
)


def make_chord_sheet(song, *, chordpro=HYMN_SHEET, key="G", approved=True, **fields):
    """A chord sheet for ``song``, approved unless ``approved=False``."""
    from apps.songs.models import ChordSheet

    status = ChordSheet.Status.APPROVED if approved else ChordSheet.Status.PENDING
    return ChordSheet.objects.create(
        song=song, chordpro=chordpro, key=key, status=status, **fields
    )


def make_team_part(name=None, *, church=None, **fields):
    """A Team Part of ``church`` (the first church by default) with a
    unique name (the seeded ones also exist)."""
    from apps.teams.models import TeamPart

    return TeamPart.objects.create(
        church=church or first_church(),
        name=name or f"Part {next(_sequence)}",
        **fields,
    )


def make_team_profile(user, parts=(), *, church=None):
    """Give ``user`` a Team Profile in ``church`` (the parts' church, else
    the first church) with ``parts``."""
    from apps.teams.models import TeamProfile

    parts = list(parts)
    church = church or (parts[0].church if parts else first_church())
    profile, _ = TeamProfile.objects.get_or_create(user=user, church=church)
    profile.parts.set(parts)
    return profile


def make_assignment(service, person, part=None, *, reply="pending"):
    """An Assignment stored directly (the rules refuse past services); the
    person gets the part in their Team Profile in the service's church."""
    from apps.teams.models import Assignment, TeamProfile

    part = part or make_team_part(church=service.church)
    profile, _ = TeamProfile.objects.get_or_create(user=person, church=service.church)
    profile.parts.add(part)
    return Assignment.objects.create(
        service=service, part=part, person=person, reply=reply
    )


def make_spotify_connection(
    user, *, access="test-access-token", refresh="test-refresh-token", expires_in=3600
):
    """A Spotify connection for ``user`` with made-up tokens, stored
    encrypted. Needs ``override_settings(**SPOTIFY_TEST_SETTINGS)``."""
    import datetime

    from django.utils import timezone

    from apps.songs.connections import encrypt
    from apps.songs.models import SpotifyConnection

    return SpotifyConnection.objects.create(
        user=user,
        access_token_encrypted=encrypt(access),
        refresh_token_encrypted=encrypt(refresh),
        expires_at=timezone.now() + datetime.timedelta(seconds=expires_in),
    )


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
