"""Phase 9B, slice e (decision 0014): the public pages.

The Directory, a Church Homepage, Request this service and My requests,
each seen by a visitor who isn't signed in, someone from another church,
one of the church's own people, and for a hidden church. No public page
ever shows lyrics, chord sheets, songs, lineups, members or teams.
"""

import datetime

from django.contrib.staticfiles import finders
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.announcements.models import Announcement
from apps.core.testing import (
    TEST_PASSWORD,
    complete_setup,
    first_church,
    make_assignment,
    make_chord_sheet,
    make_church,
    make_lineup,
    make_member,
    make_service,
    make_song,
    make_team_part,
    make_theme,
    make_user,
)
from apps.notifications.models import Notification
from apps.occasions.models import OccasionRequest, OccasionType

DIRECTORY = reverse("churches:directory")
MY_REQUESTS = reverse("public_requests:my_requests")
LOGIN = reverse("accounts:login")
# Private words planted in the church's records; never on a public page.
PRIVATE = "Quillfeather"


def home_url(church):
    return reverse("churches:home", kwargs={"slug": church.slug})


def request_url(church, occasion_type):
    return reverse(
        "public_requests:request",
        kwargs={"slug": church.slug, "type_pk": occasion_type.pk},
    )


def soon(days=20, hour=10):
    day = timezone.localdate() + datetime.timedelta(days=days)
    return timezone.make_aware(datetime.datetime.combine(day, datetime.time(hour)))


class PublicPagesTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        # The church from before Phase 9B, after its Administrator switches
        # "Show the church publicly" on.
        cls.church = complete_setup(
            first_church(),
            name="Riverside Church",
            show_in_directory=True,
            show_upcoming_services=True,
            about="We meet by the river.\nAll are welcome.",
            address="1 River Road, Springfield",
        )
        cls.wedding = OccasionType.objects.for_church(cls.church).get(name="Wedding")
        cls.wedding.is_active = True
        cls.wedding.offered_publicly = True
        cls.wedding.save()
        cls.baptism = OccasionType.objects.for_church(cls.church).get(name="Baptism")
        cls.baptism.is_active = True  # active, but not offered publicly
        cls.baptism.save()
        cls.funeral = OccasionType.objects.for_church(cls.church).get(name="Funeral")
        cls.funeral.offered_publicly = True  # offered, but switched off
        cls.funeral.save()

        cls.member = make_user(church=cls.church, roles=["church_member"])
        cls.approver = make_user(church=cls.church, roles=["pastoral_staff"])
        cls.other_church = complete_setup(make_church("Hilltop Chapel"))
        cls.outsider = make_user(church=cls.other_church, roles=["administrator"])
        cls.hidden = complete_setup(make_church("Hidden Hall"), show_in_directory=False)
        cls.hidden_type = OccasionType.objects.for_church(cls.hidden).get(
            name="Wedding"
        )
        cls.hidden_type.is_active = True
        cls.hidden_type.offered_publicly = True
        cls.hidden_type.save()

        # Private records, every one carrying the private word.
        cls.service = make_service(
            church=cls.church, name=f"{PRIVATE} Sunday", starts_at=soon(days=3)
        )
        make_theme(cls.service, title=f"{PRIVATE} theme")
        song = make_song(
            church=cls.church,
            title=f"{PRIVATE} Song",
            artist=f"{PRIVATE} Band",
            lyrics=f"{PRIVATE} lyric line",
        )
        make_chord_sheet(song, chordpro=f"{{title: {PRIVATE}}}\n[G]{PRIVATE} chords")
        make_lineup(cls.service, [song])
        make_member(first_name=PRIVATE, last_name="Person")
        make_assignment(cls.service, cls.member, make_team_part(name=f"{PRIVATE} part"))

        Announcement.objects.create(
            church=cls.church,
            title="Picnic on Sunday",
            body="Bring a dish.",
            author=cls.approver,
            visibility=Announcement.Visibility.PUBLIC,
        )
        for title, fields in (
            (f"{PRIVATE} internal", {}),
            (
                f"{PRIVATE} archived",
                {
                    "visibility": Announcement.Visibility.PUBLIC,
                    "archived_at": timezone.now(),
                },
            ),
            (
                f"{PRIVATE} team",
                {
                    "visibility": Announcement.Visibility.PUBLIC,
                    "audience": Announcement.Audience.SERVICE_TEAM,
                    "service": cls.service,
                },
            ),
        ):
            Announcement.objects.create(
                church=cls.church, title=title, body="x", author=cls.approver, **fields
            )

    def visitors(self):
        """(who, user or None) for each kind of visitor."""
        return (
            ("anonymous", None),
            ("other church", self.outsider),
            ("member", self.member),
        )

    def visit_as(self, user):
        self.client.logout()
        if user is not None:
            self.client.force_login(user)

    def set_church(self, **fields):
        for name, value in fields.items():
            setattr(self.church, name, value)
        self.church.save()


