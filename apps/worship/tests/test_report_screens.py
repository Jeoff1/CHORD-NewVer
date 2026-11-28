"""UI/UX Phase 10 (28 Nov 2026): settings and reports screens. UI-UX-Master-Plan.md §16. Real figures
only; no invented metrics."""

from django.test import TestCase
from django.urls import reverse

from apps.core.testing import complete_setup, make_administrator


class ReportScreenTests(TestCase):
    def setUp(self):
        complete_setup()
        self.client.force_login(make_administrator())

    def test_reports_are_cards(self):
        page = self.client.get(reverse("worship:reports"))
        if b"chord-report-cards" in page.content:
            self.assertContains(page, "chord-report-card")
        else:
            self.assertContains(page, "No reports yet.")

    def test_a_report_has_the_switch_period_and_an_empty_state(self):
        page = self.client.get(reverse("worship:report_song_usage"))
        self.assertContains(page, 'class="card shadow-sm chord-period"')
        self.assertContains(page, "chord-empty")
        self.assertContains(page, f'href="{reverse("worship:reports")}"')

    def test_the_settings_menu_is_still_the_hub(self):
        page = self.client.get(reverse("accounts:appearance"))
        self.assertContains(page, "chord-settings-menu")
