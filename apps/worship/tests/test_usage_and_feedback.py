"""Phase 6, part B: Suggestion Feedback, song usage from confirmed lineups,
and the song usage and attendance reports (Design-Decisions, Phase 6;
workflow review F3, F8)."""

import datetime

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.core.testing import (
    complete_setup,
    first_church,
    make_search_run,
    make_service,
    make_song,
    make_theme,
    make_user,
)
from apps.songs.models import Song
from apps.worship import feedback, lineups, ranking, reports, usage
from apps.worship.models import (
    Lineup,
    LineupItem,
    SuggestionFeedback,
    SuggestionSettings,
)

ACCEPTED = Song.WorshipCheck.ACCEPTED
Label = SuggestionFeedback.Label
DAY = datetime.timedelta(days=1)


def accepted_song(title, **fields):
    fields.setdefault("worship_check", ACCEPTED)
    fields.setdefault("worship_model_score", 0.8)
    fields.setdefault("embedding", [1.0, 0.0])
    return make_song(title=title, **fields)


def confirmed_lineup(service, songs, status=Lineup.Status.CONFIRMED):
    """A lineup stored directly (the rules refuse past services)."""
    lineup = Lineup.objects.create(service=service, status=status)
    for position, song in enumerate(songs):
        LineupItem.objects.create(lineup=lineup, song=song, position=position)
    return lineup


def service_at(starts_at, **fields):
    return make_service(starts_at=starts_at, **fields)


class FeedbackTests(TestCase):
    def setUp(self):
        complete_setup()
        self.service = make_service()
        make_theme(self.service)
        self.slots = list(self.service.template.slots.all())
        self.songs = [accepted_song(f"Song {letter}") for letter in "ABCDEF"]
        self.run = make_search_run(self.service, self.songs)
        self.leader = make_user(roles=["worship_leader"])
        self.pastor = make_user(roles=["pastoral_staff"])
        self.lineup = lineups.create_from_run(self.service, self.leader)

    def item(self, title):
        return self.lineup.items.get(song__title=title)

    def labels(self):
        return {
            row.song.title: row.label
            for row in SuggestionFeedback.objects.filter(lineup=self.lineup)
        }

    def test_nothing_is_recorded_before_confirmation(self):
        lineups.remove(self.lineup, self.item("Song B"), self.leader)
        self.assertFalse(SuggestionFeedback.objects.exists())

    def test_kept_swapped_and_removed_are_recorded_on_confirmation(self):
        lineups.swap(self.lineup, self.item("Song A"), self.songs[4], self.leader)
        lineups.remove(self.lineup, self.item("Song B"), self.leader)
        lineups.move(self.lineup, self.item("Song C"), 1, self.leader)  # still kept
        lineups.confirm(self.lineup, self.leader)
        self.assertEqual(
            self.labels(),
            {
                "Song A": Label.SWAPPED,
                "Song B": Label.REMOVED,
                "Song C": Label.KEPT,
                "Song D": Label.KEPT,
                "Song E": Label.SWAPPED_IN,  # the alternative chosen in the swap
            },
        )

    def test_a_swapped_in_song_can_still_be_swapped_or_removed(self):
        lineups.swap(self.lineup, self.item("Song A"), self.songs[4], self.leader)
        lineups.swap(self.lineup, self.item("Song E"), self.songs[5], self.leader)
        lineups.swap(self.lineup, self.item("Song B"), self.songs[0], self.leader)
        lineups.remove(self.lineup, self.item("Song A"), self.leader)
        lineups.confirm(self.lineup, self.leader)
        labels = self.labels()
        self.assertEqual(labels["Song E"], Label.SWAPPED)  # swapped in, then out
        self.assertEqual(labels["Song F"], Label.SWAPPED_IN)
        self.assertEqual(labels["Song B"], Label.SWAPPED)
        # Song A was swapped out, chosen back in, then removed: its outcome
        # follows the last thing done to it.
        self.assertEqual(labels["Song A"], Label.REMOVED)

    def test_a_swapped_in_song_no_longer_in_the_lineup_counts_as_removed(self):
        lineups.swap(self.lineup, self.item("Song A"), self.songs[4], self.leader)
        self.item("Song E").delete()  # defensive: outcome left "swapped in"
        lineups.confirm(self.lineup, self.leader)
        self.assertEqual(self.labels()["Song E"], Label.REMOVED)

    def test_rows_hold_the_lyrics_scores_and_church_data(self):
        song = self.songs[2]
        song.team_knows = True
        song.save()
        lineups.confirm(self.lineup, self.leader)
        row = SuggestionFeedback.objects.get(song=song)
        suggestion = self.run.suggestions.get(song=song)
        self.assertEqual(row.run, self.run)
        self.assertEqual(row.rank, suggestion.rank)
        self.assertEqual(row.relevance, suggestion.relevance)
        self.assertEqual(row.worship_model_score, 0.8)
        self.assertTrue(row.team_knows)
        self.assertEqual(row.slot_feel, self.slots[2].feel)

    def test_confirming_again_replaces_the_feedback(self):
        lineups.confirm(self.lineup, self.pastor)
        lineups.reopen(self.lineup, self.pastor)
        lineups.remove(self.lineup, self.item("Song C"), self.leader)
        lineups.confirm(self.lineup, self.leader)
        self.assertEqual(self.labels()["Song C"], Label.REMOVED)
        self.assertEqual(SuggestionFeedback.objects.count(), 4)

    def test_regenerated_songs_leave_no_feedback_and_pool_songs_none(self):
        lineups.set_locked(self.lineup, self.item("Song B"), True, self.leader)
        make_search_run(self.service, [self.songs[5], *self.songs[1:5]])
        lineups.regenerate(self.lineup, self.leader)
        lineups.add_from_pool(
            self.lineup, accepted_song("Pool Song"), None, self.leader
        )
        lineups.confirm(self.lineup, self.leader)
        labels = self.labels()
        self.assertNotIn("Song A", labels)  # replaced by regenerating
        self.assertNotIn("Pool Song", labels)
        self.assertEqual(labels["Song B"], Label.KEPT)  # locked, kept
        self.assertEqual(labels["Song F"], Label.KEPT)  # newly placed
        self.assertTrue(all(label == Label.KEPT for label in labels.values()))

    def test_a_kept_song_no_longer_in_the_lineup_counts_as_removed(self):
        # Defensive: an outcome left "kept" for a song that left the lineup.
        self.item("Song D").delete()
        lineups.confirm(self.lineup, self.leader)
        self.assertEqual(self.labels()["Song D"], Label.REMOVED)

    def test_the_turned_down_outcome_needs_a_suggested_song(self):
        pool_song = accepted_song("From The Pool")
        feedback.turned_down(self.lineup, pool_song.pk, Label.REMOVED)
        self.assertEqual(len(self.lineup.suggestion_outcomes), 4)


