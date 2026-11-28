"""UI/UX Phase 4 (28 Nov 2026): the Services and Bookings screens. UI-UX-Master-Plan.md §10."""

from django.test import TestCase
from django.urls import reverse

from apps.core.testing import (
    complete_setup,
    make_occasion,
    make_occasion_type,
    make_user,
)


class BookingScreenTests(TestCase):
    def setUp(self):
        complete_setup()
        self.pastor = make_user(roles=["pastoral_staff"])
        self.client.force_login(self.pastor)

    def test_the_list_has_a_segmented_filter_and_booking_rows(self):
        occasion = make_occasion(
            make_occasion_type(name="Garden blessing"), occasion_for="Ana and Ben"
        )
        page = self.client.get(reverse("occasions:list"))
        self.assertContains(page, 'class="chord-seg"')
        self.assertContains(page, 'aria-current="page">Upcoming</a>')
        self.assertContains(page, "chord-row")
        self.assertContains(page, "chord-date")
        self.assertContains(
            page,
            f'href="{reverse("occasions:detail", kwargs={"public_id": occasion.public_id})}"',
        )
        self.assertContains(page, "Garden blessing: Ana and Ben")

    def test_an_empty_list_offers_to_book(self):
        page = self.client.get(reverse("occasions:list"))
        self.assertContains(page, "chord-empty")
        self.assertContains(page, "No occasions are booked")
        if self.pastor.has_perm("occasions.add_occasion"):
            self.assertContains(page, f'href="{reverse("occasions:create")}"')

    def test_a_search_with_no_result_says_so(self):
        page = self.client.get(reverse("occasions:list"), {"q": "zzz"})
        self.assertContains(page, "Nothing matches your search")

    def test_the_booking_page_has_a_record_header_and_details(self):
        occasion = make_occasion(
            make_occasion_type(name="Home blessing"), occasion_for="Lia"
        )
        page = self.client.get(
            reverse("occasions:detail", kwargs={"public_id": occasion.public_id})
        )
        self.assertContains(page, "chord-record")
        self.assertContains(page, 'class="chord-dl"')
        self.assertContains(page, "Home blessing: Lia")

    def test_the_booking_form_is_in_sections(self):
        if not self.pastor.has_perm("occasions.add_occasion"):
            self.skipTest("this role can't book")
        make_occasion_type()
        page = self.client.get(reverse("occasions:create"))
        for legend in ("The service", "When", "Where and who", "Notes"):
            self.assertContains(page, f"<legend>{legend}</legend>")
        self.assertContains(page, 'name="occasion_type"')
        self.assertContains(page, 'name="occasion_for"')
