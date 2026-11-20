"""Chord sheets: who may add one, pending and approval, the sheet form with
its conversion and ChordPro check, Find chords, and full lyrics only for
people who plan (Design-Decisions, Phase 7; workflow review F13).

Chord sheet text here is public domain or made up (AGENTS.md)."""

from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import Role
from apps.audit.models import AuditEvent
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
from apps.songs.models import ChordSheet, Song

Status = ChordSheet.Status


def form_url(song, next_url=""):
    url = reverse("songs:chordsheet", kwargs={"public_id": song.public_id})
    return f"{url}?next={next_url}" if next_url else url


def detail_url(song):
    return reverse("songs:detail", kwargs={"public_id": song.public_id})


class SheetTestCase(TestCase):
    def setUp(self):
        complete_setup()
        self.leader = make_user(roles=["worship_leader"])
        self.pastor = make_user(roles=["pastoral_staff"])
        self.member = make_user(roles=["team_member"], first_name="Tess")
        self.other_member = make_user(roles=["team_member"])
        self.song = make_song(
            title="Amazing Grace",
            lyrics="Made-up words for a test",
            lyrics_status=Song.LyricsStatus.FOUND,
        )
        self.service = make_service()

    def confirm_in_lineup(self, song=None):
        return make_lineup(self.service, [song or self.song], keys=["A"])


