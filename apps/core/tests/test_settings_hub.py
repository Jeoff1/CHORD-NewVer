"""The Settings hub (Phase 9A, A7, part 3): one place for every setting,
with a categorised side menu built from what each app registers."""

from django.test import RequestFactory, TestCase
from django.urls import reverse

from apps.core.settings_menu import SettingsMenu
from apps.core.testing import complete_setup, make_administrator, make_user


def menu_for(user, path="/"):
    request = RequestFactory().get(path)
    request.user = user
    request.church = None
    return SettingsMenu(request)


def labels(menu):
    return {
        category.title: [p.label for p in category.pages]
        for category in menu.categories
    }


class MenuTests(TestCase):
    def setUp(self):
        complete_setup()

    def test_the_administrator_sees_every_category_in_order(self):
        menu = menu_for(make_administrator())
        self.assertEqual(
            [category.title for category in menu.categories],
            [
                "General",
                "People and access",
                "Members",
                "Worship",
                "Teams and occasions",
                "Integrations",
            ],
        )
        found = labels(menu)
        self.assertEqual(found["General"], ["Church details", "Labels", "Modules"])
        self.assertEqual(
            found["People and access"], ["Users", "Roles and permissions", "Audit log"]
        )
        self.assertEqual(found["Teams and occasions"], ["Team parts", "Occasion types"])
        self.assertEqual(found["Integrations"], ["Spotify"])

    def test_worship_pages_sit_in_two_groups(self):
        worship = next(
            c for c in menu_for(make_administrator()).categories if c.key == "worship"
        )
        groups = [(page.group, page.label) for page in worship.pages]
        self.assertEqual(
            groups,
            [
                ("Services", "Service templates"),
                ("Services", "Sermon series"),
                ("Services", "Seasons"),
                ("Songs and suggestions", "Theme tags"),
                ("Songs and suggestions", "Trusted artists"),
                ("Songs and suggestions", "Worship check"),
                ("Songs and suggestions", "Suggestion settings"),
            ],
        )

    def test_only_pages_the_person_may_open_show(self):
        pastor = make_user(roles=["pastoral_staff"])
        found = labels(menu_for(pastor))
        self.assertNotIn("General", found)
        self.assertNotIn("People and access", found)
        self.assertNotIn("Integrations", found)
        self.assertIn("Service templates", found["Worship"])
        self.assertNotIn("Trusted artists", found["Worship"])
        self.assertEqual(found["Teams and occasions"], ["Team parts", "Occasion types"])
        self.assertNotIn(
            "Team parts",
            labels(menu_for(make_user(roles=["office_staff"]))).get(
                "Teams and occasions", []
            ),
        )

    def test_a_person_with_no_settings_has_no_menu(self):
        menu = menu_for(make_user(roles=["church_member"]))
        self.assertEqual(menu.categories, [])
        self.assertIsNone(menu.home_url)

    def test_a_switched_off_modules_pages_are_gone(self):
        complete_setup(disabled_modules=["teams", "members"])
        found = labels(menu_for(make_administrator()))
        self.assertNotIn("Members", found)
        self.assertEqual(found["Teams and occasions"], ["Occasion types"])
        complete_setup(disabled_modules=["worship"])
        found = labels(menu_for(make_administrator()))
        # Occasions and Teams need Worship; the Spotify page is Worship's.
        self.assertNotIn("Worship", found)
        self.assertNotIn("Teams and occasions", found)
        self.assertNotIn("Integrations", found)

    def test_the_current_page_includes_its_add_and_edit_pages(self):
        admin = make_administrator()
        menu = menu_for(admin, reverse("worship:template_create"))
        self.assertEqual(menu.current.label, "Service templates")
        self.assertEqual(menu.current.group, "Services")
        self.assertIsNone(menu_for(admin, reverse("worship:home")).current)


class HubPageTests(TestCase):
    def setUp(self):
        complete_setup()

    def test_the_gear_opens_the_first_page_the_person_may_open(self):
        self.client.force_login(make_administrator())
        page = self.client.get(reverse("home"))
        self.assertContains(
            page,
            f'href="{reverse("church:settings", kwargs={"section": "details"})}" '
            'aria-label="Settings"',
        )
        self.client.force_login(make_user(roles=["pastoral_staff"]))
        page = self.client.get(reverse("home"))
        self.assertContains(
            page, f'href="{reverse("worship:template_list")}" aria-label="Settings"'
        )
        self.client.force_login(make_user(roles=["church_member"]))
        self.assertNotContains(
            self.client.get(reverse("home")), 'aria-label="Settings"'
        )

    def test_a_settings_page_shows_the_menu_and_where_it_is(self):
        self.client.force_login(make_administrator())
        page = self.client.get(reverse("worship:template_list"))
        self.assertContains(
            page, '<nav class="chord-settings-menu" aria-label="Settings">'
        )
        self.assertContains(page, "Worship · Services")
        self.assertContains(
            page,
            f'<a href="{reverse("worship:template_list")}" aria-current="page">'
            "Service templates</a>",
        )
        # The open category holds the current page; the others are closed.
        content = page.content.decode()
        self.assertEqual(content.count("<details open>"), 1)
        self.assertIn(f'href="{reverse("home")}" class="chord-back-link"', content)
        self.assertIn('<h1 class="h3 mb-3">Settings</h1>', content)
        self.assertIn('<h2 class="h3 mb-0">Service templates</h2>', content)

    def test_every_settings_page_shows_the_menu(self):
        self.client.force_login(make_administrator())
        menu = menu_for(make_administrator())
        for page in menu.pages:
            with self.subTest(page.label):
                response = self.client.get(page.url)
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, "chord-settings-menu")
                self.assertNotContains(response, 'class="nav nav-tabs')

    def test_a_settings_list_form_sits_in_the_hub(self):
        self.client.force_login(make_administrator())
        page = self.client.get(reverse("occasions:types_create"))
        self.assertContains(page, "Teams and occasions")
        self.assertContains(page, '<h2 class="h3 mb-3">Add occasion type</h2>')

    def test_the_setup_wizard_stays_outside_the_hub(self):
        from apps.church.models import ChurchProfile

        ChurchProfile.objects.update(setup_completed=False)
        self.client.force_login(make_administrator())
        page = self.client.get(reverse("church:setup", kwargs={"section": "details"}))
        self.assertNotContains(page, "chord-settings-menu")

    def test_other_pages_have_no_hub(self):
        self.client.force_login(make_administrator())
        self.assertNotContains(self.client.get(reverse("home")), "chord-settings-menu")

    def test_the_songs_more_menu_opens_worship_settings(self):
        self.client.force_login(make_user(roles=["worship_leader"]))
        page = self.client.get(reverse("songs:list"))
        self.assertContains(page, ">Worship settings</a>")
        self.client.force_login(
            make_user(roles=["team_member"], perms=["songs.view_song"])
        )
        page = self.client.get(reverse("songs:list"))
        self.assertNotContains(page, "Worship settings")
        self.assertNotContains(page, ">More</button>")
