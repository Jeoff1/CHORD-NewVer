"""UI/UX Phase 11 (28 Nov 2026): the final consistency, accessibility and animation audit.
UI-UX-Master-Plan.md §17 and Animation-Plan.md."""

import pathlib
import re

from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from apps.core.testing import complete_setup, make_user

ROOT = pathlib.Path(__file__).resolve().parents[3]
REDESIGN_CSS = ("components.css", "planning.css", "account.css")


class AuditTests(SimpleTestCase):
    def test_every_redesign_stylesheet_stops_motion_when_asked(self):
        for name in REDESIGN_CSS:
            css = (ROOT / "static" / "css" / name).read_text(encoding="utf-8")
            with self.subTest(name=name):
                self.assertIn("prefers-reduced-motion: reduce", css)

    def test_no_bootstrap_badges_are_left_on_the_redesigned_screens(self):
        # The retired Member Directory and Households keep their old look.
        left = [
            str(path.relative_to(ROOT))
            for folder in ("apps", "templates")
            for path in (ROOT / folder).rglob("*.html")
            if "members" not in path.parts
            and re.search(r'class="badge text-bg', path.read_text(encoding="utf-8"))
        ]
        self.assertEqual(left, [])

    def test_no_bootstrap_nav_pills_are_left(self):
        left = [
            str(path.relative_to(ROOT))
            for folder in ("apps", "templates")
            for path in (ROOT / folder).rglob("*.html")
            if "members" not in path.parts
            and "nav-pills" in path.read_text(encoding="utf-8")
        ]
        self.assertEqual(left, [])


class ErrorPageTests(TestCase):
    def test_the_404_page_uses_the_shared_look(self):
        complete_setup()
        self.client.force_login(make_user(roles=["church_member"]))
        page = self.client.get("/no-such-page/")
        self.assertEqual(page.status_code, 404)
        self.assertContains(page, "chord-error", status_code=404)
        self.assertContains(page, "Page not found", status_code=404)
        self.assertContains(page, f'href="{reverse("home")}"', status_code=404)
