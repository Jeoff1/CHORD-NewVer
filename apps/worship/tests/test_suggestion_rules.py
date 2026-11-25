"""The rules behind song suggestions: search phrases, ranking, sequencing
and seasons. They are plain functions, tested without views."""

import datetime

from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from apps.church.models import ChurchProfile
from apps.core.music import Feel
from apps.core.testing import make_service, make_song
from apps.songs.ml.keyword import KeywordEngine
from apps.songs.models import Song, ThemeTag
from apps.worship import ranking, sequencing, versions
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

    def test_relevance_is_on_a_fixed_scale(self):
        # With the ONNX engine's range, 0.20 maps to 0 and 0.60 to 1.
        scale = (0.20, 0.60)
        self.assertEqual(ranking.relevance(0.60, scale), 1.0)
        self.assertEqual(ranking.relevance(0.40, scale), 0.5)  # not 0.4999…
        self.assertEqual(ranking.relevance(0.75, scale), 1.0)  # clipped
        self.assertEqual(ranking.relevance(0.10, scale), 0.0)  # clipped

    def test_the_same_match_gets_the_same_relevance_whatever_the_pool(self):
        # Smoke test, 2026-11-18: a weak pool's best song used to score 1.0.
        weak = self.song([0.3, (1 - 0.3**2) ** 0.5], title="Weak")
        alone = ranking.rank([weak], theme_vector=[1.0, 0.0], day=DAY, weights=WEIGHTS)
        strong = self.song([1.0, 0.0], title="Strong")
        together = ranking.rank(
            [weak, strong], theme_vector=[1.0, 0.0], day=DAY, weights=WEIGHTS
        )
        self.assertEqual(alone[0].relevance, 0.3)
        self.assertEqual(together[1].relevance, 0.3)
        self.assertEqual(together[1].song, weak)

    def test_closest_first_with_fixed_labels(self):
        scale = (0.20, 0.60)
        cosines = {"Close": 0.55, "Fair": 0.45, "Little": 0.33, "Unrelated": 0.18}
        songs = [
            self.song([c, (1 - c * c) ** 0.5], title=title)
            for title, c in cosines.items()
        ]
        ranked = ranking.rank(
            reversed(songs),
            theme_vector=[1.0, 0.0],
            day=DAY,
            weights=WEIGHTS,
            similarity_range=scale,
        )
        self.assertEqual([r.song.title for r in ranked], list(cosines))
        self.assertEqual(
            [r.reasons[0] for r in ranked],
            [
                "Its lyrics match the theme closely.",
                "Its lyrics match the theme fairly well.",
                "Its lyrics match the theme a little.",
                "Its lyrics don't match the theme well.",
            ],
        )
        self.assertEqual(ranked[1].match, 0.45)

    def test_match_label_thresholds(self):
        self.assertEqual(
            ranking.match_label(0.75), "Its lyrics match the theme closely."
        )
        self.assertEqual(
            ranking.match_label(0.5), "Its lyrics match the theme fairly well."
        )
        self.assertEqual(
            ranking.match_label(0.25), "Its lyrics match the theme a little."
        )
        self.assertEqual(
            ranking.match_label(0.24), "Its lyrics don't match the theme well."
        )

    def test_songs_without_an_embedding_are_left_out(self):
        only = self.song([0.5, 0.5])
        self.song([])
        ranked = ranking.rank(
            Song.objects.all(), theme_vector=[1.0, 0.0], day=DAY, weights=WEIGHTS
        )
        self.assertEqual([r.song for r in ranked], [only])
        self.assertEqual(ranked[0].relevance, 0.5)

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
        # Usage from confirmed lineups: test_usage_and_feedback.py.
        self.assertEqual(ranking.song_usage(make_service()), {})

    def test_listing(self):
        self.assertEqual(ranking._listing(["A"]), "A")
        self.assertEqual(ranking._listing(["A", "B", "C"]), "A, B and C")


def item(title="Song", feel="", score=1.0, artist="Band", embedding=None, **fields):
    """A ranked song, as ranking and grouping see it."""
    song = Song(title=title, feel=feel, artist=artist, embedding=embedding, **fields)
    return ranking.Ranked(
        song, score, relevance=score, familiarity=0, season=0, recency=0, match=0
    )


