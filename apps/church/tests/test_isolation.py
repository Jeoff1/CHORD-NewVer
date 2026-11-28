"""Phase 9B (decision 0014): one church never sees another's records.

Two churches get the same kinds of records, each created explicitly in its
own church (never through a default), and each record carries its
church's marker word. Each church's administrator, who holds every
permission there, then:

- gets 404 from every page and action that takes an object of the other
  church, by GET and by POST (``OBJECT_URLS``; a test fails when a URL
  taking an object is neither listed nor exempted with a reason);
- never sees the other church's marker on any page without arguments, or
  on any page of its own records (lists, details and every form's choices).
"""

import datetime
import uuid

from django.db import transaction
from django.db.models import F, Value
from django.db.models.functions import Concat
from django.test import TestCase
from django.urls import get_resolver, reverse
from django.urls.resolvers import URLResolver
from django.utils import timezone

from apps.accounts.models import Role
from apps.announcements.models import Announcement
from apps.core.testing import (
    complete_setup,
    first_church,
    make_chord_sheet,
    make_church,
    make_lineup,
    make_occasion,
    make_search_run,
    make_service,
    make_song,
    make_theme,
    make_user,
)
from apps.notifications.models import Notification
from apps.occasions.models import OccasionRequest, OccasionType
from apps.songs.models import ThemeTag, TrustedArtist
from apps.worship.models import Season, SermonSeries, ServiceTemplate

# Every URL taking an object: its name, and its arguments from one church's
# records. ``own=False`` skips checking it with the church's own records.
OBJECT_URLS = {
    "accounts:user_update": lambda o: {"pk": o["admin"].pk},
    "accounts:user_history": lambda o: {"pk": o["admin"].pk},
    "accounts:user_password": lambda o: {"pk": o["admin"].pk},
    "accounts:user_remove": lambda o: {"pk": o["admin"].pk},
    "church:switch": lambda o: {"slug": o["church"].slug},
    "accounts:role_update": lambda o: {"pk": o["role"].pk},
    "accounts:role_delete": lambda o: {"pk": o["role"].pk},
    "notifications:open": lambda o: {"pk": o["notification"].pk},
    "songs:detail": lambda o: {"public_id": o["song"].public_id},
    "songs:update": lambda o: {"public_id": o["song"].public_id},
    "songs:check_again": lambda o: {"public_id": o["song"].public_id},
    "songs:chordsheet": lambda o: {"public_id": o["song"].public_id},
    "songs:chordsheet_approve": lambda o: {"pk": o["sheet"].pk},
    "songs:chordsheet_discard": lambda o: {"pk": o["sheet"].pk},
    "songs:theme_tags_update": lambda o: {"pk": o["tag"].pk},
    "songs:theme_tags_switch": lambda o: {"pk": o["tag"].pk},
    "songs:trusted_artists_update": lambda o: {"pk": o["trusted"].pk},
    "songs:trusted_artists_switch": lambda o: {"pk": o["trusted"].pk},
    "worship:service": lambda o: {"public_id": o["service"].public_id},
    "worship:service_update": lambda o: {"public_id": o["service"].public_id},
    "worship:theme": lambda o: {"public_id": o["service"].public_id},
    "worship:theme_document": lambda o: {"public_id": o["service"].public_id},
    "worship:attendance": lambda o: {"public_id": o["service"].public_id},
    "worship:suggest": lambda o: {"public_id": o["service"].public_id},
    "worship:suggestions": lambda o: {"public_id": o["service"].public_id},
    "worship:suggestion_feel": lambda o: {
        "public_id": o["service"].public_id,
        "pk": o["suggestion"].pk,
    },
    "worship:suggestion_not_worship": lambda o: {
        "public_id": o["service"].public_id,
        "pk": o["suggestion"].pk,
    },
    "worship:lineup": lambda o: {"public_id": o["service"].public_id},
    "worship:lineup_create": lambda o: {"public_id": o["service"].public_id},
    "worship:lineup_add_suggestion": lambda o: {
        "public_id": o["service"].public_id,
        "pk": o["suggestion"].pk,
    },
    "worship:lineup_add": lambda o: {"public_id": o["service"].public_id},
    "worship:lineup_regenerate": lambda o: {"public_id": o["service"].public_id},
    "worship:lineup_confirm": lambda o: {"public_id": o["service"].public_id},
    "worship:lineup_save_playlist": lambda o: {"public_id": o["service"].public_id},
    "worship:lineup_reopen": lambda o: {"public_id": o["service"].public_id},
    "worship:lineup_send_back": lambda o: {"public_id": o["service"].public_id},
    "worship:lineup_song": lambda o: {
        "public_id": o["service"].public_id,
        "pk": o["item"].pk,
    },
    "worship:lineup_swap": lambda o: {
        "public_id": o["service"].public_id,
        "pk": o["item"].pk,
    },
    "worship:lineup_item": lambda o: {
        "public_id": o["service"].public_id,
        "pk": o["item"].pk,
    },
    "worship:lineup_item_action": lambda o: {
        "public_id": o["service"].public_id,
        "pk": o["item"].pk,
        "action": "lock",
    },
    "worship:template_update": lambda o: {"pk": o["template"].pk},
    "worship:seasons_update": lambda o: {"pk": o["season"].pk},
    "worship:seasons_switch": lambda o: {"pk": o["season"].pk},
    "occasions:detail": lambda o: {"public_id": o["occasion"].public_id},
    "occasions:update": lambda o: {"public_id": o["occasion"].public_id},
    "occasions:decide": lambda o: {"public_id": o["request"].public_id},
    "occasions:withdraw": lambda o: {"public_id": o["request"].public_id},
    "occasions:types_update": lambda o: {"pk": o["occasion_type"].pk},
    "occasions:types_switch": lambda o: {"pk": o["occasion_type"].pk},
    "announcements:archive": lambda o: {"public_id": o["announcement"].public_id},
    # Withdrawing from My requests at every church: only one's own.
    "public_requests:withdraw": lambda o: {"public_id": o["request"].public_id},
    # Teams pages for one service: the service lookup is the church's.
    "teams:assign": lambda o: {"public_id": o["service"].public_id},
    "teams:assignment_remove": lambda o: {
        "public_id": o["service"].public_id,
        "assignment_id": uuid.uuid4(),
    },
}
NOT_CHECKED_WITH_OWN = {
    "teams:assignment_remove",  # needs a real assignment
    "worship:theme_document",  # needs a real sermon PDF (test_sermon_pdf.py)
}

