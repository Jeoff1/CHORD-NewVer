"""The lineup song page: the chord sheet in the service key, transposed on
the server and re-rendered with htmx; the practise-along toggle; pending
sheets; how many lineup songs have a sheet; and the keys a song was sung in
(Design-Decisions, Phase 7). Sheet text is public domain or made up."""

import datetime

from django.test import TestCase
from django.urls import reverse

from apps.core.testing import (
    HYMN_SHEET,
    complete_setup,
    make_chord_sheet,
    make_lineup,
    make_service,
    make_song,
    make_user,
)
from apps.songs import sheets
from apps.worship import lineups
from apps.worship.models import Lineup

DAY = datetime.timedelta(days=1)


def song_url(item):
    return reverse(
        "worship:lineup_song",
        kwargs={"public_id": item.lineup.service.public_id, "pk": item.pk},
    )


class LineupSongTestCase(TestCase):
    def setUp(self):
        complete_setup()
        self.leader = make_user(roles=["worship_leader"])
        self.pastor = make_user(roles=["pastoral_staff"])
        self.member = make_user(roles=["team_member"])
        self.other_member = make_user(roles=["team_member"])
        self.service = make_service()
        self.hymn = make_song(title="Amazing Grace", artist="John Newton")
        self.other = make_song(title="Made Up Song")
        self.lineup = make_lineup(self.service, [self.hymn, self.other], keys=["A"])
        self.item = self.lineup.items.get(song=self.hymn)
        make_chord_sheet(self.hymn)  # written in G

    def get(self, user, item=None, **params):
        self.client.force_login(user)
        return self.client.get(song_url(item or self.item), params)


class ViewerTests(LineupSongTestCase):
    def test_everyone_who_sees_the_lineup_gets_the_sheet_in_the_service_key(self):
        for user in (self.member, self.leader, self.pastor):
            page = self.get(user)
            self.assertContains(page, "Service key A")
            self.assertContains(page, ">A/C#<")  # G/B in G, shown in A
            self.assertNotContains(page, ">G/B<")
            self.assertContains(page, "In A.")

    def test_without_a_service_key_the_sheets_own_key(self):
        self.item.key = ""
        self.item.save()
        page = self.get(self.member)
        self.assertContains(page, "shown in the sheet's key, G")
        self.assertContains(page, ">G/B<")

    def test_a_key_change_rerenders_only_the_sheet_on_the_server(self):
        self.client.force_login(self.member)
        response = self.client.get(
            song_url(self.item), {"key": "Bb"}, HTTP_HX_REQUEST="true"
        )
        self.assertTemplateUsed(response, "songs/includes/chord_sheet.html")
        self.assertTemplateNotUsed(response, "worship/lineup_song.html")
        self.assertContains(response, ">Bb/D<")
        self.assertContains(response, "your own view; the key for everyone is A")

    def test_up_and_down_a_semitone(self):
        page = self.get(self.member)
        self.assertContains(page, "?key=Bb")  # up from A
        self.assertContains(page, "?key=Ab")  # down from A

    def test_capo_and_nashville_numbers(self):
        capo = self.get(self.member, capo="2")
        self.assertContains(capo, "Capo 2: play G shapes.")
        self.assertContains(capo, ">G/B<")
        numbers = self.get(self.member, numbers="1")
        self.assertContains(numbers, ">1/3<")
        self.assertContains(numbers, "Numbers are in A.")

    def test_nashville_numbers_in_a_minor_key_say_where_they_count_from(self):
        minor = make_song(title="Made Up Lament")
        make_chord_sheet(minor, chordpro="[Am]La [Dm]la [E7]la\n", key="Am")
        item = self.lineup.items.create(song=minor, position=5, key="Am")
        page = self.get(self.member, item, numbers="1")
        self.assertContains(page, "Numbers count from the minor key (1 = A minor).")
        self.assertContains(page, ">1m<")
        self.assertContains(page, ">4m<")
        major = self.get(self.member, numbers="1")
        self.assertNotContains(major, "Numbers count from the minor key")
        self.assertContains(major, "Numbers are in A.")

    def test_the_practise_along_toggle_needs_the_recordings_key(self):
        page = self.get(self.member)
        self.assertNotContains(page, "Practise along")
        self.hymn.recording_key = "Bb"
        self.hymn.save()
        page = self.get(self.member)
        self.assertContains(page, "Practise along (Bb, the recording's key)")
        practise = self.get(self.member, practise="1")
        self.assertContains(practise, "In Bb, the recording's key")
        self.assertContains(practise, ">Bb/D<")

    def test_bad_choices_fall_back(self):
        page = self.get(self.member, key="H", capo="lots", numbers="maybe")
        self.assertContains(page, ">A/C#<")

    def test_team_members_dont_see_an_unconfirmed_lineup_song(self):
        self.lineup.status = Lineup.Status.DRAFT
        self.lineup.save()
        self.assertEqual(self.get(self.member).status_code, 404)
        self.assertEqual(self.get(self.leader).status_code, 200)

    def test_needs_the_view_lineup_permission_and_the_module(self):
        self.assertEqual(self.get(make_user()).status_code, 403)
        complete_setup(disabled_modules=["worship"])
        self.assertEqual(self.get(self.leader).status_code, 404)

    def test_a_sheet_is_shown_only_with_the_view_permission(self):
        viewer = make_user(perms=["worship.view_lineup"])
        page = self.get(viewer)
        self.assertEqual(page.status_code, 200)
        self.assertNotContains(page, ">A/C#<")
        self.assertContains(page, "This song has a chord sheet.")