class TrainingDataTests(TestCase):
    """Design-Decisions, Phase 9: feedback is training data, so it holds no
    Spotify fields as features, no Trusted Artist bonus, no version choice
    and no genre-filter record."""

    FORBIDDEN = {
        "title",
        "artist",
        "album",
        "spotify_id",
        "length_seconds",
        "worship_score",
        "trusted",
        "trusted_artist",
        "bonus",
        "versions",
        "version",
        "reasons",
        "genre",
        "genres",
        "searches",
        "genre_dropped",
    }

    def test_no_forbidden_field_is_stored_or_a_feature(self):
        names = {field.name for field in SuggestionFeedback._meta.get_fields()}
        self.assertFalse(names & self.FORBIDDEN)
        self.assertFalse(set(SuggestionFeedback.FEATURES) & self.FORBIDDEN)
        self.assertLessEqual(set(SuggestionFeedback.FEATURES), names)
        # The song and the run identify a row; they are never features.
        self.assertNotIn("song", SuggestionFeedback.FEATURES)
        self.assertNotIn("run", SuggestionFeedback.FEATURES)


class SongUsageTests(TestCase):
    """``ranking.song_usage`` reads confirmed lineups (review F3)."""

    def setUp(self):
        complete_setup()
        self.first = make_service()
        self.later = service_at(self.first.starts_at + 7 * DAY)
        self.song = accepted_song("Used Song")
        self.other = accepted_song("Fresh Song")

    def test_only_confirmed_lineups_of_earlier_services_count(self):
        confirmed_lineup(self.first, [self.song])
        confirmed_lineup(
            service_at(self.first.starts_at - 7 * DAY),
            [self.song],
            status=Lineup.Status.DRAFT,
        )
        confirmed_lineup(
            service_at(self.first.starts_at - 14 * DAY, is_cancelled=True),
            [self.song],
        )
        confirmed_lineup(service_at(self.later.starts_at + 7 * DAY), [self.other])
        found = ranking.song_usage(self.later)
        self.assertEqual(set(found), {self.song.pk})
        self.assertEqual(found[self.song.pk].times, 1)
        self.assertEqual(found[self.song.pk].last_used, self.first.local_date)
        self.assertEqual(ranking.song_usage(self.first), {})

    def test_ranking_changes_once_a_lineup_is_confirmed(self):
        weights = SuggestionSettings.load(first_church()).weights()

        def score():
            ranked = ranking.rank(
                [self.song, self.other],
                theme_vector=[1.0, 0.0],
                day=self.later.local_date,
                weights=weights,
                usage=ranking.song_usage(self.later),
                window_weeks=4,
            )
            return {item.song.title: item for item in ranked}

        before = score()
        self.assertEqual(before["Used Song"].score, before["Fresh Song"].score)
        lineup = confirmed_lineup(self.first, [self.song], status=Lineup.Status.DRAFT)
        self.assertEqual(score()["Used Song"].score, before["Used Song"].score)
        lineup.status = Lineup.Status.CONFIRMED
        lineup.save()
        after = score()["Used Song"]
        self.assertGreater(after.familiarity, 0)  # used once before
        self.assertGreater(after.recency, 0)  # a week ago, in the window
        self.assertLess(after.score, before["Used Song"].score)
        self.assertIn("Used 1 time before.", after.reasons)
        self.assertTrue(any(r.startswith("Held back: sung on") for r in after.reasons))

    def test_a_song_counts_once_per_service(self):
        confirmed_lineup(self.first, [self.song])
        found = usage.by_song(
            usage.uses(first_church()) + usage.uses(first_church())
        )  # each use twice
        self.assertEqual(found[self.song.pk].times, 1)

    def test_sung_again_within_the_window(self):
        found = usage.SongUsage(self.song.pk)
        found.days = [datetime.date(2026, 1, 4), datetime.date(2026, 1, 25)]
        self.assertTrue(found.sung_again_within(4))  # 3 weeks apart
        self.assertFalse(found.sung_again_within(3))  # exactly the window
        self.assertFalse(found.sung_again_within(0))