class DirectoryTests(PublicPagesTestCase):
    def test_public_churches_only_for_everyone(self):
        for who, user in self.visitors():
            self.visit_as(user)
            with self.subTest(who=who):
                page = self.client.get(DIRECTORY)
                self.assertContains(page, "Riverside Church")
                self.assertContains(page, "Hilltop Chapel")
                self.assertNotContains(page, "Hidden Hall")

    def test_search_on_name_and_address_ignoring_case(self):
        by_name = self.client.get(DIRECTORY, {"q": "riverSIDE"})
        self.assertContains(by_name, "Riverside Church")
        self.assertNotContains(by_name, "Hilltop Chapel")
        by_address = self.client.get(DIRECTORY, {"q": "SPRINGFIELD"})
        self.assertContains(by_address, "Riverside Church")
        hidden = self.client.get(DIRECTORY, {"q": "hidden"})
        self.assertNotContains(hidden, "Hidden Hall")

    def test_it_is_paginated(self):
        for n in range(25):
            make_church(f"Valley Church {n:02d}", setup_completed=True)
        first = self.client.get(DIRECTORY, {"q": "valley"})
        self.assertEqual(len(first.context["object_list"]), 24)
        second = self.client.get(DIRECTORY, {"q": "valley", "page": 2})
        self.assertEqual(len(second.context["object_list"]), 1)


class DirectoryRedesignTests(PublicPagesTestCase):
    """The redesign (27 Nov 2026): the landing showcase's rule, sorting, the
    HTMX results and suggestions, and the way home."""

    def test_a_public_church_that_has_not_finished_setup_is_left_out(self):
        make_church("Half Built Chapel", setup_completed=False)
        page = self.client.get(DIRECTORY)
        self.assertNotContains(page, "Half Built Chapel")
        self.assertContains(page, "Riverside Church")

    def test_newest_first_by_default_and_by_name_either_way(self):
        make_church("Abbey Road Church", setup_completed=True)
        make_church("Zion Hill Church", setup_completed=True)

        def names(**params):
            return [
                c.name
                for c in self.client.get(DIRECTORY, params).context["object_list"]
            ]

        self.assertEqual(names()[:2], ["Zion Hill Church", "Abbey Road Church"])
        self.assertEqual(names(sort="name")[0], "Abbey Road Church")
        self.assertEqual(names(sort="-name")[0], "Zion Hill Church")
        self.assertEqual(names(sort="nonsense"), names())  # unknown: newest

    def test_a_church_card_shows_its_page_logo_or_fallback_and_no_contact(self):
        page = self.client.get(DIRECTORY)
        self.assertContains(page, f'href="{home_url(self.church)}"')
        self.assertContains(page, "1 River Road, Springfield")
        self.assertContains(page, "dir-card__fallback")
        self.assertContains(page, "View church")
        self.church.logo.name = "church/riverside-logo.png"
        self.church.save()
        self.assertContains(self.client.get(DIRECTORY), "church/riverside-logo.png")

    def test_an_htmx_request_gets_only_the_results(self):
        page = self.client.get(DIRECTORY, {"q": "river"}, HTTP_HX_REQUEST="true")
        self.assertTemplateUsed(page, "church/includes/directory_results.html")
        self.assertTemplateNotUsed(page, "church/directory.html")
        self.assertNotContains(page, "<html")
        self.assertContains(page, "Search results for <q>river</q>", html=False)
        self.assertContains(page, "1 church found")
        self.assertContains(page, "Back to all churches")

    def test_the_full_page_has_the_search_and_the_way_home(self):
        page = self.client.get(DIRECTORY)
        self.assertTemplateUsed(page, "church/directory.html")
        self.assertContains(page, "Discover Churches")
        self.assertContains(page, f'href="{reverse("home")}"')
        self.assertContains(page, "Back to Home")
        self.assertContains(page, f'hx-get="{reverse("churches:suggest")}"')
        self.assertContains(page, "css/directory.css")
        self.assertNotContains(page, "Back to all churches")

    def test_the_placeholder_cards_stay_hidden_unless_loading_is_slow(self):
        # They share .dir-grid (display: grid), so the hiding rule must be
        # the more specific one, or they show under the real cards for good.
        css = open(finders.find("css/directory.css"), encoding="utf-8").read()
        self.assertIn(".dir-area .dir-grid.dir-skeleton { display: none; }", css)
        self.assertIn(
            ".dir-area.is-slow .dir-grid.dir-skeleton { display: grid; }", css
        )
        self.assertContains(self.client.get(DIRECTORY), 'class="dir-grid dir-skeleton"')

    def test_an_empty_search_offers_every_church_again(self):
        page = self.client.get(DIRECTORY, {"q": "nothing like this"})
        self.assertContains(page, "No church matches")
        self.assertContains(page, "Show all churches")

    def test_signed_in_people_keep_their_account_and_theme(self):
        self.member.theme = "dark"
        self.member.save()
        self.visit_as(self.member)
        page = self.client.get(DIRECTORY)
        self.assertContains(page, "Riverside Church")
        self.assertContains(page, 'var choice = "dark"')
        self.assertEqual(int(self.client.session["_auth_user_id"]), self.member.pk)


