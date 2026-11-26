"""The lineup comes first; suggestions assist (decision 0015; Phase 9C):
starting a lineup with a song of one's own choosing, adding one suggestion
at a time, and filling only the empty slots."""

from django.test import TestCase
from django.urls import reverse

from apps.audit.models import AuditEvent
from apps.core.testing import (
    complete_setup,
    make_search_run,
    make_service,
    make_song,
    make_theme,
    make_user,
)
from apps.songs.models import Song
from apps.worship import lineups
from apps.worship.models import Lineup, SuggestionFeedback

ACCEPTED = Song.WorshipCheck.ACCEPTED


def url(service, name, **kwargs):
    return reverse(f"worship:{name}", kwargs={"public_id": service.public_id, **kwargs})


class LineupFirstTestCase(TestCase):
    def setUp(self):
        complete_setup()
        self.service = make_service()
        make_theme(self.service, notes="The message in a few sentences.")
        self.slots = list(self.service.template.slots.all())
        self.songs = [
            make_song(title=f"Song {letter}", worship_check=ACCEPTED)
            for letter in "ABCDEF"
        ]
        self.run = make_search_run(self.service, self.songs)
        self.pastor = make_user(roles=["pastoral_staff"])
        self.leader = make_user(roles=["worship_leader"])
        self.member = make_user(roles=["team_member"])
        self.own = make_song(title="Pastor's Choice", worship_check=ACCEPTED)

    def suggestion(self, title):
        return self.run.suggestions.get(song__title=title)

    def lineup(self):
        return Lineup.objects.get(service=self.service)

    def titles(self):
        return [
            (i.slot.name if i.slot else None, i.song.title)
            for i in self.lineup().items.order_by("position")
        ]


class RuleTests(LineupFirstTestCase):
    def test_a_lineup_starts_empty_and_only_once(self):
        lineup, started = lineups.start(self.service, self.pastor)
        self.assertTrue(started)
        self.assertFalse(lineup.items.exists())
        self.assertEqual(lineup.run, self.run)
        again, started = lineups.start(self.service, self.leader)
        self.assertEqual((again, started), (lineup, False))

    def test_starting_is_refused_for_a_cancelled_service_or_without_permission(self):
        with self.assertRaises(lineups.LineupRefused):
            lineups.start(self.service, self.member)
        self.service.is_cancelled = True
        self.service.save()
        with self.assertRaisesMessage(lineups.LineupRefused, "is cancelled"):
            lineups.start(self.service, self.pastor)
        self.assertFalse(Lineup.objects.exists())

    def test_a_suggestion_goes_to_its_slot_or_the_first_empty_one(self):
        lineup, _ = lineups.start(self.service, self.pastor)
        lineups.add_from_pool(lineup, self.own, self.slots[1], self.pastor)
        # Song B was suggested for slot 2, now taken: it goes to slot 1.
        item = lineups.add_suggestion(lineup, self.suggestion("Song B"), self.pastor)
        self.assertEqual(item.slot, self.slots[0])
        self.assertEqual(item.reasons, self.suggestion("Song B").reasons)
        item = lineups.add_suggestion(lineup, self.suggestion("Song C"), self.pastor)
        self.assertEqual(item.slot, self.slots[2])
        self.assertEqual(
            self.titles(),
            [
                (self.slots[0].name, "Song B"),
                (self.slots[1].name, "Pastor's Choice"),
                (self.slots[2].name, "Song C"),
            ],
        )

    def test_a_picked_suggestion_is_feedback_and_pool_songs_are_not(self):
        lineup, _ = lineups.start(self.service, self.pastor)
        lineups.add_suggestion(lineup, self.suggestion("Song E"), self.pastor)
        lineups.add_from_pool(lineup, self.own, None, self.pastor)
        lineups.confirm(self.lineup(), self.pastor)
        feedback = SuggestionFeedback.objects.get()
        self.assertEqual(feedback.song.title, "Song E")
        self.assertEqual(feedback.label, SuggestionFeedback.Label.PICKED)

    def test_another_services_suggestion_is_refused(self):
        other = make_service()
        other_run = make_search_run(other, [make_song(worship_check=ACCEPTED)])
        lineup, _ = lineups.start(self.service, self.pastor)
        with self.assertRaisesMessage(lineups.LineupRefused, "another service"):
            lineups.add_suggestion(lineup, other_run.suggestions.first(), self.pastor)

    def test_filling_keeps_the_songs_already_chosen(self):
        lineup, _ = lineups.start(self.service, self.pastor)
        lineups.add_from_pool(lineup, self.own, self.slots[0], self.pastor)
        lineup, added = lineups.fill_from_suggestions(lineup, self.pastor)
        self.assertEqual(added, len(self.slots) - 1)
        rows = self.titles()
        self.assertEqual(rows[0], (self.slots[0].name, "Pastor's Choice"))
        self.assertEqual([slot for slot, _ in rows], [s.name for s in self.slots])
        with self.assertRaisesMessage(lineups.LineupRefused, "Every slot"):
            lineups.fill_from_suggestions(lineup, self.pastor)

    def test_filling_needs_suggestions(self):
        service = make_service()
        lineup, _ = lineups.start(service, self.pastor)
        with self.assertRaisesMessage(lineups.LineupRefused, "Find songs first"):
            lineups.fill_from_suggestions(lineup, self.pastor)