class RuleTests(SheetTestCase):
    def test_people_who_approve_add_a_sheet_to_any_pool_song_approved_at_once(self):
        for user in (self.leader, self.pastor):
            song = make_song()
            self.assertTrue(sheets.may_add(user, song))
            sheet = sheets.save(song, user, HYMN_SHEET, "G")
            self.assertEqual(sheet.status, Status.APPROVED)
            self.assertEqual(sheet.approved_by, user)

    def test_a_second_save_replaces_the_approved_sheet(self):
        sheets.save(self.song, self.leader, HYMN_SHEET, "G")
        sheets.save(self.song, self.pastor, "[A]Changed\n", "A")
        sheet = ChordSheet.objects.get(song=self.song)
        self.assertEqual((sheet.key, sheet.chordpro), ("A", "[A]Changed\n"))

    def test_a_team_member_may_paste_only_for_a_confirmed_lineup_song(self):
        self.assertFalse(sheets.may_add(self.member, self.song))
        with self.assertRaises(sheets.SheetRefused):
            sheets.save(self.song, self.member, HYMN_SHEET, "G")
        make_lineup(self.service, [self.song], confirmed=False)
        self.assertFalse(sheets.may_add(self.member, self.song))  # a draft
        self.service.lineup.status = "confirmed"
        self.service.lineup.save()
        self.assertTrue(sheets.may_add(self.member, self.song))
        sheet = sheets.save(self.song, self.member, HYMN_SHEET, "G")
        self.assertEqual(sheet.status, Status.PENDING)
        self.assertEqual(sheet.added_by, self.member)

    def test_not_for_a_cancelled_service_or_a_song_with_a_sheet(self):
        self.service.is_cancelled = True
        self.service.save()
        self.confirm_in_lineup()
        self.assertFalse(sheets.may_add(self.member, self.song))
        service = make_service()
        make_lineup(service, [self.song])
        self.assertTrue(sheets.may_add(self.member, self.song))
        make_chord_sheet(self.song)
        self.assertFalse(sheets.may_add(self.member, self.song))

    def test_a_pending_sheet_is_hidden_from_other_team_members(self):
        self.confirm_in_lineup()
        sheets.save(self.song, self.member, HYMN_SHEET, "G")
        self.assertEqual(len(sheets.pending_for(self.song, self.member)), 1)
        self.assertEqual(sheets.pending_for(self.song, self.other_member), [])
        self.assertEqual(len(sheets.pending_for(self.song, self.leader)), 1)
        self.assertIsNone(sheets.approved_sheet(self.song))

    def test_the_leader_or_the_pastor_approves(self):
        self.confirm_in_lineup()
        for approver in (self.leader, self.pastor):
            pending = sheets.save(self.song, self.member, HYMN_SHEET, "G")
            sheets.approve(pending, approver)
            pending.refresh_from_db()
            self.assertEqual(pending.status, Status.APPROVED)
            self.assertEqual(pending.approved_by, approver)
            pending.delete()

    def test_approving_is_a_permission_not_a_role(self):
        self.confirm_in_lineup()
        pending = sheets.save(self.song, self.member, HYMN_SHEET, "G")
        with self.assertRaises(sheets.SheetRefused):
            sheets.approve(pending, self.other_member)
        elder = make_user(perms=["songs.approve_chordsheet"])
        sheets.approve(pending, elder)
        role = Role.objects.get(key="worship_leader")
        role.permissions.remove(*role.permissions.filter(codename="approve_chordsheet"))
        leader = type(self.leader).objects.get(pk=self.leader.pk)
        self.assertFalse(sheets.may_approve(leader))

    def test_only_one_approved_sheet_per_song(self):
        self.confirm_in_lineup()
        pending = sheets.save(self.song, self.member, HYMN_SHEET, "G")
        make_chord_sheet(self.song)
        with self.assertRaisesMessage(sheets.SheetRefused, "already has an approved"):
            sheets.approve(pending, self.leader)

    def test_discarding_a_pending_sheet(self):
        self.confirm_in_lineup()
        pending = sheets.save(self.song, self.member, HYMN_SHEET, "G")
        with self.assertRaises(sheets.SheetRefused):
            sheets.discard(pending, self.member)
        sheets.discard(pending, self.leader)
        self.assertFalse(ChordSheet.objects.exists())
        approved = make_chord_sheet(self.song)
        with self.assertRaisesMessage(sheets.SheetRefused, "edited, not discarded"):
            sheets.discard(approved, self.leader)

    def test_the_text_is_checked_converted_and_keyed(self):
        with self.assertRaisesMessage(sheets.SheetRefused, "isn't a chord"):
            sheets.save(self.song, self.leader, "[H]bad\n", "G")
        sheet = sheets.save(self.song, self.leader, "G       C\nMade up words\n", "G")
        self.assertEqual(sheet.chordpro, "[G]Made up [C]words\n")
        sheet = sheets.save(self.song, self.leader, "{key: D}\n[D]La\n", "")
        self.assertEqual(sheet.key, "D")
        with self.assertRaisesMessage(sheets.SheetRefused, "Choose the key"):
            sheets.save(self.song, self.leader, "[D]La\n", "")
        with self.assertRaisesMessage(sheets.SheetRefused, "says it is in D"):
            sheets.save(self.song, self.leader, "{key: D}\n[D]La\n", "E")

    def test_find_chords_links_open_searches_and_fetch_nothing(self):
        links = dict(sheets.find_chords_links(self.song))
        self.assertTrue(
            links["Ultimate Guitar"].startswith(
                "https://www.ultimate-guitar.com/search.php?"
            )
        )
        self.assertIn("Amazing+Grace", links["Ultimate Guitar"])
        self.assertIn("worshiptogether.com", links["Worship Together"])
        self.assertIn("chords", links["The web"])