class SuggestionTests(PublicPagesTestCase):
    SUGGEST = reverse("churches:suggest")

    def test_listed_churches_only_by_name_or_address(self):
        make_church("Half Built Chapel", setup_completed=False)
        by_name = self.client.get(self.SUGGEST, {"q": "chapel"})
        # The match is marked, so look for each church by its page.
        self.assertContains(by_name, f'href="{home_url(self.other_church)}"')
        self.assertEqual(
            [c.name for c in by_name.context["churches"]], ["Hilltop Chapel"]
        )
        hidden = self.client.get(self.SUGGEST, {"q": "hidden"})
        self.assertEqual(hidden.context["churches"], [])
        self.assertNotContains(hidden, home_url(self.hidden))
        by_address = self.client.get(self.SUGGEST, {"q": "springfield"})
        self.assertContains(by_address, "Riverside Church")
        self.assertContains(by_address, f'href="{home_url(self.church)}"')
        self.assertContains(by_address, "See all results for")

    def test_nothing_for_one_letter_and_at_most_six(self):
        self.assertNotContains(self.client.get(self.SUGGEST, {"q": "r"}), "Riverside")
        for n in range(8):
            make_church(f"Meadow Church {n}", setup_completed=True)
        page = self.client.get(self.SUGGEST, {"q": "meadow"})
        self.assertEqual(len(page.context["churches"]), 6)

    def test_the_typed_text_is_marked_and_escaped(self):
        page = self.client.get(self.SUGGEST, {"q": "river"})
        self.assertContains(page, "<mark>River</mark>side Church", html=False)
        make_church("<b>Bold</b> Chapel", setup_completed=True)
        page = self.client.get(self.SUGGEST, {"q": "bold"})
        self.assertContains(
            page, "&lt;b&gt;<mark>Bold</mark>&lt;/b&gt; Chapel", html=False
        )

    def test_names_that_start_with_the_text_come_first(self):
        make_church("Old Hilltop Fellowship", setup_completed=True)
        page = self.client.get(self.SUGGEST, {"q": "hilltop"})
        self.assertEqual(page.context["churches"][0].name, "Hilltop Chapel")

    def test_no_church_can_take_the_suggest_address(self):
        self.assertNotEqual(make_church("Suggest").slug, "suggest")


