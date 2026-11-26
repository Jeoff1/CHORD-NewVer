"""The sermon PDF on a theme, and reading a long theme in passages
(Phase 9C; Design-Decisions, "Phase 9C", Sermon PDF). Every text here is
invented."""

import shutil
import tempfile
from unittest import mock

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.audit.models import AuditEvent
from apps.core.storage import private_storage
from apps.core.testing import (
    complete_setup,
    first_church,
    make_service,
    make_theme,
    make_user,
)
from apps.songs.ml.keyword import KeywordEngine, words
from apps.worship import reading, sermons, suggesting
from apps.worship.models import SearchRun, Theme
from apps.worship.phrases import search_phrases

TEMP_PRIVATE = tempfile.mkdtemp()


def make_pdf(*pages):
    """A small, real PDF with one line of text on each page ("" makes a page
    with no text, like a scanned one)."""
    objects = {
        1: b"<< /Type /Catalog /Pages 2 0 R >>",
        3: b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    }
    kids, number = [], 4
    for text in pages:
        stream = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode("latin-1")
        objects[number] = (
            b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream"
        )
        objects[number + 1] = (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            b"/Resources << /Font << /F1 3 0 R >> >> /Contents %d 0 R >>" % number
        )
        kids.append(b"%d 0 R" % (number + 1))
        number += 2
    objects[2] = b"<< /Type /Pages /Kids [%s] /Count %d >>" % (
        b" ".join(kids),
        len(kids),
    )
    out, offsets = bytearray(b"%PDF-1.4\n"), {}
    for key in sorted(objects):
        offsets[key] = len(out)
        out += b"%d 0 obj\n" % key + objects[key] + b"\nendobj\n"
    xref, size = len(out), max(objects) + 1
    out += b"xref\n0 %d\n0000000000 65535 f \n" % size
    for key in range(1, size):
        out += b"%010d 00000 n \n" % offsets[key]
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (
        size,
        xref,
    )
    return bytes(out)


def pdf_upload(*pages, name="Sermon.pdf"):
    return SimpleUploadedFile(name, make_pdf(*pages), content_type="application/pdf")


def filler(count, word="walking"):
    return " ".join(f"{word}{n % 7}" for n in range(count))


