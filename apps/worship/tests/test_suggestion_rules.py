"""The rules behind song suggestions: search phrases, ranking, sequencing
and seasons. They are plain functions, tested without views."""

import datetime
from types import SimpleNamespace

from django.test import SimpleTestCase, TestCase

from apps.core.music import Feel
from apps.core.testing import make_song
from apps.songs.ml.keyword import KeywordEngine
from apps.songs.models import Song, ThemeTag
from apps.worship import ranking, sequencing
from apps.worship.models import Season, ServiceTemplate, TemplateSlot
from apps.worship.phrases import candidates, search_phrases
from apps.worship.ranking import Usage

DAY = datetime.date(2026, 12, 6)
WEIGHTS = {"relevance": 1.0, "familiarity": 0.3, "season": 0.2, "recency": 0.4}
ONLY_RELEVANCE = {"relevance": 1.0, "familiarity": 0, "season": 0, "recency": 0}


class PhraseTests(SimpleTestCase):
    engine = KeywordEngine()

    def test_a_short_title_comes_first(self):
        phrases = search_phrases(
            "Grace that forgives",
            "Grace that forgives\nMercy for the lost, grace for the weary",
            3,
            self.engine,
        )
        self.assertEqual(phrases[0], "grace that forgives")
        self.assertEqual(len(phrases), 3)

    def test_a_long_title_is_not_a_phrase(self):
        title = "When we walk through the valley of the shadow"
        phrases = search_phrases(title, title + "\nHope and rest", 2, self.engine)
        self.assertNotIn(title.lower(), phrases)
        self.assertEqual(len(phrases), 2)

    def test_phrases_covered_by_the_title_are_skipped(self):
        phrases = search_phrases(
            "Living hope", "Living hope\nhope rises", 4, self.engine
        )
        self.assertEqual(phrases[0], "living hope")
        self.assertNotIn("hope", phrases[1:])
        self.assertNotIn("living", phrases[1:])

    def test_count_is_respected_and_empty_text_gives_nothing(self):
        self.assertEqual(search_phrases("", "", 4, self.engine), [])
        self.assertEqual(search_phrases("Joy", "Joy", 1, self.engine), ["joy"])

    def test_candidates_skip_stop_words_and_verse_numbers(self):
        found = candidates("The love of God, John 3:16. Love of God never fails.")
        self.assertEqual(found[0], "love")
        self.assertIn("love of god", found)
        self.assertNotIn("of god", found)
        self.assertNotIn("the love", found)
        self.assertFalse(any(any(c.isdigit() for c in p) for p in found))


class RankingTests(TestCase):
    def song(self, embedding, **fields):
        return make_song(embedding=embedding, **fields)

    def test_relevance_runs_from_the_closest_to_the_farthest(self):
        near = self.song([1.0, 0.0], title="Near")
        middle = self.song([0.6, 0.8], title="Middle")
        far = self.song([0.0, 1.0], title="Far")
        ranked = ranking.rank(
            [far, near, middle], theme_vector=[1.0, 0.0], day=DAY, weights=WEIGHTS
        )
        self.assertEqual([r.song for r in ranked], [near, middle, far])
        self.assertEqual([r.relevance for r in ranked], [1.0, 0.6, 0.0])
        self.assertEqual(ranked[1].match, 0.6)
        self.assertIn("Its lyrics match the theme closely.", ranked[0].reasons)
        self.assertIn("Its lyrics match the theme a little.", ranked[2].reasons)

    def test_songs_without_an_embedding_are_left_out(self):
        only = self.song([0.5, 0.5])
        self.song([])
        ranked = ranking.rank(
            Song.objects.all(), theme_vector=[1.0, 0.0], day=DAY, weights=WEIGHTS
        )
        self.assertEqual([r.song for r in ranked], [only])
        self.assertEqual(ranked[0].relevance, 1.0)  # alone, it is the closest

    def test_familiarity_and_recent_use(self):
        known = self.song([1.0, 0.0], team_knows=True)
        usage = {known.pk: Usage(times=5, last_used=DAY - datetime.timedelta(days=7))}
        [item] = ranking.rank(
            [known],
            theme_vector=[1.0, 0.0],
            day=DAY,
            weights=WEIGHTS,
            usage=usage,
            window_weeks=4,
        )
        self.assertEqual(item.familiarity, 1.0)
        self.assertEqual(item.recency, 0.75)
        self.assertEqual(item.score, round(1.0 + 0.3 * 1.0 - 0.4 * 0.75, 4))
        self.assertIn("The team knows it.", item.reasons)
        self.assertIn("Used 5 times before.", item.reasons)
        self.assertIn("Held back: sung on Nov 29.", item.reasons)

    def test_recent_use_fades_out_over_the_repeat_window(self):
        old = Usage(times=1, last_used=DAY - datetime.timedelta(weeks=4))
        self.assertEqual(ranking.recency(old, DAY, 4), 0.0)
        self.assertEqual(ranking.recency(Usage(), DAY, 4), 0.0)
        self.assertEqual(ranking.recency(Usage(1, DAY), DAY, 0), 0.0)
        later = Usage(times=1, last_used=DAY + datetime.timedelta(days=1))
        self.assertEqual(ranking.recency(later, DAY, 4), 0.0)

    def test_a_recently_used_song_drops_below_a_fresh_one(self):
        used = self.song([1.0, 0.0], title="Used")
        fresh = self.song([1.0, 0.0], title="Zed fresh")
        usage = {used.pk: Usage(times=1, last_used=DAY)}
        ranked = ranking.rank(
            [used, fresh],
            theme_vector=[1.0, 0.0],
            day=DAY,
            weights=WEIGHTS,
            usage=usage,
            window_weeks=4,
        )
        self.assertEqual([r.song for r in ranked], [fresh, used])

    def test_season_fit_and_shared_theme_tags(self):
        grace = ThemeTag.objects.get(name="Grace")
        hope = ThemeTag.objects.get(name="Hope")
        season = Season.objects.create(
            name="Harvest time",
            starts_on=datetime.date(2026, 11, 1),
            ends_on=datetime.date(2026, 12, 31),
        )
        season.tags.set([hope])
        fitting = self.song([1.0, 0.0], tags=[hope, grace])
        [item] = ranking.rank(
            [fitting],
            theme_vector=[1.0, 0.0],
            day=DAY,
            weights=WEIGHTS,
            theme_tags=[grace.pk],
            seasons=[season],
        )
        self.assertEqual(item.season, 1.0)
        self.assertIn("Suits the season: Harvest time.", item.reasons)
        self.assertIn("About Grace, like the theme.", item.reasons)

    def test_the_weights_decide(self):
        close = self.song([1.0, 0.0], title="Close")
        known = self.song([0.0, 1.0], title="Known", team_knows=True)
        by_match = ranking.rank(
            [close, known], theme_vector=[1.0, 0.0], day=DAY, weights=ONLY_RELEVANCE
        )
        by_familiarity = ranking.rank(
            [close, known],
            theme_vector=[1.0, 0.0],
            day=DAY,
            weights={**ONLY_RELEVANCE, "familiarity": 5.0},
        )
        self.assertEqual(by_match[0].song, close)
        self.assertEqual(by_familiarity[0].song, known)

    def test_ties_go_by_title(self):
        b = self.song([1.0, 0.0], title="Beta")
        a = self.song([1.0, 0.0], title="alpha")
        ranked = ranking.rank(
            [b, a], theme_vector=[1.0, 0.0], day=DAY, weights=ONLY_RELEVANCE
        )
        self.assertEqual([r.song for r in ranked], [a, b])

    def test_usage_is_empty_until_lineups_exist(self):
        self.assertEqual(ranking.song_usage(None), {})

    def test_listing(self):
        self.assertEqual(ranking._listing(["A"]), "A")
        self.assertEqual(ranking._listing(["A", "B", "C"]), "A, B and C")


