"""Guided service planning (Phase 9C; Design-Decisions, "Phase 9C"): the
four Planning Steps, the next-step panel, the Song Lineup page and the
Confirm rundown."""

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.core.testing import (
    complete_setup,
    make_assignment,
    make_lineup,
    make_service,
    make_song,
    make_team_part,
    make_theme,
    make_user,
)
from apps.worship.models import SearchRun


def url(service, name):
    return reverse(f"worship:{name}", kwargs={"public_id": service.public_id})


def assign_url(service):
    return reverse("teams:assign", kwargs={"public_id": service.public_id})


def step_labels(page):
    content = page.content.decode()
    return content.count('class="chord-steps__step')


def current_step(page):
    content = page.content.decode()
    return content[content.index('aria-current="step"') :][:600]


class PlanningTestCase(TestCase):
    def setUp(self):
        complete_setup()
        self.pastor = make_user(roles=["pastoral_staff"])
        self.leader = make_user(roles=["worship_leader"])
        self.member = make_user(roles=["team_member"])
        self.service = make_service(name="Sunday test")

    def page(self, user, name="service"):
        self.client.force_login(user)
        return self.client.get(url(self.service, name))


class StepBarTests(PlanningTestCase):
    def test_a_new_service_has_four_steps_and_the_theme_is_next(self):
        page = self.page(self.pastor)
        self.assertEqual(step_labels(page), 4)
        for label in ("Theme", "Praise Team", "Song Lineup", "Confirm"):
            self.assertContains(page, label)
        self.assertIn("Theme", current_step(page))
        # Each step is a link to its page; Confirm only once a lineup exists.
        self.assertContains(
            page, f'href="{url(self.service, "theme")}" class="stretched-link"'
        )
        self.assertContains(
            page, f'href="{assign_url(self.service)}" class="stretched-link"'
        )
        self.assertContains(
            page, f'href="{url(self.service, "lineup")}" class="stretched-link"'
        )
        self.assertNotContains(
            page, f'href="{url(self.service, "lineup_confirm")}" class="stretched-link"'
        )

    def test_with_teams_off_there_are_three_steps(self):
        complete_setup(disabled_modules=["teams"])
        make_theme(self.service)
        page = self.page(self.pastor)
        self.assertEqual(step_labels(page), 3)
        self.assertNotContains(page, "Praise Team")
        self.assertIn("Song Lineup", current_step(page))
        self.assertContains(page, "Next: choose the songs")

    def test_the_church_names_the_team_and_the_lineup(self):
        complete_setup(
            labels={
                "team": {"singular": "Music Team", "plural": "Music Teams"},
                "lineup": {"singular": "Song List", "plural": "Song Lists"},
            }
        )
        make_theme(self.service)
        page = self.page(self.pastor)
        self.assertContains(page, "Music Team")
        self.assertContains(page, "Next: assign the Music Team")
        # "Song List" already says song: no "Song Song List".
        self.assertContains(page, ">Song List</a>")
        self.assertNotContains(page, "Song Song List")
        self.assertContains(page, '<h2 id="team-title" class="card-title">Music Team')

    def test_the_team_sees_no_steps_and_no_panel(self):
        make_theme(self.service)
        page = self.page(self.member)
        self.assertNotContains(page, "Planning steps")
        self.assertNotContains(page, 'id="next-step"')


class NextStepTests(PlanningTestCase):
    def test_first_post_the_theme(self):
        page = self.page(self.pastor)
        self.assertContains(page, "Next: post the theme")
        self.assertContains(
            page,
            f'href="{url(self.service, "theme")}" class="btn btn-primary chord-btn">Post the theme',
        )

    def test_then_assign_the_team_or_skip(self):
        make_theme(self.service)
        page = self.page(self.pastor)
        self.assertIn("Praise Team", current_step(page))
        self.assertContains(page, "Next: assign the Praise Team")
        self.assertContains(
            page,
            f'href="{assign_url(self.service)}" class="btn btn-primary chord-btn">Assign the Praise Team',
        )
        self.assertContains(
            page,
            f'href="{url(self.service, "lineup")}" class="fw-semibold">Skip for now',
        )

    def test_once_someone_is_assigned_choose_the_songs(self):
        make_theme(self.service)
        make_assignment(self.service, make_user(first_name="Jo"), make_team_part())
        page = self.page(self.pastor)
        self.assertContains(page, "1 assigned, 0 accepted")
        self.assertIn("Song Lineup", current_step(page))
        self.assertContains(page, ">Choose the songs</a>")

    def test_a_declined_place_doesnt_count_as_assigned(self):
        make_theme(self.service)
        make_assignment(self.service, make_user(), make_team_part(), reply="declined")
        page = self.page(self.pastor)
        self.assertContains(page, "Nobody yet")
        self.assertIn("Praise Team", current_step(page))

    def test_after_a_search_the_team_step_is_skipped(self):
        make_theme(self.service)
        SearchRun.objects.create(
            service=self.service,
            status=SearchRun.Status.DONE,
            finished_at=timezone.now(),
        )
        page = self.page(self.pastor)
        self.assertIn("Song Lineup", current_step(page))
        self.assertContains(page, "Nobody yet")

    def test_a_running_search_shows_its_progress(self):
        make_theme(self.service)
        SearchRun.objects.create(service=self.service, status=SearchRun.Status.RUNNING)
        page = self.page(self.pastor)
        self.assertContains(page, "Finding songs")
        self.assertContains(page, ">See the progress</a>")

    def test_a_draft_is_reviewed_and_confirmed(self):
        make_theme(self.service)
        make_lineup(self.service, [make_song(title="Opening")], confirmed=False)
        page = self.page(self.pastor)
        self.assertContains(page, "Next: confirm the lineup")
        self.assertContains(
            page,
            f'href="{url(self.service, "lineup_confirm")}" class="btn btn-primary chord-btn">Review and confirm',
        )

    def test_once_confirmed_the_panel_says_so(self):
        make_theme(self.service)
        make_assignment(self.service, make_user(), make_team_part())
        make_lineup(self.service, [make_song()], confirmed=True)
        page = self.page(self.pastor)
        self.assertNotContains(page, 'aria-current="step"')
        self.assertContains(page, "Lineup confirmed")
        self.assertContains(page, ">Open the lineup</a>")

    def test_without_the_permission_the_panel_says_what_it_waits_for(self):
        office = make_user(
            perms=["worship.view_worshipservice", "worship.change_lineup"]
        )
        page = self.page(office)
        self.assertContains(page, "Next: post the theme")
        self.assertContains(page, "Waiting for the theme to be posted.")
        self.assertNotContains(page, ">Post the theme</a>")

    def test_a_cancelled_service_has_no_panel(self):
        self.service.is_cancelled = True
        self.service.save()
        page = self.page(self.pastor)
        self.assertNotContains(page, 'id="next-step"')