class SheetFormTests(SheetTestCase):
    def test_the_leader_adds_a_sheet_and_it_is_audited_without_the_text(self):
        self.client.force_login(self.leader)
        page = self.client.get(form_url(self.song))
        self.assertContains(page, "Ultimate Guitar")
        response = self.client.post(
            form_url(self.song), {"key": "G", "chordpro": HYMN_SHEET, "action": "save"}
        )
        self.assertRedirects(response, detail_url(self.song))
        sheet = ChordSheet.objects.get()
        self.assertEqual(sheet.status, Status.APPROVED)
        event = AuditEvent.objects.get(object_id=str(sheet.pk))
        self.assertEqual(event.action, AuditEvent.Action.CREATED)
        self.assertNotIn("Amazing grace", str(event.changes))
        self.assertNotIn("[G]", str(event.changes))

    def test_convert_shows_the_chordpro_before_saving(self):
        self.client.force_login(self.leader)
        response = self.client.post(
            form_url(self.song),
            {"key": "G", "chordpro": "G       C\nMade up words\n", "action": "convert"},
        )
        self.assertContains(response, "Converted to ChordPro")
        self.assertContains(response, "[G]Made up [C]words")
        self.assertFalse(ChordSheet.objects.exists())

    def test_invalid_chordpro_is_refused_with_a_message(self):
        self.client.force_login(self.leader)
        response = self.client.post(
            form_url(self.song),
            {"key": "G", "chordpro": "[G]ok\n[Zx]no\n", "action": "save"},
        )
        self.assertContains(response, "Line 2: “Zx” isn&#x27;t a chord.")
        self.assertFalse(ChordSheet.objects.exists())

    def test_a_team_members_paste_waits_and_goes_back_to_next(self):
        self.confirm_in_lineup()
        self.client.force_login(self.member)
        back = "/worship/"
        page = self.client.get(form_url(self.song, back))
        self.assertContains(page, "Send for approval")
        response = self.client.post(
            form_url(self.song),
            {"key": "G", "chordpro": HYMN_SHEET, "action": "save", "next": back},
        )
        self.assertRedirects(response, back, fetch_redirect_response=False)
        self.assertEqual(ChordSheet.objects.get().status, Status.PENDING)

    def test_an_outside_next_is_ignored(self):
        self.client.force_login(self.leader)
        response = self.client.post(
            form_url(self.song),
            {
                "key": "G",
                "chordpro": HYMN_SHEET,
                "action": "save",
                "next": "https://example.com/",
            },
        )
        self.assertRedirects(response, detail_url(self.song))

    def test_a_team_member_without_a_confirmed_lineup_is_refused(self):
        self.client.force_login(self.member)
        self.assertEqual(self.client.get(form_url(self.song)).status_code, 403)
        self.assertEqual(
            self.client.post(
                form_url(self.song), {"key": "G", "chordpro": HYMN_SHEET}
            ).status_code,
            403,
        )

    def test_approve_and_discard_pages(self):
        self.confirm_in_lineup()
        pending = sheets.save(self.song, self.member, HYMN_SHEET, "G")
        approve = reverse("songs:chordsheet_approve", kwargs={"pk": pending.pk})
        discard = reverse("songs:chordsheet_discard", kwargs={"pk": pending.pk})
        for user in (self.member, self.other_member):
            self.client.force_login(user)
            self.assertEqual(self.client.post(approve).status_code, 403)
            self.assertEqual(self.client.post(discard).status_code, 403)
        self.client.force_login(self.pastor)
        self.client.post(approve)
        pending.refresh_from_db()
        self.assertEqual(pending.status, Status.APPROVED)
        second = sheets.save(make_song(), self.leader, HYMN_SHEET, "G")
        response = self.client.post(
            reverse("songs:chordsheet_discard", kwargs={"pk": second.pk}), follow=True
        )
        self.assertContains(response, "edited, not discarded")


class SongPageTests(SheetTestCase):
    def test_the_sheet_on_the_song_page_with_the_viewer(self):
        self.song.recording_key = "Bb"
        self.song.save()
        make_chord_sheet(self.song)
        self.client.force_login(self.leader)
        page = self.client.get(detail_url(self.song))
        self.assertContains(page, "Amazing ")
        self.assertContains(page, ">G/B<")
        self.assertContains(page, "Edit the chord sheet")
        self.assertContains(page, "Practise along (Bb")
        transposed = self.client.get(
            detail_url(self.song), {"key": "A"}, HTTP_HX_REQUEST="true"
        )
        self.assertTemplateUsed(transposed, "songs/includes/chord_sheet.html")
        self.assertTemplateNotUsed(transposed, "songs/song_detail.html")
        self.assertContains(transposed, ">A/C#<")

    def test_without_a_sheet_find_chords_shows(self):
        self.client.force_login(self.leader)
        page = self.client.get(detail_url(self.song))
        self.assertContains(page, "No chord sheet yet.")
        self.assertContains(page, "ultimate-guitar.com/search.php")
        self.assertContains(page, 'target="_blank"')
        self.assertContains(page, "Add a chord sheet")

    def test_pending_sheets_offer_approval_to_people_who_approve(self):
        self.confirm_in_lineup()
        sheets.save(self.song, self.member, HYMN_SHEET, "G")
        self.client.force_login(self.leader)
        page = self.client.get(detail_url(self.song))
        self.assertContains(page, "is waiting for approval")
        self.assertContains(page, ">Approve<")