@override_settings(PRIVATE_MEDIA_ROOT=TEMP_PRIVATE)
class SermonPdfViewTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEMP_PRIVATE, ignore_errors=True)

    def setUp(self):
        complete_setup()
        self.pastor = make_user(roles=["pastoral_staff"])
        self.leader = make_user(roles=["worship_leader"])
        self.member = make_user(roles=["team_member"])
        self.service = make_service()
        self.theme_url = reverse(
            "worship:theme", kwargs={"public_id": self.service.public_id}
        )
        self.document_url = reverse(
            "worship:theme_document", kwargs={"public_id": self.service.public_id}
        )

    def post_theme(self, **data):
        self.client.force_login(self.pastor)
        fields = {"title": "Grace that forgives", "scripture": "", "notes": ""}
        fields.update(data)
        return self.client.post(self.theme_url, fields, follow=True)

    def theme(self):
        return Theme.objects.get(service=self.service)

    def test_the_pastor_attaches_a_pdf_and_its_text_is_read(self):
        page = self.post_theme(
            document=pdf_upload(
                "Mercy meets us at the cross", "Forgiven people forgive"
            )
        )
        theme = self.theme()
        self.assertTrue(private_storage.exists(theme.document.name))
        self.assertTrue(theme.document.name.startswith("worship/sermons/"))
        self.assertIn("Mercy meets us at the cross", theme.document_text)
        self.assertIn("Forgiven people forgive", theme.document_text)
        self.assertIn("Forgiven people forgive", theme.text())
        self.assertContains(page, "words were read from the sermon PDF")
        self.assertContains(page, "Sermon.pdf")
        # The audit trail has the file's name, never its text.
        event = AuditEvent.objects.get()
        self.assertEqual(event.changes["Sermon PDF"], ["", "Sermon.pdf"])
        self.assertNotIn("Mercy", str(event.changes))

    def test_the_form_names_it_with_the_sermon_label(self):
        complete_setup(labels={"sermon": {"singular": "Homily", "plural": "Homilies"}})
        self.client.force_login(self.pastor)
        page = self.client.get(self.theme_url)
        self.assertContains(page, "Homily PDF")
        self.assertContains(page, 'accept="application/pdf,.pdf"')

    def test_people_who_plan_open_it_and_the_team_cant(self):
        self.post_theme(document=pdf_upload("Grace upon grace"))
        for user in (self.pastor, self.leader):
            self.client.force_login(user)
            response = self.client.get(self.document_url)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response["Content-Type"], "application/pdf")
            self.assertIn("inline", response["Content-Disposition"])
            service_page = self.client.get(
                reverse("worship:service", kwargs={"public_id": self.service.public_id})
            )
            self.assertContains(service_page, self.document_url)
        self.client.force_login(self.member)
        self.assertEqual(self.client.get(self.document_url).status_code, 403)
        service_page = self.client.get(
            reverse("worship:service", kwargs={"public_id": self.service.public_id})
        )
        self.assertNotContains(service_page, self.document_url)

    def test_no_pdf_is_404(self):
        make_theme(self.service)
        self.client.force_login(self.pastor)
        self.assertEqual(self.client.get(self.document_url).status_code, 404)

    def test_only_real_pdfs_are_accepted(self):
        fake = SimpleUploadedFile("notes.pdf", b"<html>not a pdf</html>")
        page = self.post_theme(document=fake)
        self.assertContains(page, "This file isn&#x27;t a PDF.")
        page = self.post_theme(document=SimpleUploadedFile("notes.txt", b"%PDF-1.4"))
        self.assertContains(page, "Choose a PDF file.")
        page = self.post_theme(
            document=SimpleUploadedFile("bad.pdf", b"%PDF-1.4 rubbish")
        )
        self.assertContains(page, "couldn&#x27;t be read")
        self.assertFalse(Theme.objects.exists())

    def test_a_pdf_over_the_limit_is_refused(self):
        with mock.patch.object(sermons, "MAX_BYTES", 10):
            page = self.post_theme(document=pdf_upload("Long"))
        self.assertContains(page, "15 MB or smaller")

    def test_a_scanned_pdf_is_kept_with_a_warning(self):
        page = self.post_theme(document=pdf_upload(""))
        theme = self.theme()
        self.assertTrue(theme.document)
        self.assertEqual(theme.document_text, "")
        self.assertContains(page, "No text could be read from the sermon PDF")

    def test_replacing_or_clearing_removes_the_old_file(self):
        self.post_theme(document=pdf_upload("First draft"))
        first = self.theme().document.name
        self.post_theme(document=pdf_upload("Second draft", name="Final.pdf"))
        theme = self.theme()
        self.assertFalse(private_storage.exists(first))
        self.assertIn("Second draft", theme.document_text)
        self.post_theme(**{"document-clear": "on"})
        theme = self.theme()
        self.assertFalse(theme.document)
        self.assertEqual(theme.document_text, "")
        self.assertEqual(
            len(AuditEvent.objects.filter(changes__has_key="Sermon PDF")), 3
        )

    def test_saving_without_a_new_file_keeps_the_text(self):
        self.post_theme(document=pdf_upload("Kept words"))
        self.post_theme(title="A new title")
        theme = self.theme()
        self.assertEqual(theme.title, "A new title")
        self.assertIn("Kept words", theme.document_text)

    def test_a_pdf_with_text_stands_in_for_notes(self):
        self.post_theme(document=pdf_upload("Grace and favor for the undeserving"))
        self.client.force_login(self.leader)
        page = self.client.get(
            reverse("worship:lineup", kwargs={"public_id": self.service.public_id})
        )
        self.assertNotContains(page, "has no sermon notes")


