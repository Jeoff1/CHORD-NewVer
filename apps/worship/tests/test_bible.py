"""The Bible CHORD ships with and the Main scripture field (Phase 9C;
Design-Decisions, "Phase 9C", Main scripture). The text is the World
English Bible, which is in the public domain."""

import importlib
from collections import Counter

from django.apps import apps as django_apps
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from apps.audit.models import AuditEvent
from apps.core.testing import (
    complete_setup,
    first_church,
    make_service,
    make_theme,
    make_user,
)
from apps.worship import bible
from apps.worship.models import BibleSettings, Theme


def ref(text, **kwargs):
    passage = bible.parse(text, **kwargs)
    return passage.reference() if passage else None


class BookTableTests(SimpleTestCase):
    def test_every_book_has_its_text_and_no_name_is_shared(self):
        self.assertEqual({b.code for b in bible.BOOKS}, set(bible._chapters()))
        keys = Counter(key for book in bible.BOOKS for key in bible._keys(book))
        self.assertEqual([key for key, n in keys.items() if n > 1], [])
        self.assertEqual(len(bible.books()), 66)
        self.assertEqual(len(bible.books(deuterocanon=True)), 81)

    def test_the_text_is_the_world_english_bible(self):
        self.assertEqual(
            bible.passage_text("Genesis 1:1"),
            "In the beginning, God created the heavens and the earth.",
        )
        self.assertEqual(len(bible.chapters(bible.parse("Rev 1").book)), 22)


class ParseTests(SimpleTestCase):
    def test_references_are_read_however_they_are_written(self):
        cases = {
            "John 3:16": "John 3:16",
            "jn 3:16-18": "John 3:16-18",
            "John 3.16": "John 3:16",
            "JOHN  3 : 16": "John 3:16",
            "1 Cor 13": "1 Corinthians 13",
            "1cor 13:4-7": "1 Corinthians 13:4-7",
            "I Corinthians 13:4–7": "1 Corinthians 13:4-7",
            "Second Timothy 3:16": "2 Timothy 3:16",
            "Rom 8:28-9:2": "Romans 8:28-9:2",
            "Genesis 1-2": "Genesis 1-2",
            "Song of Solomon 2:4": "Song of Songs 2:4",
            "Ps 23": "Psalm 23",
            "Psalms 23-24": "Psalms 23-24",
            "Rev. 22:21": "Revelation 22:21",
        }
        for typed, expected in cases.items():
            with self.subTest(typed=typed):
                self.assertEqual(ref(typed), expected)

    def test_what_isnt_a_passage_is_none(self):
        for typed in (
            "",
            "Various",
            "John",
            "John 22:1",
            "John 3:99",
            "John 3:18-16",
            "Hezekiah 1:1",
            "Rom 8:28-99:1",
        ):
            with self.subTest(typed=typed):
                self.assertIsNone(bible.parse(typed))

    def test_the_deuterocanonical_books_only_when_included(self):
        self.assertIsNone(bible.parse("Tobit 1:1"))
        self.assertIsNone(bible.parse("Psalm 151"))
        self.assertEqual(ref("Tobit 1:1", deuterocanon=True), "Tobit 1:1")
        self.assertEqual(ref("Sir 1:1-3", deuterocanon=True), "Sirach 1:1-3")
        self.assertEqual(ref("Psalm 151", deuterocanon=True), "Psalm 151 1")

    def test_a_long_passage_is_cut(self):
        passage = bible.parse("Psalm 119")
        self.assertEqual(len(passage.verses()), bible.MAX_VERSES)
        self.assertTrue(passage.is_cut())
        self.assertFalse(bible.parse("Psalm 23").is_cut())

    def test_verses_across_chapters(self):
        verses = bible.parse("Rom 8:38-9:1").verses()
        self.assertEqual([(c, v) for c, v, _ in verses], [(8, 38), (8, 39), (9, 1)])


class SuggestTests(SimpleTestCase):
    def values(self, typed, **kwargs):
        return [value for value, _ in bible.suggest(typed, **kwargs)]

    def test_books_by_name_or_abbreviation(self):
        self.assertEqual(self.values("phil"), ["Philippians ", "Philemon "])
        self.assertIn("1 Corinthians ", self.values("1 c"))
        self.assertIn("John ", self.values("jn"))
        self.assertEqual(bible.suggest("rev")[0][1], "22 chapters")

    def test_chapters_then_verses(self):
        self.assertEqual(self.values("ps 2")[:3], ["Psalm 2", "Psalm 20", "Psalm 21"])
        found = bible.suggest("john 3:1")
        self.assertEqual(
            [v for v, _ in found][:3], ["John 3:1", "John 3:10", "John 3:11"]
        )
        self.assertTrue(found[0][1].startswith("Now there was a man of the Pharisees"))

    def test_each_book_first_for_a_short_name(self):
        self.assertEqual(
            self.values("jo 3")[:5],
            ["Joshua 3", "Job 3", "Joel 3", "Jonah 3", "John 3"],
        )

    def test_a_range_is_offered_whole(self):
        self.assertEqual(self.values("rom 8:28-30"), ["Romans 8:28-30"])
        self.assertEqual(self.values("john 3:99"), [])

    def test_at_most_eight_and_nothing_for_nothing(self):
        self.assertEqual(len(bible.suggest("j")), bible.SUGGESTIONS)
        self.assertEqual(bible.suggest(""), [])
        self.assertEqual(bible.suggest("123"), [])

    def test_deuterocanonical_books_follow_the_setting(self):
        self.assertNotIn("Tobit ", self.values("tob"))
        self.assertIn("Tobit ", self.values("tob", deuterocanon=True))