class SequencingTests(TestCase):
    def setUp(self):
        # The seeded template: Opening (upbeat), Praise (mid-tempo),
        # Worship (slow), Response (slow).
        self.slots = list(ServiceTemplate.objects.get().slots.all())

    def placed(self, ranked, slots=None, feel_weight=0.15):
        return {
            p.slot.name: (ranked[p.index].song.title, p.reason)
            for p in sequencing.place(
                ranked, slots or self.slots, feel_weight=feel_weight
            )
        }

    def test_a_close_song_of_a_near_feel_beats_a_weak_song_of_the_right_feel(self):
        # Smoke test, 2026-11-18: Joyful, Joyful (upbeat, 0.86) lost Praise
        # to Amazing Grace (mid-tempo, 0.21).
        ranked = [
            item("Blessed", Feel.UPBEAT, 1.0),
            item("Joyful", Feel.UPBEAT, 0.86),
            item("Amazing", Feel.MID, 0.21),
        ]
        placed = self.placed(ranked, slots=self.slots[:2])
        self.assertEqual(placed["Opening"], ("Blessed", ""))
        self.assertEqual(placed["Praise"][0], "Joyful")
        self.assertIn(
            "doesn't match this slot, which asks for mid-tempo", placed["Praise"][1]
        )

    def test_each_step_between_feels_costs_the_weight(self):
        worship = self.slots[2:3]  # slow
        # Upbeat is two steps from slow: 0.5 - 0.3 = 0.2 loses to 0.3.
        ranked = [item("Upbeat", Feel.UPBEAT, 0.5), item("Slow", Feel.SLOW, 0.3)]
        self.assertEqual(self.placed(ranked, worship)["Worship"][0], "Slow")
        # 0.7 - 0.3 = 0.4 beats 0.3.
        ranked = [item("Upbeat", Feel.UPBEAT, 0.7), item("Slow", Feel.SLOW, 0.3)]
        self.assertEqual(self.placed(ranked, worship)["Worship"][0], "Upbeat")
        self.assertEqual(sequencing.feel_distance(Feel.UPBEAT, Feel.SLOW), 2)
        self.assertEqual(sequencing.feel_distance(Feel.MID, Feel.SLOW), 1)

    def test_the_best_song_gets_its_own_feel_first(self):
        ranked = [
            item("Slow best", Feel.SLOW, 1.0),
            item("Upbeat", Feel.UPBEAT, 0.9),
            item("Mid", Feel.MID, 0.8),
            item("Slow next", Feel.SLOW, 0.7),
        ]
        placed = self.placed(ranked)
        self.assertEqual(
            {name: title for name, (title, _) in placed.items()},
            {
                "Opening": "Upbeat",
                "Praise": "Mid",
                "Worship": "Slow best",
                "Response": "Slow next",
            },
        )
        self.assertTrue(all(reason == "" for _, reason in placed.values()))

    def test_an_unknown_feel_costs_half_a_step(self):
        self.assertEqual(sequencing.feel_distance("", Feel.SLOW), 0.5)
        self.assertEqual(sequencing.feel_distance("", ""), 0)
        # 0.5 - 0.075 = 0.425 loses to a known slow song at 0.45...
        ranked = [item("Unknown", "", 0.5), item("Slow", Feel.SLOW, 0.45)]
        self.assertEqual(self.placed(ranked, self.slots[2:3])["Worship"][0], "Slow")
        # ...but beats a much weaker one, and says why it is there.
        ranked = [item("Unknown", "", 0.5), item("Slow", Feel.SLOW, 0.3)]
        placed = self.placed(ranked, self.slots[2:3])
        self.assertEqual(placed["Worship"][0], "Unknown")
        self.assertIn("feel isn't known yet", placed["Worship"][1])

    def test_an_unknown_feel_never_beats_a_known_close_match(self):
        # Smoke-test comparison, 2026-11-18: Come, Thou Fount (feel unset,
        # 0.39) took Praise from Blessed Assurance (upbeat, 0.52).
        ranked = [
            item("Blessed Assurance", Feel.UPBEAT, 0.52),
            item("Come, Thou Fount", "", 0.39),
        ]
        praise = self.slots[1:2]  # mid-tempo
        self.assertEqual(self.placed(ranked, praise)["Praise"][0], "Blessed Assurance")
        # At the same score, the matching known feel always wins.
        ranked = [item("Unknown", "", 0.5), item("Mid", Feel.MID, 0.5)]
        self.assertEqual(self.placed(ranked, praise)["Praise"][0], "Mid")

    def test_a_slot_without_a_feel_charges_nothing_for_an_unknown_feel(self):
        template = ServiceTemplate.objects.create(name="Prayer night")
        any_slot = TemplateSlot.objects.create(template=template, name="Song")
        ranked = [item("Unknown", "", 0.5), item("Slow", Feel.SLOW, 0.49)]
        self.assertEqual(self.placed(ranked, [any_slot]), {"Song": ("Unknown", "")})

    def test_one_title_once_per_lineup(self):
        ranked = [
            item("Good News", Feel.SLOW, 0.87, artist="Avalon"),
            item("Good News (Live)", Feel.SLOW, 0.84, artist="Choir"),
            item("Silent Night", Feel.SLOW, 0.7),
        ]
        placed = self.placed(ranked, self.slots[2:])
        self.assertEqual(
            sorted(title for title, _ in placed.values()), ["Good News", "Silent Night"]
        )

    def test_fewer_songs_than_slots_leaves_slots_out(self):
        placed = self.placed([item("Only", Feel.UPBEAT)])
        self.assertEqual(list(placed), ["Opening"])

    def test_a_slot_without_a_feel_takes_any_song(self):
        template = ServiceTemplate.objects.create(name="Prayer night")
        any_slot = TemplateSlot.objects.create(template=template, name="Song")
        placed = self.placed([item("Any", Feel.SLOW)], slots=[any_slot])
        self.assertEqual(placed, {"Song": ("Any", "")})

    def test_without_the_feel_weight_rank_order_fills_the_slots(self):
        ranked = [item(str(n), Feel.SLOW, 1 - n / 10) for n in range(4)]
        placed = self.placed(ranked, feel_weight=0)
        self.assertEqual([title for title, _ in placed.values()], ["0", "1", "2", "3"])


