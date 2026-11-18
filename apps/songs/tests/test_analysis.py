"""Song analysis rules, with the keyword engine.

Lyrics here are invented, or public domain (Amazing Grace, 1779; Holy,
Holy, Holy, 1826).
"""

from django.test import TestCase
from django.utils import timezone

from apps.core.music import Feel
from apps.core.testing import make_song, make_user
from apps.songs.analysis import (
    TAG_THRESHOLD,
    TRUSTED_ARTIST_BONUS,
    analyse,
    analyse_song,
    is_trusted,
    lyrics_text,
    trusted_artist_bonus,
)
from apps.songs.ml.keyword import KeywordEngine
from apps.songs.models import Song, ThemeTag, TrustedArtist

HYMN = """Amazing grace, how sweet the sound
That saved a wretch like me
I once was lost, but now am found
Was blind, but now I see
Holy, holy, holy, Lord God Almighty
Early in the morning our song shall rise to thee
Holy, holy, holy, Lord God Almighty"""
SECULAR = """Driving down the highway in my car
Radio playing low beneath the stars
Summer nights and city lights"""
HOLY = HYMN + "\nPure and righteous, holy is the Lamb"
CELEBRATION = "Shout and dance, we celebrate and rejoice, sing aloud to God our King"


class LyricsTextTests(TestCase):
    def test_repeated_lines_count_once(self):
        self.assertEqual(
            lyrics_text("Holy, holy\n\n  holy, HOLY \nAmen\nHoly, holy"),
            "Holy, holy\nAmen",
        )


class AnalyseTests(TestCase):
    engine = KeywordEngine()

    def test_worship_lyrics_pass_the_check(self):
        result = analyse(HYMN, tags=[], engine=self.engine)
        self.assertTrue(result.accepted)
        self.assertGreaterEqual(result.worship_score, 0.5)
        self.assertEqual(result.engine, "keyword")
        self.assertEqual(len(result.embedding), 256)

    def test_other_lyrics_fail_it(self):
        result = analyse(SECULAR, tags=[], engine=self.engine)
        self.assertFalse(result.accepted)
        self.assertEqual(result.worship_score, 0)

    def test_trusted_artist_adds_confidence(self):
        one_word = "Glory over the hills"
        plain = analyse(one_word, tags=[], engine=self.engine)
        self.assertFalse(plain.accepted)
        trusted = analyse(one_word, tags=[], trusted=True, engine=self.engine)
        self.assertTrue(trusted.accepted)
        self.assertEqual(trusted.model_score, plain.model_score)
        self.assertGreater(trusted.worship_score, trusted.model_score)

    def test_suggests_the_best_fitting_tags(self):
        grace = ThemeTag.objects.get(name="Grace")
        salvation = ThemeTag.objects.get(name="Salvation")
        creation = ThemeTag.objects.get(name="Creation")
        result = analyse(
            HYMN + "\nGrace and favor, undeserved\nRescue, redeem and save",
            tags=[grace, salvation, creation],
            engine=self.engine,
        )
        self.assertEqual(set(result.tag_scores), {grace.pk, salvation.pk, creation.pk})
        self.assertEqual(result.tag_scores[creation.pk], 0)
        self.assertEqual(result.suggested_tags[0], salvation.pk)
        self.assertIn(grace.pk, result.suggested_tags)
        self.assertNotIn(creation.pk, result.suggested_tags)
        for pk in result.suggested_tags:
            self.assertGreaterEqual(result.tag_scores[pk], TAG_THRESHOLD)

    def test_songs_failing_the_check_get_no_tags(self):
        grace = ThemeTag.objects.get(name="Grace")
        result = analyse(
            "Grace and favor, undeserved kindness", tags=[grace], engine=self.engine
        )
        self.assertFalse(result.accepted)
        self.assertGreaterEqual(result.tag_scores[grace.pk], TAG_THRESHOLD)
        self.assertEqual(result.suggested_tags, [])

    def test_at_most_four_tags(self):
        tags = list(ThemeTag.objects.all())
        every_word = " ".join(" ".join(tag.keyword_set()) for tag in tags)
        result = analyse(every_word, tags=tags, engine=self.engine)
        self.assertEqual(len(result.suggested_tags), 4)

    def test_feel_guess(self):
        self.assertEqual(
            analyse(CELEBRATION, tags=[], engine=self.engine).feel, Feel.UPBEAT
        )
        quiet = "Be still and rest, I kneel in quiet surrender"
        self.assertEqual(analyse(quiet, tags=[], engine=self.engine).feel, Feel.SLOW)
        self.assertEqual(analyse(SECULAR, tags=[], engine=self.engine).feel, Feel.MID)