class PendingSheetTests(LineupSongTestCase):
    def test_a_team_member_pastes_and_only_they_and_planners_see_it_waiting(self):
        other_item = self.lineup.items.get(song=self.other)
        page = self.get(self.member, other_item)
        self.assertContains(page, "No chord sheet yet.")
        self.assertContains(page, "Paste a chord sheet")
        self.assertContains(page, "ultimate-guitar.com/search.php")
        sheets.save(self.other, self.member, HYMN_SHEET, "G")
        self.assertContains(
            self.get(self.member, other_item),
            "Your chord sheet is waiting for approval.",
        )
        hidden = self.get(self.other_member, other_item)
        self.assertNotContains(hidden, "waiting for approval")
        self.assertNotContains(hidden, "Amazing ")
        self.assertContains(hidden, "No chord sheet yet.")
        leader_page = self.get(self.leader, other_item)
        self.assertContains(leader_page, "is waiting for approval")
        self.assertContains(leader_page, ">Approve<")
        sheets.approve(self.other.chord_sheets.get(), self.leader)
        # No service key for this song: shown in the sheet's own key.
        self.assertContains(self.get(self.other_member, other_item), ">G/B<")


class SheetCountTests(LineupSongTestCase):
    def test_the_lineup_shows_how_many_songs_have_a_sheet(self):
        self.client.force_login(self.member)
        page = self.client.get(
            reverse("worship:lineup", kwargs={"public_id": self.service.public_id})
        )
        self.assertContains(page, "1 of 2 songs have a chord sheet.")
        self.assertContains(page, "Every song needs one now that it is confirmed.")
        self.assertContains(page, "Needs a chord sheet", count=1)
        card = self.client.get(
            reverse("worship:service", kwargs={"public_id": self.service.public_id})
        )
        self.assertContains(card, "1 of 2 songs have a chord sheet.")
        self.assertContains(card, song_url(self.item))

    def test_pending_sheets_dont_count(self):
        sheets.save(self.other, self.member, HYMN_SHEET, "G")
        self.client.force_login(self.leader)
        page = self.client.get(
            reverse("worship:lineup", kwargs={"public_id": self.service.public_id})
        )
        self.assertContains(page, "1 of 2 songs have a chord sheet.")

    def test_a_draft_shows_no_chord_sheet_without_needing_it(self):
        self.lineup.status = Lineup.Status.DRAFT
        self.lineup.save()
        self.client.force_login(self.leader)
        page = self.client.get(
            reverse("worship:lineup", kwargs={"public_id": self.service.public_id})
        )
        self.assertContains(page, ">No chord sheet<")
        self.assertNotContains(page, "Every song needs one")


class KeyHistoryTests(LineupSongTestCase):
    """When choosing a lineup song's key, the keys it was sung in before."""

    def earlier(self, days, key, **fields):
        service = make_service(starts_at=self.service.starts_at - days * DAY, **fields)
        confirmed = fields.pop("confirmed", True) if "confirmed" in fields else True
        return make_lineup(service, [self.hymn], keys=[key], confirmed=confirmed)

    def test_confirmed_lineups_of_earlier_services_most_recent_first(self):
        self.earlier(70, "F")
        self.earlier(14, "G")
        self.earlier(35, "Ab")
        self.earlier(21, "")  # sung with no key set
        make_lineup(
            make_service(starts_at=self.service.starts_at - 7 * DAY),
            [self.hymn],
            keys=["C"],
            confirmed=False,
        )
        self.earlier(28, "D", is_cancelled=True)
        make_lineup(
            make_service(starts_at=self.service.starts_at + 7 * DAY),
            [self.hymn],
            keys=["E"],
        )
        self.assertEqual(
            [key for key, _ in lineups.key_history(self.item)], ["G", "Ab", "F"]
        )

    def test_the_key_page_shows_them(self):
        lineup = self.earlier(14, "G")
        self.client.force_login(self.leader)
        page = self.client.get(
            reverse(
                "worship:lineup_item",
                kwargs={"public_id": self.service.public_id, "pk": self.item.pk},
            )
        )
        day = lineup.service.local_date
        self.assertContains(
            page, f"Sung before in: G ({day:%b} {day.day}, {day.year})."
        )

    def test_a_song_never_sung_says_so(self):
        self.client.force_login(self.leader)
        page = self.client.get(
            reverse(
                "worship:lineup_item",
                kwargs={"public_id": self.service.public_id, "pk": self.item.pk},
            )
        )
        self.assertContains(page, "Not sung in a confirmed lineup before")


class KeptMarkNoteTests(LineupSongTestCase):
    NOTE = "Some marks were kept as written and aren't transposed."

    def setUp(self):
        super().setUp()
        self.hymn.chord_sheets.update(chordpro="[G]Made up [*Zz9]words [C]here\n")

    def test_the_note_shows_when_the_key_differs_from_the_sheets(self):
        page = self.get(self.member)  # service key A, sheet in G
        self.assertContains(page, self.NOTE)
        self.assertContains(page, 'class="chord kept"')
        self.assertContains(page, ">Zz9<")

    def test_no_note_in_the_sheets_own_key(self):
        page = self.get(self.member, key="G")
        self.assertNotContains(page, self.NOTE)
        self.assertContains(page, 'class="chord kept"')  # still shown apart

    def test_no_note_without_kept_marks(self):
        self.hymn.chord_sheets.update(chordpro="[G]Made up [N.C.]words [C]here\n")
        page = self.get(self.member)
        self.assertNotContains(page, self.NOTE)
        self.assertNotContains(page, 'class="chord kept"')