class ReportTestCase(TestCase):
    """Two services held with confirmed lineups a week apart, and lineups
    that mustn't count."""

    def setUp(self):
        complete_setup()
        now = timezone.now()
        self.two_weeks_ago = service_at(now - 14 * DAY, attendance=120)
        self.last_week = service_at(now - 7 * DAY)
        self.both = accepted_song("Every Week", artist="Choir (1900)")
        self.once = accepted_song("Once")
        confirmed_lineup(self.two_weeks_ago, [self.both, self.once])
        confirmed_lineup(self.last_week, [self.both])
        # Not counted: a draft, a cancelled service, a service not held yet.
        draft_song = accepted_song("Only In A Draft")
        confirmed_lineup(
            service_at(now - 21 * DAY), [draft_song], status=Lineup.Status.DRAFT
        )
        confirmed_lineup(
            service_at(now - 28 * DAY, is_cancelled=True), [accepted_song("Cancelled")]
        )
        confirmed_lineup(service_at(now + 7 * DAY), [accepted_song("Next Week")])
        self.leader = make_user(roles=["worship_leader"])
        self.pastor = make_user(roles=["pastoral_staff"])
        self.team_member = make_user(roles=["team_member"])
        self.office = make_user(roles=["office_staff"])


class SongUsageReportTests(ReportTestCase):
    URL = reverse("worship:report_song_usage")

    def test_the_report_matches_the_confirmed_lineups(self):
        rows = reports.song_usage(first_church(), window_weeks=4)
        self.assertEqual([r.song.title for r in rows], ["Every Week", "Once"])
        every = rows[0]
        self.assertEqual(every.times, 2)
        self.assertEqual(
            every.days, [self.two_weeks_ago.local_date, self.last_week.local_date]
        )
        self.assertTrue(every.sung_again)  # a week apart, window of 4
        self.assertFalse(rows[1].sung_again)
        self.assertFalse(
            reports.song_usage(first_church(), window_weeks=1)[0].sung_again
        )

    def test_a_period_narrows_it(self):
        rows = reports.song_usage(
            first_church(), start=self.last_week.local_date, window_weeks=4
        )
        self.assertEqual([(r.song.title, r.times) for r in rows], [("Every Week", 1)])

    def test_the_page_highlights_songs_sung_again(self):
        for user in (self.leader, self.pastor):
            self.client.force_login(user)
            page = self.client.get(self.URL)
            self.assertContains(page, "Every Week")
            self.assertContains(page, "Choir (1900)")
            self.assertContains(page, "Sung again within the repeat window")
            self.assertContains(page, 'class="table-warning"', count=1)
            self.assertNotContains(page, "Only In A Draft")
            self.assertNotContains(page, "Next Week")
            self.assertNotContains(page, "Cancelled")

    def test_the_period_filter_on_the_page(self):
        self.client.force_login(self.leader)
        page = self.client.get(
            self.URL, {"start": self.last_week.local_date.isoformat()}
        )
        self.assertNotContains(page, ">Once<")
        self.assertContains(page, "Every Week")

    def test_csv_export(self):
        self.client.force_login(self.leader)
        response = self.client.get(self.URL, {"format": "csv"})
        self.assertEqual(response["Content-Type"], "text/csv")
        self.assertIn("song-usage.csv", response["Content-Disposition"])
        lines = response.content.decode().splitlines()
        self.assertEqual(
            lines[0],
            "Song,Artist,Times used,Last used,Dates used,Sung again within 4 weeks",
        )
        self.assertEqual(
            lines[1],
            f"Every Week,Choir (1900),2,{self.last_week.local_date.isoformat()},"
            f"{self.two_weeks_ago.local_date.isoformat()}; "
            f"{self.last_week.local_date.isoformat()},Yes",
        )
        self.assertEqual(len(lines), 3)

    def test_only_planners_see_it(self):
        for user in (self.team_member, self.office):
            self.client.force_login(user)
            self.assertEqual(self.client.get(self.URL).status_code, 403)

    def test_switched_off_module_is_404(self):
        complete_setup(disabled_modules=["worship"])
        self.client.force_login(self.leader)
        self.assertEqual(self.client.get(self.URL).status_code, 404)