class AnalyseSongTests(TestCase):
    def found(self, lyrics=HOLY, **fields):
        return make_song(lyrics=lyrics, lyrics_status=Song.LyricsStatus.FOUND, **fields)

    def test_saves_the_analysis(self):
        song = self.found()
        analyse_song(song)
        song.refresh_from_db()
        self.assertEqual(song.worship_check, Song.WorshipCheck.ACCEPTED)
        self.assertEqual(song.analysed_with, "keyword")
        self.assertIsNotNone(song.analysed_at)
        self.assertTrue(song.embedding)
        self.assertIn(str(ThemeTag.objects.get(name="Holiness").pk), song.tag_scores)
        self.assertIn("Holiness", [tag.name for tag in song.tags.all()])

    def test_rejects_other_songs(self):
        song = self.found(SECULAR)
        analyse_song(song)
        self.assertEqual(song.worship_check, Song.WorshipCheck.REJECTED)

    def test_switched_off_tags_are_not_suggested(self):
        ThemeTag.objects.filter(name="Holiness").update(is_active=False)
        song = self.found()
        analyse_song(song)
        self.assertNotIn("Holiness", [tag.name for tag in song.tags.all()])

    def test_keeps_a_reviewed_songs_corrections(self):
        joy = ThemeTag.objects.get(name="Joy")
        song = self.found(
            SECULAR,
            worship_check=Song.WorshipCheck.ACCEPTED,
            feel=Feel.UPBEAT,
            reviewed_at=timezone.now(),
            reviewed_by=make_user(),
            tags=[joy],
        )
        analyse_song(song)
        song.refresh_from_db()
        self.assertEqual(song.worship_check, Song.WorshipCheck.ACCEPTED)
        self.assertEqual(song.feel, Feel.UPBEAT)
        self.assertEqual(list(song.tags.all()), [joy])
        self.assertEqual(song.worship_score, 0)
        self.assertIsNotNone(song.analysed_at)

    def test_a_review_saved_during_analysis_wins(self):
        song = self.found(SECULAR)
        # A person corrects the song while the worker holds an old copy.
        Song.objects.filter(pk=song.pk).update(
            worship_check=Song.WorshipCheck.ACCEPTED,
            team_knows=True,
            reviewed_at=timezone.now(),
        )
        analyse_song(song)
        song.refresh_from_db()
        self.assertEqual(song.worship_check, Song.WorshipCheck.ACCEPTED)
        self.assertTrue(song.team_knows)
        self.assertIsNotNone(song.analysed_at)

    def test_songs_without_lyrics_are_left_alone(self):
        song = make_song(lyrics_status=Song.LyricsStatus.MISSING)
        self.assertIsNone(analyse_song(song))
        self.assertIsNone(song.analysed_at)

    def test_raw_model_score_ignores_the_trusted_artist_list(self):
        # Design-Decisions, Phase 5: only lyrics may affect the model's score.
        lyrics = "Glory over the hills"
        plain = self.found(lyrics, artist="Choir A")
        listed = self.found(lyrics, artist="Choir B")
        TrustedArtist.objects.create(name="Choir B")
        analyse_song(plain)
        analyse_song(listed)
        plain.refresh_from_db()
        listed.refresh_from_db()
        self.assertEqual(plain.worship_model_score, listed.worship_model_score)

    def test_adjusted_score_has_the_bonus_only_for_listed_artists(self):
        lyrics = "Glory over the hills"
        plain = self.found(lyrics, artist="Choir A")
        listed = self.found(lyrics, artist="Choir B")
        TrustedArtist.objects.create(name="Choir B")
        analyse_song(plain)
        analyse_song(listed)
        plain.refresh_from_db()
        listed.refresh_from_db()
        self.assertEqual(plain.worship_score, plain.worship_model_score)
        self.assertAlmostEqual(
            listed.worship_score, listed.worship_model_score + TRUSTED_ARTIST_BONUS
        )
        self.assertEqual(plain.worship_check, Song.WorshipCheck.REJECTED)
        self.assertEqual(listed.worship_check, Song.WorshipCheck.ACCEPTED)

    def test_the_bonus_never_goes_past_one(self):
        self.assertEqual(trusted_artist_bonus(0.9, trusted=True), 1.0)
        self.assertEqual(trusted_artist_bonus(0.9, trusted=False), 0.9)

    def test_the_artist_never_reaches_the_engine(self):
        seen = []

        class Recorder(KeywordEngine):
            def score(self, text, labels):
                seen.append(text)
                return super().score(text, labels)

            def embed(self, texts):
                seen.extend(texts)
                return super().embed(texts)

        TrustedArtist.objects.create(name="Unmistakable Artist Name")
        song = self.found("Glory over the hills", artist="Unmistakable Artist Name")
        analyse_song(song, Recorder())
        self.assertTrue(seen)
        self.assertFalse(any("Unmistakable" in text for text in seen))

    def test_trusted_artist_matches_any_credited_artist(self):
        TrustedArtist.objects.create(name="Grace Band")
        TrustedArtist.objects.create(name="Retired Choir", is_active=False)
        self.assertTrue(is_trusted("Someone, grace band"))
        self.assertFalse(is_trusted("Retired Choir"))
        self.assertFalse(is_trusted("Grace"))