class ReadingTests(TestCase):
    """A long theme is read in passages, so the model sees all of it."""

    def setUp(self):
        complete_setup()
        self.service = make_service()

    def long_theme(self, ending):
        return make_theme(
            self.service,
            title="Sunday message",
            scripture="Romans",  # no chapter: no passage text
            document_text=f"{filler(700)} {ending}",
        )

    def test_passages_cover_the_text_and_spread_over_a_long_one(self):
        text = filler(400)
        chunks = reading.passages(text, size=150)
        self.assertEqual([len(c.split()) for c in chunks], [150, 150, 100])
        many = reading.passages(filler(150 * 30), size=150, limit=5)
        self.assertEqual(len(many), 5)
        everything = reading.passages(filler(150 * 30), size=150, limit=100)
        self.assertEqual(many[0], everything[0])
        self.assertEqual(many[-1], everything[-1])

    def test_a_short_theme_is_read_whole_as_before(self):
        theme = make_theme(self.service, title="Holy", notes="We praise God")
        engine = KeywordEngine()
        self.assertEqual(
            reading.theme_vector(theme, engine), engine.embed([theme.text()])[0]
        )
        self.assertEqual(reading.tag_texts(theme), [[theme.text()]])
        self.assertIsNone(reading.phrase_sources(theme))

    def test_the_end_of_a_long_sermon_reaches_the_model(self):
        theme = self.long_theme("redemption redemption redemption")
        seen = []

        class Recording(KeywordEngine):
            def embed(self, texts):
                seen.extend(texts)
                return super().embed(texts)

        vector = reading.theme_vector(theme, Recording())
        # No text longer than a passage reaches the model, so nothing is cut off.
        self.assertLessEqual(
            max(len(text.split()) for text in seen), reading.PASSAGE_WORDS
        )
        self.assertTrue(any("redemption" in text for text in seen))
        ending = KeywordEngine().embed(["redemption"])[0]
        self.assertGreater(sum(a * b for a, b in zip(vector, ending)), 0)

    def test_a_model_that_cuts_text_off_would_miss_it(self):
        """Why passages: read whole, the model's limit drops the ending."""
        theme = self.long_theme("redemption redemption redemption")

        class Cutting(KeywordEngine):
            def embed(self, texts):
                return super().embed([" ".join(t.split()[:200]) for t in texts])

        ending = KeywordEngine().embed(["redemption"])[0]
        whole = Cutting().embed([theme.text()])[0]
        self.assertEqual(sum(a * b for a, b in zip(whole, ending)), 0)
        passages = reading.theme_vector(theme, Cutting())
        self.assertGreater(sum(a * b for a, b in zip(passages, ending)), 0)

    def test_the_title_keeps_its_weight(self):
        theme = self.long_theme("")
        vector = reading.theme_vector(theme, KeywordEngine())
        title = KeywordEngine().embed(["Sunday message Romans"])[0]
        self.assertGreater(sum(a * b for a, b in zip(vector, title)), 0.5)

    def test_tags_are_read_from_passages_with_the_heading(self):
        theme = self.long_theme("")
        groups = reading.tag_texts(theme)
        self.assertEqual(len(groups), 1)  # only the PDF has text
        texts = groups[0]
        self.assertLessEqual(len(texts), reading.TAG_PASSAGES)
        self.assertTrue(
            all(text.startswith("Sunday message\nRomans\n") for text in texts)
        )

    def test_theme_tags_come_from_the_pdf(self):
        grace = "grace and favor, undeserved kindness. "
        theme = make_theme(
            self.service,
            title="Sunday message",
            document_text=" ".join(f"{filler(20)} {grace}" for _ in range(30)),
        )
        church = first_church()
        engine = KeywordEngine()
        self.assertFalse(suggesting.theme_tag_ids(theme.heading(), engine, church))
        self.assertTrue(
            suggesting.theme_tag_ids(reading.tag_texts(theme), engine, church)
        )

    def test_search_phrases_come_from_the_whole_sermon(self):
        theme = self.long_theme("steadfast love endures " * 20)
        engine = KeywordEngine()
        phrases = search_phrases(
            theme.title,
            theme.text(),
            4,
            engine,
            theme_vector=reading.theme_vector(theme, engine),
        )
        self.assertEqual(phrases[0], "sunday message")
        self.assertTrue(
            any(set(words(p)) & {"steadfast", "love", "endure"} for p in phrases)
        )

    def test_a_run_reads_the_pdf(self):
        grace = "grace and favor, undeserved kindness. "
        make_theme(
            self.service,
            title="Sunday message",
            document_text=" ".join(f"{filler(20)} {grace}" for _ in range(30)),
        )
        leader = make_user(roles=["worship_leader"])
        run = suggesting.request_run(self.service, leader, use_spotify=False)
        run = suggesting.claim_next_run() or run
        suggesting.execute(run, engine=KeywordEngine())
        run.refresh_from_db()
        self.assertTrue(run.theme_tags)
        self.assertIsNotNone(SearchRun.objects.get(pk=run.pk).weights)