class HomepageTests(PublicPagesTestCase):
    def test_what_everyone_sees(self):
        for who, user in self.visitors():
            self.visit_as(user)
            with self.subTest(who=who):
                page = self.client.get(home_url(self.church))
                self.assertContains(page, "Riverside Church")
                self.assertContains(page, "We meet by the river.<br>All are welcome.")
                self.assertContains(page, "1 River Road")
                self.assertContains(page, "Picnic on Sunday")
                self.assertContains(page, "Wedding")
                self.assertNotContains(page, "Baptism")
                self.assertNotContains(page, "Funeral")
                # The upcoming service: date, time and kind only.
                self.assertContains(page, "Upcoming services")
                self.assertContains(page, self.service.template.name)
                self.assertNotContains(page, PRIVATE)

    def test_a_hidden_or_unknown_church_is_404_for_everyone(self):
        for who, user in self.visitors():
            self.visit_as(user)
            with self.subTest(who=who):
                self.assertEqual(
                    self.client.get(home_url(self.hidden)).status_code, 404
                )
                missing = reverse("churches:home", kwargs={"slug": "no-such-church"})
                self.assertEqual(self.client.get(missing).status_code, 404)
        # Even its own people.
        self.visit_as(make_user(church=self.hidden, roles=["administrator"]))
        self.assertEqual(self.client.get(home_url(self.hidden)).status_code, 404)

    def test_upcoming_services_only_when_switched_on(self):
        self.set_church(show_upcoming_services=False)
        self.assertNotContains(
            self.client.get(home_url(self.church)), "Upcoming services"
        )

    def test_a_switched_off_module_adds_nothing(self):
        self.set_church(disabled_modules=["occasions", "announcements"])
        page = self.client.get(home_url(self.church))
        self.assertNotContains(page, "Request this service")
        self.assertNotContains(page, "Picnic on Sunday")
        self.set_church(disabled_modules=["worship"])
        self.assertNotContains(
            self.client.get(home_url(self.church)), "Upcoming services"
        )

    def test_request_buttons_follow_the_outside_requests_setting(self):
        self.visit_as(self.outsider)
        self.assertContains(
            self.client.get(home_url(self.church)), "Request this service"
        )
        self.set_church(accept_outside_requests=False)
        page = self.client.get(home_url(self.church))
        self.assertNotContains(page, "Request this service")
        self.assertContains(page, "its own people only")
        self.visit_as(self.member)
        self.assertContains(
            self.client.get(home_url(self.church)), "Request this service"
        )


class ProfileRedesignTests(PublicPagesTestCase):
    """The public profile (redesign, 27 Nov 2026): a public website for each
    church, the same for everyone, with no sign-in needed to view it."""

    def test_everyone_views_the_same_profile_without_signing_in(self):
        for who, user in self.visitors():
            self.visit_as(user)
            with self.subTest(who=who):
                page = self.client.get(home_url(self.church))
                self.assertEqual(page.status_code, 200)
                self.assertTemplateUsed(page, "church/homepage.html")
                # The cover, the sidebar and both tabs.
                self.assertContains(page, 'class="pf-banner"')
                self.assertContains(
                    page,
                    '<h1 class="pf-name" id="pf-name">Riverside Church</h1>',
                    html=False,
                )
                self.assertContains(page, "Announcements")
                self.assertContains(page, "Available services")
                self.assertContains(page, "Picnic on Sunday")
                self.assertContains(page, "Wedding")
                self.assertContains(page, "Upcoming services")
                self.assertContains(page, "Powered by")
                # Nothing private, and no sign-in asked for just viewing.
                self.assertNotContains(page, PRIVATE)
                self.assertNotContains(page, "sign in to send one")

    def test_the_sections_go_in_the_sidebar_and_the_tabs(self):
        page = self.client.get(home_url(self.church))
        tabs = [s.label for s in page.context["tab_sections"]]
        self.assertEqual(tabs, ["Announcements", "Available services"])
        self.assertEqual(
            [s.template for s in page.context["side_sections"]],
            ["worship/includes/homepage_upcoming.html"],
        )
        self.assertEqual(page.context["tab_sections"][0].count, 1)

    def test_contact_shows_once_with_links(self):
        self.set_church(
            phone="0917 555 0100",
            email="office@river.example",
            website="https://river.example",
        )
        page = self.client.get(home_url(self.church))
        content = page.content.decode()
        self.assertIn('href="tel:09175550100"', content)
        self.assertIn('href="mailto:office@river.example"', content)
        self.assertIn('href="https://river.example"', content)
        self.assertIn(
            "https://www.google.com/maps/search/?api=1&amp;query=1%20River%20Road",
            content,
        )
        self.assertEqual(content.count("0917 555 0100"), 1)
        self.assertEqual(content.count(">office@river.example<"), 1)

    def test_the_way_back_and_home(self):
        page = self.client.get(home_url(self.church))
        self.assertContains(page, f'href="{DIRECTORY}"')
        self.assertContains(page, "Back to Churches")
        self.assertContains(page, f'href="{reverse("home")}"')

    def test_no_announcements_shows_a_note_while_the_module_is_on(self):
        Announcement.objects.for_church(self.church).delete()
        page = self.client.get(home_url(self.church))
        self.assertContains(page, "No announcements yet.")
        self.set_church(disabled_modules=["announcements"])
        page = self.client.get(home_url(self.church))
        self.assertNotContains(page, "No announcements yet.")
        self.assertEqual(
            [s.label for s in page.context["tab_sections"]], ["Available services"]
        )

    def test_a_long_announcement_gets_read_more(self):
        Announcement.objects.create(
            church=self.church,
            title="Long news",
            body="Word " * 80,
            author=self.approver,
            visibility=Announcement.Visibility.PUBLIC,
        )
        page = self.client.get(home_url(self.church))
        self.assertContains(page, "Read more", count=1)

    def test_a_visitor_is_offered_to_sign_in_only_to_request(self):
        self.set_church(accept_outside_requests=False)
        page = self.client.get(home_url(self.church))
        self.assertNotContains(page, "Request this service")
        self.assertContains(page, "If you belong to it")
        self.assertContains(page, "Wedding")  # still visible to everyone

    def test_its_own_styles_load_and_the_logo_or_fallback_shows(self):
        page = self.client.get(home_url(self.church))
        self.assertContains(page, "css/profile.css")
        self.assertContains(page, "church/profile.js")
        self.assertContains(page, "pf-logo--none")
        self.church.logo.name = "church/riverside-logo.png"
        self.church.save()
        self.assertContains(
            self.client.get(home_url(self.church)), "church/riverside-logo.png"
        )