class SongLineupPageTests(PlanningTestCase):
    def test_before_a_lineup_the_page_holds_the_suggestions(self):
        make_theme(self.service)
        page = self.page(self.leader, "lineup")
        self.assertContains(page, '<h1 class="h3 mb-0">Song Lineup')
        self.assertContains(page, 'id="suggestions"')
        self.assertContains(page, "Rank the song pool only")
        self.assertContains(page, 'aria-current="page"')
        self.assertNotContains(page, "Continue to confirm")
        self.assertEqual(self.page(self.member, "lineup").status_code, 404)

    def test_a_draft_leads_to_the_rundown_with_a_playlist_preview(self):
        make_theme(self.service)
        make_lineup(
            self.service,
            [
                make_song(title="Has a track"),
                make_song(title="No track", spotify_id=""),
            ],
            confirmed=False,
        )
        with self.settings(
            SPOTIFY_CLIENT_ID="id",
            SPOTIFY_CLIENT_SECRET="secret",
            SPOTIFY_TOKEN_KEY="5XL1mFBHVjXxHH9Wc7jvTeJ8ifQ7ER8QmFbx2V3Mh4g=",
        ):
            page = self.page(self.leader, "lineup")
        self.assertContains(
            page,
            f'href="{url(self.service, "lineup_confirm")}" class="btn btn-primary chord-btn">Continue to confirm',
        )
        self.assertContains(page, "1 song is saved as a playlist")
        self.assertContains(page, "No Spotify track, so not in the playlist: No track.")
        self.assertContains(page, "connect it</a> first")
        self.assertContains(page, "Listen before you confirm")


class RundownTests(PlanningTestCase):
    def setUp(self):
        super().setUp()
        make_theme(self.service, title="Grace that forgives", scripture="Psalm 23")
        self.lineup = make_lineup(
            self.service,
            [make_song(title="Opening"), make_song(title="Response")],
            confirmed=False,
        )

    def test_the_rundown_lists_what_will_be_confirmed(self):
        part = make_team_part(name="Bass guitar")
        make_assignment(
            self.service, make_user(first_name="Kim", last_name="Cruz"), part
        )
        make_assignment(self.service, make_user(), part, reply="declined")
        page = self.page(self.pastor, "lineup_confirm")
        for text in (
            "Sunday test",
            "Grace that forgives",
            "Psalm 23",
            "Opening",
            "Response",
            "Kim Cruz",
            "Bass guitar",
        ):
            self.assertContains(page, text)
        self.assertContains(page, "Before you confirm")
        self.assertContains(page, "1 declined place needs filling.")
        self.assertContains(page, "1 person hasn&#x27;t replied yet.")
        self.assertContains(page, "No chord sheet yet: Opening, Response.")
        self.assertContains(page, "No key set: Opening, Response.")
        self.assertContains(page, ">Confirm lineup</button>")
        self.assertIn("Confirm", current_step(page))

    def test_nobody_assigned_is_a_warning_that_doesnt_block(self):
        page = self.page(self.pastor, "lineup_confirm")
        self.assertContains(page, "Nobody is assigned to the Praise Team yet.")
        response = self.client.post(url(self.service, "lineup_confirm"))
        self.assertRedirects(response, url(self.service, "service"))
        self.lineup.refresh_from_db()
        self.assertTrue(self.lineup.is_confirmed)
        page = self.page(self.pastor, "lineup_confirm")
        self.assertNotContains(page, ">Confirm lineup</button>")
        self.assertNotContains(page, "Before you confirm")
        self.assertContains(page, "The team can see it.")

    def test_the_team_cant_open_the_rundown(self):
        self.assertEqual(self.page(self.member, "lineup_confirm").status_code, 403)

    def test_a_cancelled_service_cant_be_confirmed_from_the_rundown(self):
        self.service.is_cancelled = True
        self.service.save()
        page = self.page(self.pastor, "lineup_confirm")
        self.assertContains(page, "is cancelled")
        self.assertNotContains(page, ">Confirm lineup</button>")