class ThemePassageTests(TestCase):
    def setUp(self):
        complete_setup()
        self.service = make_service()

    def test_the_passage_text_is_kept_and_matched(self):
        theme = make_theme(self.service, scripture="Jn 3:16")
        self.assertTrue(theme.scripture_text.startswith("For God so loved the world"))
        self.assertIn(theme.scripture_text, theme.body())
        theme.scripture = "Various passages"
        theme.save(update_fields=["scripture"])
        theme.refresh_from_db()
        self.assertEqual(theme.scripture_text, "")

    def test_the_churchs_setting_decides_the_books(self):
        theme = make_theme(self.service, scripture="Tobit 4:7")
        self.assertEqual(theme.scripture_text, "")
        BibleSettings.objects.update_or_create(
            church=first_church(), defaults={"include_deuterocanon": True}
        )
        theme.save()
        self.assertIn("alms", theme.scripture_text.lower())

    def test_the_migration_fills_existing_themes(self):
        theme = make_theme(self.service, scripture="Psalm 23")
        Theme.objects.filter(pk=theme.pk).update(scripture_text="")
        migration = importlib.import_module("apps.worship.migrations.0016_bible")
        migration.fill_scripture_text(django_apps, None)
        theme.refresh_from_db()
        self.assertIn("Yahweh is my shepherd", theme.scripture_text)


class ScriptureViewTests(TestCase):
    def setUp(self):
        complete_setup()
        self.pastor = make_user(roles=["pastoral_staff"])
        self.member = make_user(roles=["team_member"])
        self.service = make_service()
        self.suggest = reverse("worship:scripture_suggest")
        self.passage = reverse("worship:scripture_passage")

    def test_suggestions_while_typing(self):
        self.client.force_login(self.pastor)
        page = self.client.get(self.suggest, {"scripture": "jn 3:16"})
        self.assertContains(page, 'role="option"')
        self.assertContains(page, 'data-value="John 3:16"')
        self.assertContains(page, "For God so loved")
        self.assertNotContains(page, "<html")

    def test_the_passage_preview(self):
        self.client.force_login(self.pastor)
        page = self.client.get(self.passage, {"scripture": "Ps 23:1-2"})
        self.assertContains(page, "Psalm 23:1-2")
        self.assertContains(page, "Yahweh is my shepherd")
        self.assertContains(page, "World English Bible")
        page = self.client.get(self.passage, {"scripture": "Hezekiah 4"})
        self.assertContains(page, "Not found in the Bible")
        page = self.client.get(self.passage, {"scripture": ""})
        self.assertEqual(page.content.strip(), b"")

    def test_only_people_who_post_themes(self):
        self.client.force_login(self.member)
        self.assertEqual(
            self.client.get(self.suggest, {"scripture": "jn"}).status_code, 403
        )
        self.assertEqual(
            self.client.get(self.passage, {"scripture": "jn 1"}).status_code, 403
        )

    def test_the_theme_form_suggests_and_previews(self):
        self.client.force_login(self.pastor)
        page = self.client.get(
            reverse("worship:theme", kwargs={"public_id": self.service.public_id})
        )
        self.assertContains(page, 'role="combobox"')
        self.assertContains(page, f'hx-get="{self.suggest}"')
        self.assertContains(page, f'hx-get="{self.passage}"')
        self.assertContains(page, "worship/scripture.js")
        self.assertContains(page, "Jn 3:16 or Ps 23")

    def test_any_text_is_still_saved(self):
        self.client.force_login(self.pastor)
        self.client.post(
            reverse("worship:theme", kwargs={"public_id": self.service.public_id}),
            {"title": "Many voices", "scripture": "Various passages", "notes": ""},
        )
        theme = Theme.objects.get()
        self.assertEqual(theme.scripture, "Various passages")
        self.assertEqual(theme.scripture_text, "")

    def test_the_theme_card_offers_the_passage_to_everyone_who_sees_it(self):
        make_theme(self.service, scripture="John 3:16")
        url = reverse("worship:service", kwargs={"public_id": self.service.public_id})
        for user in (self.pastor, self.member):
            self.client.force_login(user)
            page = self.client.get(url)
            self.assertContains(page, "Read John 3:16")
            self.assertContains(page, "For God so loved the world")


class BibleSettingsTests(TestCase):
    def setUp(self):
        complete_setup()
        self.url = reverse("worship:bible_settings")

    def test_the_pastor_includes_the_deuterocanonical_books(self):
        pastor = make_user(roles=["pastoral_staff"])
        self.client.force_login(pastor)
        page = self.client.get(self.url)
        self.assertContains(page, "Include the deuterocanonical books")
        self.assertContains(page, "World English Bible")
        self.client.post(self.url, {"include_deuterocanon": "on"})
        self.assertTrue(BibleSettings.load(first_church()).include_deuterocanon)
        event = AuditEvent.objects.get()
        self.assertEqual(event.changes["Deuterocanonical books"], ["No", "Yes"])
        page = self.client.get(
            reverse("worship:scripture_suggest"), {"scripture": "tob"}
        )
        self.assertContains(page, 'data-value="Tobit "')

    def test_off_by_default_and_only_with_the_permission(self):
        self.assertFalse(BibleSettings.load(first_church()).include_deuterocanon)
        for role in ("worship_leader", "team_member"):
            self.client.force_login(make_user(roles=[role]))
            self.assertEqual(self.client.get(self.url).status_code, 403)