class AttendanceReportTests(ReportTestCase):
    URL = reverse("worship:report_attendance")
    REPORTS = reverse("worship:reports")

    def test_the_headcounts_of_held_services(self):
        service_at(timezone.now() + 3 * DAY, attendance=999)  # not held yet
        for user in (self.pastor, self.office):
            self.client.force_login(user)
            page = self.client.get(self.URL)
            self.assertContains(page, "120")
            # Checked in the data, not the HTML: "999" can turn up in a
            # username or an id on the page.
            self.assertNotIn(999, [s.attendance for s in page.context["services"]])
            # UI/UX Phase 10: the average is a summary count.
            self.assertContains(page, '<span class="chord-stat__value">120</span>')
            self.assertContains(page, "average headcount")
            self.assertContains(self.client.get(self.REPORTS), "Attendance")

    def test_hidden_when_no_headcount_was_ever_recorded(self):
        from apps.worship.models import WorshipService

        WorshipService.objects.update(attendance=None)
        self.client.force_login(self.office)
        self.assertEqual(self.client.get(self.URL).status_code, 404)
        reports_page = self.client.get(self.REPORTS)
        self.assertNotContains(reports_page, "Attendance</a>")
        self.assertContains(reports_page, "No reports yet")
        self.client.force_login(self.pastor)
        reports_page = self.client.get(self.REPORTS)
        self.assertContains(reports_page, "Song usage")
        self.assertNotContains(reports_page, "Attendance</a>")

    def test_who_may_see_it(self):
        for user in (self.leader, self.team_member):
            self.client.force_login(user)
            self.assertEqual(self.client.get(self.URL).status_code, 403)
        self.client.force_login(self.team_member)
        self.assertEqual(self.client.get(self.REPORTS).status_code, 403)

    def test_the_reports_link_in_the_worship_nav(self):
        home = reverse("worship:home")
        self.client.force_login(self.leader)
        self.assertContains(self.client.get(home), self.REPORTS)
        self.client.force_login(self.team_member)
        self.assertNotContains(self.client.get(home), self.REPORTS)