class LyricsTests(SheetTestCase):
    """Workflow review F13: full lyrics only for people who plan, by a
    permission."""

    def test_the_leader_and_the_pastor_see_the_lyrics(self):
        for user in (self.leader, self.pastor):
            self.client.force_login(user)
            self.assertContains(
                self.client.get(detail_url(self.song)), "Made-up words for a test"
            )

    def test_without_the_permission_the_lyrics_are_hidden(self):
        viewer = make_user(roles=["team_member"], perms=["songs.view_song"])
        self.client.force_login(viewer)
        page = self.client.get(detail_url(self.song))
        self.assertEqual(page.status_code, 200)
        self.assertNotContains(page, "Made-up words for a test")
        self.assertContains(page, "shown to the people who plan")


class DefaultRoleTests(TestCase):
    def holds(self, key, codename):
        return Role.objects.get(key=key).permissions.filter(codename=codename).exists()

    def test_default_roles(self):
        expected = {
            "worship_leader": {
                "view_lyrics",
                "view_chordsheet",
                "add_chordsheet",
                "approve_chordsheet",
            },
            "pastoral_staff": {
                "view_lyrics",
                "view_chordsheet",
                "add_chordsheet",
                "approve_chordsheet",
            },
            "team_member": {"view_chordsheet", "add_chordsheet"},
            "office_staff": set(),
        }
        for key, held in expected.items():
            for codename in (
                "view_lyrics",
                "view_chordsheet",
                "add_chordsheet",
                "approve_chordsheet",
            ):
                with self.subTest(role=key, permission=codename):
                    self.assertEqual(self.holds(key, codename), codename in held)


