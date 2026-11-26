"""The landing page: what a visitor who isn't signed in sees at the home
address. Since Phase 9B it is the platform's page, not one church's
(decision 0014): it offers every Module and uses the neutral wording."""

from django.contrib.staticfiles import finders
from django.test import TestCase
from django.urls import reverse

from apps.church.views import SHOWCASE_SIZE
from apps.core.testing import complete_setup, make_church, make_user

HOME = reverse("home")


class LandingPageTests(TestCase):
    def test_a_visitor_sees_the_landing_page_with_a_way_to_sign_in(self):
        complete_setup(name="Grace Fellowship")
        response = self.client.get(HOME)
        self.assertTemplateUsed(response, "church/landing.html")
        self.assertContains(response, f'href="{reverse("accounts:login")}"')
        # The platform's page names no church.
        self.assertNotContains(response, "Grace Fellowship")
        self.assertContains(response, "Worship planning · CHORD")

    def test_a_signed_in_person_sees_the_dashboard(self):
        complete_setup()
        self.client.force_login(make_user())
        response = self.client.get(HOME)
        self.assertTemplateUsed(response, "church/dashboard.html")
        self.assertTemplateNotUsed(response, "church/landing.html")

    def test_the_wording_is_neutral_whatever_a_church_calls_things(self):
        complete_setup(
            labels={
                "pastor": {"singular": "Elder", "plural": "Elders"},
                "lineup": {"singular": "Set List", "plural": "Set Lists"},
            }
        )
        response = self.client.get(HOME)
        self.assertContains(response, "Your pastor reviews and confirms it")
        self.assertNotContains(response, "set list")

    def test_one_churchs_switched_off_modules_are_still_offered(self):
        complete_setup(disabled_modules=["teams", "occasions", "announcements"])
        response = self.client.get(HOME)
        self.assertContains(response, "Team roster")
        self.assertContains(response, "Calendar and occasions")
        self.assertContains(response, "Chord sheets in any key")

    def test_switched_on_modules_are_offered(self):
        complete_setup()
        response = self.client.get(HOME)
        self.assertContains(response, "Team roster")
        self.assertContains(response, "Calendar and occasions")
        self.assertContains(response, "<h3>Announcements</h3>", html=False)


class LandingRedesignTests(TestCase):
    """The redesign (26-27 Nov 2026): the Phase 9C steps, the ways in, the
    page's own assets, and nothing of it on signed-in pages."""

    def setUp(self):
        complete_setup()

    def test_it_shows_the_four_planning_steps_of_phase_9c(self):
        response = self.client.get(HOME)
        for step in ("Theme", "Praise Team", "Song Lineup", "Confirm"):
            self.assertContains(response, step)
        self.assertContains(response, "Then the team rehearses")
        self.assertContains(response, "Optional")

    def test_the_ways_in_use_the_existing_pages(self):
        response = self.client.get(HOME)
        directory = reverse("churches:directory")
        self.assertContains(response, f'href="{reverse("accounts:login")}"')
        self.assertContains(response, f'href="{reverse("accounts:signup")}"')
        self.assertContains(response, f'href="{directory}">Explore churches')
        self.assertContains(response, f'href="{directory}">Churches')
        # Registering a church is reached from sign-in, not from this page.
        self.assertNotContains(response, reverse("churches:register"))

    def test_it_loads_its_own_stylesheet_script_and_images(self):
        response = self.client.get(HOME)
        for path in (
            "css/landing.css",
            "church/landing.js",
            "images/landing/chord-logo.webp",
            "images/landing/chord-logo-gold.webp",
            "images/landing/hero-worship.webp",
            "images/landing/rehearsal-ambient.webp",
        ):
            self.assertContains(response, path)
        for path in (
            "css/landing.css",
            "church/landing.js",
            "images/landing/chord-logo.webp",
            "images/landing/chord-logo.png",
            "images/landing/chord-logo-gold.webp",
            "images/landing/chord-logo-gold.png",
            "images/landing/hero-worship.webp",
            "images/landing/hero-worship.jpg",
            "images/landing/rehearsal-ambient.webp",
            "images/landing/rehearsal-ambient.jpg",
            "images/landing/SOURCES.md",
        ):
            self.assertTrue(finders.find(path), path)

    def test_every_image_is_decorative_or_labelled(self):
        content = self.client.get(HOME).content.decode()
        self.assertNotRegex(content, r'<img (?![^>]*alt="")')
        self.assertContains(self.client.get(HOME), 'aria-label="CHORD, home"')

    def test_the_intro_shows_once_a_session_and_can_never_block_the_page(self):
        content = self.client.get(HOME).content.decode()
        self.assertIn('id="lp-intro" aria-hidden="true"', content)
        self.assertIn("Bringing worship together", content)
        self.assertIn('sessionStorage.getItem("chord-intro-seen")', content)
        self.assertIn("800 - (Date.now() - start)", content)  # the approved minimum
        self.assertIn("reduced ? 0", content)  # none with reduced motion
        self.assertIn("setTimeout(hide, 4000)", content)  # the script's cap
        css = open(finders.find("css/landing.css"), encoding="utf-8").read()
        self.assertIn(".lp-intro { display: none; }", css)  # never without the script
        self.assertIn("lp-intro-failsafe .5s ease 6s forwards", css)

    def test_signed_in_pages_do_not_load_the_landing_styles(self):
        self.client.force_login(make_user())
        response = self.client.get(HOME)
        self.assertNotContains(response, "css/landing.css")
        self.assertNotContains(response, "church/landing.js")