# URLs taking an argument that is not another church's record, and why.
EXEMPT = {
    "admin": "Django admin: superusers only, for platform support.",
    "accounts:password_reset_confirm": "A token for one account, not a record.",
    "church:settings": "A section of the Current Church's own settings.",
    "church:setup": "A step of the Current Church's own setup.",
    "churches:home": "A church's public homepage: public by design "
    "(apps/church/tests/test_public_pages.py).",
    "public_requests:request": "Request this service from a public homepage: "
    "public by design (apps/church/tests/test_public_pages.py).",
    "members": "Members is locked to the church from before Phase 9B (§5).",
    "teams:blackout_delete": "A person's own Blackout Date; Teams is locked (§5).",
    "teams:reply": "A person's own assignment; Teams is locked (§5).",
    "teams:swap_request": "A person's own assignment; Teams is locked (§5).",
    "teams:swap_action": "Teams' Swap Requests; Teams is locked (§5).",
    "teams:person_parts": "Teams' roster; Teams is locked (§5).",
    "teams:parts_update": "Team Parts aren't per church yet; Teams is locked (§5).",
    "teams:parts_switch": "Team Parts aren't per church yet; Teams is locked (§5).",
    None: "Media files (the media URL).",
}

# Pages without arguments that aren't church pages.
CRAWL_SKIP = {
    "accounts:logout",
    "accounts:login",
    # Lists every public church, the other one too, by design
    # (apps/church/tests/test_public_pages.py).
    "churches:directory",
}


def url_patterns(patterns=None, namespace=None):
    """``(name, takes_arguments)`` for every URL in the project."""
    for pattern in patterns if patterns is not None else get_resolver().url_patterns:
        if isinstance(pattern, URLResolver):
            yield from url_patterns(
                pattern.url_patterns, pattern.namespace or namespace
            )
            continue
        name = (
            f"{namespace}:{pattern.name}"
            if namespace and pattern.name
            else pattern.name
        )
        regex = pattern.pattern.regex
        yield name, namespace, bool(regex.groups or regex.groupindex)


def build(church, marker):
    """One of each kind of record for ``church``, every name carrying
    ``marker``. Created in ``church`` explicitly, never by a default."""
    # The church's seeded rows carry the marker too.
    ThemeTag.objects.for_church(church).update(
        name=Concat(Value(f"{marker} "), F("name"))
    )
    ServiceTemplate.objects.for_church(church).update(
        name=Concat(Value(f"{marker} "), F("name"))
    )
    OccasionType.objects.for_church(church).update(
        name=Concat(Value(f"{marker} "), F("name")), is_active=True
    )
    for role in Role.objects.filter(church=church):
        role.title = f"{marker} {role.title}"
        role.save()

    admin = make_user(
        church=church,
        roles=["administrator"],
        username=f"{marker.lower()}.admin",
        first_name=marker,
    )
    service = make_service(church=church, name=f"{marker} Sunday")
    series = SermonSeries.objects.create(church=church, name=f"{marker} Series")
    make_theme(service, title=f"{marker} theme", series=series)
    song = make_song(church=church, title=f"{marker} Song", artist=f"{marker} Band")
    run = make_search_run(service, [song])
    lineup = make_lineup(service, [song], confirmed=False)
    occasion_type = OccasionType.objects.for_church(church).first()
    soon = timezone.now() + datetime.timedelta(days=30)
    return {
        "church": church,
        "admin": admin,
        "role": Role.objects.create(church=church, title=f"{marker} Ushers"),
        "notification": Notification.objects.create(
            recipient=admin, church=church, text=f"{marker} note"
        ),
        "song": song,
        "sheet": make_chord_sheet(song, approved=False),
        "tag": ThemeTag.objects.for_church(church).first(),
        "trusted": TrustedArtist.objects.create(church=church, name=f"{marker} Artist"),
        "service": service,
        "suggestion": run.suggestions.first(),
        "item": lineup.items.first(),
        "template": service.template,
        "series": series,
        "season": Season.objects.create(
            church=church,
            name=f"{marker} Season",
            starts_on=datetime.date(2026, 12, 1),
            ends_on=datetime.date(2026, 12, 24),
        ),
        "occasion_type": occasion_type,
        "occasion": make_occasion(occasion_type, occasion_for=f"{marker} couple"),
        "request": OccasionRequest.objects.create(
            church=church,
            requester=admin,
            occasion_type=occasion_type,
            starts_at=soon,
            occasion_for=f"{marker} request",
        ),
        "announcement": Announcement.objects.create(
            church=church, title=f"{marker} news", body="Hello.", author=admin
        ),
    }


class ChurchIsolationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.a = complete_setup(first_church())
        cls.b = complete_setup(make_church("Zebulon Chapel"))
        cls.records = {
            cls.a.pk: build(cls.a, "Aldermoor"),
            cls.b.pk: build(cls.b, "Zebulon"),
        }
        cls.markers = {cls.a.pk: "Aldermoor", cls.b.pk: "Zebulon"}
        # The church names themselves carry no marker.
        cls.a.name = "First Church"
        cls.a.save()

    def pairs(self):
        """(church working in, the other church) both ways round."""
        return ((self.a, self.b), (self.b, self.a))

    def login(self, church):
        self.client.force_login(self.records[church.pk]["admin"])

    def test_every_url_taking_an_object_is_checked_or_exempt(self):
        missing = [
            name
            for name, namespace, takes_arguments in url_patterns()
            if takes_arguments
            and name not in OBJECT_URLS
            and name not in EXEMPT
            and namespace not in EXEMPT
        ]
        self.assertEqual(missing, [], "Add these to OBJECT_URLS or EXEMPT.")

    def test_another_churchs_records_are_404_by_get_and_post(self):
        for church, other in self.pairs():
            self.login(church)
            theirs = self.records[other.pk]
            for name, kwargs in OBJECT_URLS.items():
                url = reverse(name, kwargs=kwargs(theirs))
                with self.subTest(church=church.name, url=name):
                    got = self.client.get(url).status_code
                    posted = self.client.post(url).status_code
                    # 405 only says the page doesn't take that method; the
                    # other method must then be the 404.
                    self.assertIn(got, (404, 405), url)
                    self.assertIn(posted, (404, 405), url)
                    self.assertIn(404, (got, posted), url)

    def test_the_same_urls_open_for_the_churchs_own_records(self):
        # Proves the 404s above come from the church, not from wrong
        # arguments. Each request is rolled back, so actions don't interfere.
        for church, _ in self.pairs():
            self.login(church)
            mine = self.records[church.pk]
            for name, kwargs in OBJECT_URLS.items():
                if not self.checks_with_own(name, church):
                    continue
                url = reverse(name, kwargs=kwargs(mine))
                with self.subTest(church=church.name, url=name):
                    self.assertNotEqual(self.rolled_back_post_or_get(url), 404, url)

    @staticmethod
    def checks_with_own(name, church):
        if name in NOT_CHECKED_WITH_OWN:
            return False
        # Teams is locked for a church without members_teams_unlocked (§5).
        return church.members_teams_unlocked or not name.startswith("teams:")

    def rolled_back_post_or_get(self, url):
        class Rollback(Exception):
            pass

        status = None
        try:
            with transaction.atomic():
                status = self.client.get(url).status_code
                if status == 405:
                    status = self.client.post(url).status_code
                raise Rollback
        except Rollback:
            pass
        return status

    def test_no_page_shows_another_churchs_records(self):
        pages = [
            name
            for name, namespace, takes_arguments in url_patterns()
            if name
            and not takes_arguments
            and namespace != "admin"
            and name not in CRAWL_SKIP
        ]
        for church, other in self.pairs():
            self.login(church)
            marker = self.markers[other.pk]
            mine = self.records[church.pk]
            urls = [reverse(name) for name in pages]
            urls += [
                reverse(name, kwargs=kwargs(mine))
                for name, kwargs in OBJECT_URLS.items()
                if self.checks_with_own(name, church)
            ]
            checked = 0
            for url in urls:
                response = self.client.get(url)
                if response.status_code != 200 or not response.get(
                    "Content-Type", ""
                ).startswith("text/"):
                    continue
                checked += 1
                with self.subTest(church=church.name, url=url):
                    self.assertNotIn(marker, response.content.decode())
            # The crawl really read the church's pages.
            self.assertGreater(checked, 50)