class ImportTests(SheetTestCase):
    """Importing a ChordPro file on the chord sheet form. Its text goes in
    the box for the person to check; nothing is saved until they save, and
    the file isn't kept. Content here is made up."""

    MADE_UP = (
        "{title: Made Up Song}\n"
        "{artist: Nobody Real}\n"
        "{tempo: 72}\n"
        "{key: Bb}\n"
        "{comment: Verse}\n"
        "[Bb]Words that [Eb]nobody [F]wrote\n"
    )

    def upload(self, name, content, **post):
        from django.core.files.uploadedfile import SimpleUploadedFile

        data = {"action": "import", "key": "", "chordpro": "", **post}
        data["import_file"] = SimpleUploadedFile(name, content)
        return self.client.post(form_url(self.song), data)

    def test_the_key_comes_from_the_key_directive(self):
        self.client.force_login(self.leader)
        response = self.upload("made-up.cho", self.MADE_UP.encode())
        self.assertContains(response, "Imported made-up.cho.")
        form = response.context["form"]
        self.assertEqual(form.initial["key"], "Bb")
        self.assertEqual(form.initial["chordpro"], self.MADE_UP)
        self.assertContains(response, '<option value="Bb" selected>')
        self.assertFalse(ChordSheet.objects.exists())  # nothing saved yet

    def test_the_short_k_directive_and_a_byte_order_mark(self):
        self.client.force_login(self.leader)
        content = "﻿{k: E}\r\n[E]Made up\r\n".encode("utf-8")
        response = self.upload("made-up.chopro", content)
        self.assertEqual(response.context["form"].initial["key"], "E")
        self.assertEqual(
            response.context["form"].initial["chordpro"], "{k: E}\n[E]Made up\n"
        )

    def test_a_file_without_a_key_keeps_the_chosen_one_or_asks(self):
        self.client.force_login(self.leader)
        response = self.upload("no-key.pro", b"[G]Made up words\n", key="G")
        self.assertEqual(response.context["form"].initial["key"], "G")
        response = self.upload("no-key.txt", b"[G]Made up words\n")
        self.assertEqual(response.context["form"].initial["key"], "")
        saved = self.client.post(
            form_url(self.song),
            {"key": "", "chordpro": "[G]Made up words\n", "action": "save"},
        )
        self.assertContains(saved, "Choose the key the sheet is written in.")

    def test_other_directives_stay_and_the_song_is_unchanged(self):
        self.client.force_login(self.leader)
        self.client.post(
            form_url(self.song),
            {"key": "Bb", "chordpro": self.MADE_UP, "action": "save"},
        )
        sheet = ChordSheet.objects.get()
        for line in (
            "{title: Made Up Song}",
            "{artist: Nobody Real}",
            "{tempo: 72}",
            "{comment: Verse}",
        ):
            self.assertIn(line, sheet.chordpro)
        self.song.refresh_from_db()
        self.assertEqual(
            (self.song.title, self.song.artist), ("Amazing Grace", "Test Artist")
        )
        self.assertNotIn("file", {f.name for f in ChordSheet._meta.get_fields()})

    def test_a_wrong_extension_is_refused(self):
        self.client.force_login(self.leader)
        response = self.upload("made-up.pdf", b"[G]Made up\n")
        self.assertContains(response, "Choose a ChordPro file: .cho, .chopro")
        self.assertEqual(response.context["form"].initial["chordpro"], "")

    def test_a_file_over_200_kb_is_refused(self):
        self.client.force_login(self.leader)
        response = self.upload("big.cho", b"[G]la\n" * 40000)
        self.assertContains(
            response, "The file is too large (234 KB; the most is 200 KB)."
        )

    def test_a_file_that_isnt_utf8_is_refused_clearly(self):
        self.client.force_login(self.leader)
        response = self.upload("latin.cho", "[G]Café made up\n".encode("latin-1"))
        self.assertContains(response, "The file isn&#x27;t UTF-8 text.")
        self.assertFalse(ChordSheet.objects.exists())

    def test_an_empty_or_missing_file(self):
        self.client.force_login(self.leader)
        self.assertContains(self.upload("empty.cho", b"  \n"), "The file is empty.")
        response = self.client.post(form_url(self.song), {"action": "import"})
        self.assertContains(response, "Choose a file to import.")

    def test_a_rhythm_line_imports_and_saves_and_transposes(self):
        self.client.force_login(self.leader)
        text = "{key: D}\nIntro: |D//G|////|D//G|////|\n[D]Made up [G]words\n"
        response = self.upload("intro.cho", text.encode())
        self.client.post(
            form_url(self.song),
            {
                "key": "D",
                "chordpro": response.context["form"].initial["chordpro"],
                "action": "save",
            },
        )
        sheet = ChordSheet.objects.get()
        self.assertIn("Intro: |[D]//[G]|////|[D]//[G]|////|", sheet.chordpro)
        page = self.client.get(detail_url(self.song), {"key": "E"})
        self.assertContains(page, ">A<")

    def test_a_team_members_import_stays_pending(self):
        self.confirm_in_lineup()
        self.client.force_login(self.member)
        response = self.upload("made-up.cho", self.MADE_UP.encode())
        self.assertEqual(response.context["form"].initial["key"], "Bb")
        self.client.post(
            form_url(self.song),
            {"key": "Bb", "chordpro": self.MADE_UP, "action": "save"},
        )
        sheet = ChordSheet.objects.get()
        self.assertEqual(sheet.status, Status.PENDING)
        self.assertEqual(sheets.pending_for(self.song, self.other_member), [])