class ChurchShowcaseTests(TestCase):
    """United in Worship: public churches that finished setting up, newest
    first, at most SHOWCASE_SIZE; only what the directory already shows."""

    def setUp(self):
        complete_setup()

    def test_a_public_church_that_finished_setup_is_shown_with_its_page(self):
        church = make_church(
            "Hope Church", address="12 Mabini Street\nQuezon City", setup_completed=True
        )
        response = self.client.get(HOME)
        self.assertContains(response, "United in Worship")
        self.assertContains(response, "Hope Church")
        self.assertContains(response, "12 Mabini Street, Quezon City")
        self.assertContains(
            response, f'href="{reverse("churches:home", kwargs={"slug": church.slug})}"'
        )
        self.assertContains(
            response, f'href="{reverse("churches:directory")}">Explore all churches'
        )

    def test_private_and_unfinished_churches_are_left_out(self):
        make_church("Hidden Church", show_in_directory=False, setup_completed=True)
        make_church("Unfinished Church", setup_completed=False)
        response = self.client.get(HOME)
        self.assertNotContains(response, "Hidden Church")
        self.assertNotContains(response, "Unfinished Church")
        self.assertContains(response, "No churches are listed here yet.")
        self.assertNotContains(response, "Explore all churches")

    def test_contact_details_never_show(self):
        make_church(
            "Hope Church",
            setup_completed=True,
            phone="0917 555 0100",
            email="office@hope.example",
            website="https://hope.example",
        )
        response = self.client.get(HOME)
        self.assertContains(response, "Hope Church")
        for private in ("0917 555 0100", "office@hope.example", "hope.example"):
            self.assertNotContains(response, private)

    def test_newest_first_and_at_most_the_showcase_size(self):
        for n in range(SHOWCASE_SIZE + 1):
            make_church(f"Church {n:02d}", setup_completed=True)
        showcase = self.client.get(HOME).context["showcase"]
        self.assertEqual(len(showcase), SHOWCASE_SIZE)
        self.assertEqual(showcase[0].name, f"Church {SHOWCASE_SIZE:02d}")
        self.assertNotIn("Church 00", [listed.name for listed in showcase])

    def test_a_church_without_a_logo_gets_the_fallback(self):
        make_church("No Logo Church", setup_completed=True)
        logo = make_church("Logo Church", setup_completed=True)
        logo.logo.name = "church/example-logo.png"
        logo.save()
        response = self.client.get(HOME)
        self.assertContains(response, "lp-church__logo--none")
        self.assertContains(response, "church/example-logo.png")

    def test_the_carousel_arrows_start_hidden_for_the_script_to_show(self):
        make_church("Hope Church", setup_completed=True)
        content = self.client.get(HOME).content.decode()
        self.assertRegex(content, r'id="lp-church-prev"[^>]*hidden')
        self.assertRegex(content, r'id="lp-church-next"[^>]*hidden')
        self.assertIn('id="lp-church-track" tabindex="0"', content)