def ranked_with_feels(*feels):
    return [SimpleNamespace(song=SimpleNamespace(feel=feel)) for feel in feels]


class SequencingTests(TestCase):
    def setUp(self):
        # The seeded template: Opening (upbeat), Praise (mid-tempo),
        # Worship (slow), Response (slow).
        self.slots = list(ServiceTemplate.objects.get().slots.all())

    def placed(self, ranked, slots=None):
        return {
            p.slot.name: (p.index, p.reason)
            for p in sequencing.place(ranked, slots or self.slots)
        }

    def test_songs_go_to_the_first_slot_of_their_feel_in_rank_order(self):
        ranked = ranked_with_feels(
            Feel.SLOW, Feel.UPBEAT, Feel.MID, Feel.SLOW, Feel.UPBEAT
        )
        placed = self.placed(ranked)
        self.assertEqual(
            {name: index for name, (index, _) in placed.items()},
            {"Opening": 1, "Praise": 2, "Worship": 0, "Response": 3},
        )
        self.assertTrue(all(reason == "" for _, reason in placed.values()))

    def test_an_empty_slot_takes_the_best_song_left_and_says_so(self):
        ranked = ranked_with_feels(Feel.SLOW, Feel.SLOW, Feel.SLOW, Feel.MID)
        placed = self.placed(ranked)
        self.assertEqual(placed["Opening"][0], 2)
        self.assertIn("No upbeat song ranked high enough", placed["Opening"][1])

    def test_fewer_songs_than_slots_leaves_slots_out(self):
        placed = self.placed(ranked_with_feels(Feel.UPBEAT))
        self.assertEqual(list(placed), ["Opening"])

    def test_a_slot_without_a_feel_takes_any_song(self):
        template = ServiceTemplate.objects.create(name="Prayer night")
        any_slot = TemplateSlot.objects.create(template=template, name="Song")
        placed = self.placed(ranked_with_feels(Feel.SLOW), slots=[any_slot])
        self.assertEqual(placed, {"Song": (0, "")})


class SeasonTests(SimpleTestCase):
    def season(self, starts, ends, yearly=False):
        return Season(
            name="Season", starts_on=starts, ends_on=ends, repeats_yearly=yearly
        )

    def test_a_dated_season(self):
        season = self.season(datetime.date(2026, 3, 1), datetime.date(2026, 4, 5))
        self.assertTrue(season.contains(datetime.date(2026, 3, 1)))
        self.assertTrue(season.contains(datetime.date(2026, 4, 5)))
        self.assertFalse(season.contains(datetime.date(2027, 3, 10)))

    def test_a_yearly_season_comes_back(self):
        season = self.season(
            datetime.date(2020, 3, 1), datetime.date(2020, 4, 5), yearly=True
        )
        self.assertTrue(season.contains(datetime.date(2031, 3, 15)))
        self.assertFalse(season.contains(datetime.date(2031, 5, 1)))

    def test_a_yearly_season_can_run_over_the_new_year(self):
        season = self.season(
            datetime.date(2020, 12, 1), datetime.date(2020, 1, 6), yearly=True
        )
        self.assertTrue(season.contains(datetime.date(2031, 12, 25)))
        self.assertTrue(season.contains(datetime.date(2032, 1, 2)))
        self.assertFalse(season.contains(datetime.date(2032, 2, 1)))