class PageTests(LineupFirstTestCase):
    def page(self, user):
        self.client.force_login(user)
        return self.client.get(url(self.service, "lineup"))

    def test_before_a_lineup_the_slots_are_empty_with_add_a_song(self):
        page = self.page(self.pastor)
        add = url(self.service, "lineup_add")
        for slot in self.slots:
            self.assertContains(page, f'href="{add}?slot={slot.pk}"')
        self.assertContains(page, "Add the songs you have in mind")
        # The suggestions sit beside the lineup, each with Add.
        self.assertContains(page, "Suggested songs")
        add_b = url(
            self.service, "lineup_add_suggestion", pk=self.suggestion("Song B").pk
        )
        self.assertContains(page, f'action="{add_b}"')

    def test_the_team_still_gets_nothing_before_confirmation(self):
        self.assertEqual(self.page(self.member).status_code, 404)

    def test_adding_a_suggestion_starts_the_lineup(self):
        self.client.force_login(self.pastor)
        response = self.client.post(
            url(self.service, "lineup_add_suggestion", pk=self.suggestion("Song B").pk),
            follow=True,
        )
        self.assertContains(response, "Song B was added to the")
        self.assertEqual(self.titles(), [(self.slots[1].name, "Song B")])
        self.assertContains(response, ">In the lineup<")
        event = AuditEvent.objects.get(object_id=str(self.lineup().pk))
        self.assertEqual(event.action, AuditEvent.Action.CREATED)

    def test_only_people_who_build_lineups_add_suggestions(self):
        self.client.force_login(self.member)
        response = self.client.post(
            url(self.service, "lineup_add_suggestion", pk=self.suggestion("Song B").pk)
        )
        self.assertEqual(response.status_code, 403)
        self.assertFalse(Lineup.objects.exists())

    def test_the_pastors_own_song_starts_the_lineup_in_the_chosen_slot(self):
        self.client.force_login(self.pastor)
        add = url(self.service, "lineup_add")
        page = self.client.get(add, {"q": "choice", "slot": self.slots[2].pk})
        self.assertContains(page, "Pastor&#x27;s Choice")
        self.assertContains(page, f'<option value="{self.slots[2].pk}" selected>')
        self.client.post(add, {"song": self.own.public_id, "slot": self.slots[2].pk})
        self.assertEqual(self.titles(), [(self.slots[2].name, "Pastor's Choice")])

    def test_a_refused_first_song_leaves_no_empty_lineup(self):
        marked = make_song(
            title="Marked",
            worship_check=Song.WorshipCheck.REJECTED,
            reviewed_at=self.service.starts_at,
        )
        self.client.force_login(self.pastor)
        response = self.client.post(
            url(self.service, "lineup_add"), {"song": marked.public_id}, follow=True
        )
        self.assertContains(response, "marked as not a worship song")
        self.assertFalse(Lineup.objects.exists())

    def test_filling_from_the_panel_fills_only_the_empty_slots(self):
        self.client.force_login(self.pastor)
        self.client.post(
            url(self.service, "lineup_add"),
            {"song": self.own.public_id, "slot": self.slots[0].pk},
        )
        response = self.client.post(url(self.service, "lineup_create"), follow=True)
        self.assertContains(response, "3 suggested songs filled the empty slots.")
        self.assertEqual(self.titles()[0], (self.slots[0].name, "Pastor's Choice"))
        self.assertEqual(len(self.titles()), len(self.slots))

    def test_find_on_spotify_brings_the_pastor_back(self):
        with self.settings(SPOTIFY_CLIENT_ID="id", SPOTIFY_CLIENT_SECRET="secret"):
            self.client.force_login(self.pastor)
            add = url(self.service, "lineup_add")
            page = self.client.get(add, {"q": "new hymn", "slot": self.slots[0].pk})
            self.assertContains(page, "Find it on Spotify")
            self.assertContains(page, reverse("songs:spotify_search"))
            # A track already in the pool sends them straight back to add it.
            response = self.client.post(
                reverse("songs:spotify_add"),
                {
                    "spotify_id": self.own.spotify_id,
                    "next": f"{add}?slot={self.slots[0].pk}",
                },
            )
        self.assertRedirects(
            response,
            f"{add}?slot={self.slots[0].pk}&q=Pastor%27s+Choice",
            fetch_redirect_response=False,
        )

    def test_the_next_step_says_to_choose_the_songs(self):
        self.client.force_login(self.pastor)
        page = self.client.get(url(self.service, "service"))
        self.assertContains(page, "Add the songs you have in mind, slot by slot")