def made_up_words(count):
    """``count`` different invented words, letters only (search phrases
    leave out anything with a digit)."""
    syllables = "ka lo mi re su ta ve ni po da fe gu ho ji ku la me no pi ro".split()
    return [a + b + c for a in syllables for b in syllables for c in syllables][:count]


class EqualSharesTests(TestCase):
    """Each part of the theme has its own share (owner, 2026-11-26): short
    notes count as much as a long sermon PDF."""

    def setUp(self):
        complete_setup()
        self.service = make_service()
        self.engine = KeywordEngine()

    def similarity(self, a, b):
        return sum(x * y for x, y in zip(a, b))

    def test_short_notes_count_as_much_as_a_long_pdf(self):
        notes = "forgiveness mercy pardon " * 10
        theme = make_theme(
            self.service,
            title="Sunday message",
            notes=notes,
            document_text=filler(3000),
        )
        vector = reading.theme_vector(theme, self.engine)
        to_notes = self.similarity(vector, self.engine.embed([notes])[0])
        to_pdf = self.similarity(vector, self.engine.embed([filler(3000)])[0])
        self.assertGreater(to_notes, 0.3)
        self.assertAlmostEqual(to_notes, to_pdf, delta=0.05)

    def test_an_empty_part_leaves_its_share_to_the_others(self):
        notes = filler(400, word="mercy")
        theme = make_theme(self.service, title="Sunday message", notes=notes)
        self.assertEqual(reading.parts(theme), [notes])
        heading = self.engine.embed([theme.heading()])[0]
        body = reading._normalised(
            reading._mean(self.engine.embed(reading.passages(notes)))
        )
        expected = reading._normalised([h + b for h, b in zip(heading, body)])
        for got, want in zip(reading.theme_vector(theme, self.engine), expected):
            self.assertAlmostEqual(got, want)

    def test_tags_average_each_part_then_the_parts(self):
        class GraceOnly(KeywordEngine):
            def score(self, text, labels):
                return [1.0 if "grace" in text else 0.0 for _ in labels]

        church = first_church()
        # Three passages of the PDF without it, the notes with it: half.
        groups = [["sermon"] * 3, ["grace"]]
        self.assertTrue(suggesting.theme_tag_ids(groups, GraceOnly(), church))
        # Counted by length instead, it would be a quarter: below the mark.
        flat = ["sermon"] * 3 + ["grace"]
        self.assertFalse(suggesting.theme_tag_ids(flat, GraceOnly(), church))

    def test_search_phrases_come_from_every_part(self):
        sermon = " ".join(made_up_words(400) * 3)
        theme = make_theme(
            self.service,
            title="Sunday message",
            notes="A fresh start. A fresh start for the forgiven.",
            document_text=sermon,
        )
        vector = reading.theme_vector(theme, self.engine)
        shared = search_phrases(
            theme.title,
            theme.text(),
            5,
            self.engine,
            theme_vector=vector,
            sources=reading.phrase_sources(theme),
        )
        self.assertTrue(any("fresh" in p or "start" in p for p in shared), shared)
        # Drawn from the whole text by frequency, the sermon crowds them out.
        crowded = search_phrases(
            theme.title, theme.text(), 5, self.engine, theme_vector=vector
        )
        self.assertFalse(any("fresh" in p for p in crowded), crowded)