class RequestThisServiceTests(PublicPagesTestCase):
    def ask(self, user=None, occasion_type=None, starts_at=None):
        return self.client.post(
            request_url(self.church, occasion_type or self.wedding),
            {
                "starts_at": (starts_at or soon()).strftime("%Y-%m-%dT%H:%M"),
                "occasion_for": "Ana and Ben",
                "note": "",
            },
        )

    def test_a_visitor_signs_in_and_comes_back_to_the_form(self):
        url = request_url(self.church, self.wedding)
        response = self.client.get(url)
        self.assertRedirects(
            response, f"{LOGIN}?next={url}", fetch_redirect_response=False
        )
        signed_in = self.client.post(
            f"{LOGIN}?next={url}",
            {
                "username": self.outsider.username,
                "password": TEST_PASSWORD,
                "next": url,
            },
        )
        self.assertRedirects(signed_in, url, fetch_redirect_response=False)
        self.assertContains(self.client.get(url), "Request: Wedding")

    def test_only_a_safe_next_address(self):
        signed_in = self.client.post(
            LOGIN,
            {
                "username": self.outsider.username,
                "password": TEST_PASSWORD,
                "next": "https://elsewhere.example/steal",
            },
        )
        self.assertRedirects(signed_in, reverse("home"), fetch_redirect_response=False)

    def test_someone_from_another_church_requests_and_approvers_hear(self):
        self.visit_as(self.outsider)
        self.assertRedirects(self.ask(), MY_REQUESTS)
        record = OccasionRequest.objects.get()
        self.assertEqual(record.church, self.church)
        self.assertEqual(record.requester, self.outsider)
        self.assertTrue(
            Notification.objects.filter(
                recipient=self.approver, church=self.church
            ).exists()
        )
        self.assertFalse(Notification.objects.filter(recipient=self.member).exists())

    def test_outsiders_only_while_the_church_accepts_them(self):
        self.set_church(accept_outside_requests=False)
        self.visit_as(self.outsider)
        self.assertEqual(
            self.client.get(request_url(self.church, self.wedding)).status_code, 403
        )
        self.assertEqual(self.ask().status_code, 403)
        self.assertFalse(OccasionRequest.objects.exists())
        self.visit_as(self.member)
        self.assertRedirects(self.ask(), MY_REQUESTS)

    def test_a_clash_shows_only_as_booked_to_others(self):
        self.visit_as(self.outsider)
        response = self.ask(starts_at=self.service.starts_at)
        self.assertContains(response, "That time is already booked.")
        self.assertNotContains(response, PRIVATE)
        self.assertFalse(OccasionRequest.objects.exists())
        self.visit_as(self.member)  # the church's own people see the name
        self.assertContains(self.ask(starts_at=self.service.starts_at), PRIVATE)

    def test_what_isnt_offered_publicly_is_404(self):
        church_b_type = OccasionType.objects.for_church(self.other_church).first()
        hidden_member = make_user(church=self.hidden, roles=["administrator"])
        for who, user in (*self.visitors(), ("hidden church's own", hidden_member)):
            self.visit_as(user)
            with self.subTest(who=who):
                for url in (
                    request_url(self.church, self.baptism),  # not offered
                    request_url(self.church, self.funeral),  # switched off
                    request_url(self.church, church_b_type),  # another church's
                    request_url(self.hidden, self.hidden_type),  # hidden church
                    reverse(
                        "public_requests:request",
                        kwargs={"slug": "no-such-church", "type_pk": self.wedding.pk},
                    ),
                ):
                    self.assertEqual(self.client.get(url).status_code, 404, url)
                    self.assertEqual(self.client.post(url).status_code, 404, url)

    def test_occasions_switched_off_is_404(self):
        self.set_church(disabled_modules=["occasions"])
        self.visit_as(self.outsider)
        self.assertEqual(
            self.client.get(request_url(self.church, self.wedding)).status_code, 404
        )