def unit(cosine_with_first_axis):
    c = cosine_with_first_axis
    return [c, (1 - c * c) ** 0.5]


class VersionTests(TestCase):
    """Versions of one song (versions.py), with the thresholds calibrated in
    the smoke test of 2026-11-18."""

    def group(self, ranked, trusted=()):
        return versions.group(
            ranked, trusted_artists={name.lower() for name in trusted}
        )

    def test_titles_match(self):
        self.assertTrue(versions.titles_match("Silent Night", "Silent Night (Live)"))
        self.assertTrue(
            versions.titles_match("Silent Night, Holy Night", "Silent Night")
        )
        # Begins the same way; only alike lyrics make them one song.
        self.assertTrue(versions.titles_match("Holy", "Holy Ground"))
        self.assertFalse(versions.titles_match("Holy", "Holiness"))
        self.assertFalse(versions.titles_match("Silent Night", "Hark! the Herald"))
        self.assertFalse(versions.titles_match("", "Silent Night"))

    def test_versions_with_alike_lyrics_and_titles_are_one_song(self):
        ranked = [
            item(
                "Silent Night, Holy Night", score=0.9, artist="Josh", embedding=unit(1)
            ),
            item("Silent Night", score=0.8, artist="Carpenters", embedding=unit(0.92)),
            item("Hark!", score=0.7, artist="Choir", embedding=unit(0.6)),
        ]
        kept = self.group(ranked)
        self.assertEqual(
            [k.song.title for k in kept], ["Silent Night, Holy Night", "Hark!"]
        )
        self.assertEqual([s.artist for s in kept[0].versions], ["Carpenters"])
        self.assertIn(
            "Other versions in the pool: Silent Night, Carpenters.", kept[0].reasons
        )

    def test_the_versions_reason_never_nests_brackets(self):
        ranked = [
            item("Hark! the Herald Angels Sing", score=0.9, embedding=unit(1)),
            item(
                "Hark! the Herald Angels Sing",
                score=0.8,
                artist="Charles Wesley (1739)",
                embedding=unit(0.99),
            ),
            item(
                "Hark! the Herald Angels Sing (Live)",
                score=0.7,
                artist="A Choir",
                embedding=unit(0.98),
            ),
        ]
        kept = self.group(ranked)
        self.assertIn(
            "Other versions in the pool: Hark! the Herald Angels Sing, Charles "
            "Wesley (1739); Hark! the Herald Angels Sing (Live), A Choir.",
            kept[0].reasons,
        )

    def test_different_titles_need_nearly_the_same_lyrics(self):
        alike = [
            item("Morning Song", embedding=unit(1)),
            item("A New Day", embedding=unit(0.92)),
        ]
        self.assertEqual(len(self.group(alike)), 2)
        same = [
            item("Morning Song", embedding=unit(1)),
            item("A New Day", embedding=unit(0.96)),
        ]
        self.assertEqual(len(self.group(same)), 1)

    def test_one_title_with_other_lyrics_is_another_song(self):
        ranked = [
            item("Good News", artist="One", embedding=unit(1)),
            item("Good News", artist="Two", embedding=unit(0.6)),
        ]
        self.assertEqual(len(self.group(ranked)), 2)

    def test_the_kept_version_follows_the_preference_order(self):
        def versions_of(**extra):
            return [
                item("Silent Night", score=0.9, artist="Best", embedding=unit(1)),
                item(
                    "Silent Night",
                    score=0.8,
                    artist="Other",
                    embedding=unit(0.95),
                    **extra,
                ),
            ]

        kept = self.group(versions_of())
        self.assertEqual(kept[0].song.artist, "Best")

        kept = self.group(versions_of(), trusted=["Other"])
        self.assertEqual(kept[0].song.artist, "Other")
        self.assertIn("because its artist is a Trusted Artist", kept[0].reasons[-1])

        kept = self.group(versions_of(reviewed_at=timezone.now()))
        self.assertEqual(kept[0].song.artist, "Other")
        self.assertIn("because a person has reviewed it", kept[0].reasons[-1])

        kept = self.group(versions_of(team_knows=True))
        self.assertEqual(kept[0].song.artist, "Other")
        self.assertIn(
            "Chosen over the version by Best because the team knows it.",
            kept[0].reasons,
        )

    def test_one_song_is_left_alone(self):
        only = [item("Solo", embedding=unit(1))]
        self.assertEqual(self.group(only), only)


class SeasonTests(SimpleTestCase):
    def season(self, starts, ends, yearly=False):
        return Season(
            church=ChurchProfile(),
            name="Season",
            starts_on=starts,
            ends_on=ends,
            repeats_yearly=yearly,
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