class MyRequestsEverywhereTests(PublicPagesTestCase):
    def setUp(self):
        self.mine = OccasionRequest.objects.create(
            church=self.church,
            requester=self.outsider,
            occasion_type=self.wedding,
            starts_at=soon(),
            occasion_for="Ana and Ben",
        )
        self.at_home = OccasionRequest.objects.create(
            church=self.other_church,
            requester=self.outsider,
            occasion_type=OccasionType.objects.for_church(self.other_church).first(),
            starts_at=soon(days=25),
            occasion_for="Cy and Di",
        )
        self.theirs = OccasionRequest.objects.create(
            church=self.church,
            requester=self.member,
            occasion_type=self.wedding,
            starts_at=soon(days=30),
            occasion_for=f"{PRIVATE} couple",
        )

    def withdraw(self, record):
        return self.client.post(
            reverse("public_requests:withdraw", kwargs={"public_id": record.public_id})
        )

    def test_own_requests_at_every_church(self):
        self.visit_as(self.outsider)
        page = self.client.get(MY_REQUESTS)
        self.assertContains(page, "Riverside Church")
        self.assertContains(page, "Hilltop Chapel")
        self.assertNotContains(page, PRIVATE)

    def test_a_visitor_signs_in_first(self):
        self.assertRedirects(
            self.client.get(MY_REQUESTS), f"{LOGIN}?next={MY_REQUESTS}"
        )

    def test_withdraw_own_pending_only(self):
        self.visit_as(self.outsider)
        self.assertRedirects(self.withdraw(self.mine), MY_REQUESTS)
        self.mine.refresh_from_db()
        self.assertEqual(self.mine.status, OccasionRequest.Status.WITHDRAWN)
        # Not again, once decided.
        self.withdraw(self.mine)
        self.mine.refresh_from_db()
        self.assertEqual(self.mine.status, OccasionRequest.Status.WITHDRAWN)
        # Never someone else's.
        self.assertEqual(self.withdraw(self.theirs).status_code, 404)
        self.theirs.refresh_from_db()
        self.assertTrue(self.theirs.is_pending)

    def test_withdrawing_needs_post(self):
        self.visit_as(self.outsider)
        url = reverse(
            "public_requests:withdraw", kwargs={"public_id": self.mine.public_id}
        )
        self.assertEqual(self.client.get(url).status_code, 405)


class NothingPrivateOnAPublicPageTests(PublicPagesTestCase):
    def test_no_lyrics_chords_songs_lineups_members_or_teams(self):
        public_pages = [
            DIRECTORY,
            f"{DIRECTORY}?q=river",
            home_url(self.church),
            home_url(self.other_church),
            request_url(self.church, self.wedding),
            MY_REQUESTS,
        ]
        for who, user in self.visitors():
            self.visit_as(user)
            for url in public_pages:
                response = self.client.get(url)
                with self.subTest(who=who, url=url):
                    self.assertIn(response.status_code, (200, 302))
                    self.assertNotIn(PRIVATE, response.content.decode())
