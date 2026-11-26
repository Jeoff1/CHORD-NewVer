"""The suggestions panel on the Song Lineup page (Phase 9C), its settings pages, and who
may see them. Suggestions are an unconfirmed lineup: team members never see
them (Design-Decisions, Phase 5)."""

import datetime

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import Role
from apps.audit.models import AuditEvent
from apps.core.testing import (
    complete_setup,
    first_church,
    make_administrator,
    make_service,
    make_song,
    make_theme,
    make_user,
)
from apps.songs.models import Song, SpotifyLimit, ThemeTag
from apps.worship.models import SearchRun, Season, Suggestion, SuggestionSettings

Status = SearchRun.Status
SPOTIFY_KEYS = {"SPOTIFY_CLIENT_ID": "id", "SPOTIFY_CLIENT_SECRET": "secret"}
SETTINGS = reverse("worship:suggestion_settings")
SEASONS = reverse("worship:seasons_list")
NEW_SEASON = reverse("worship:seasons_create")


def url(service, name):
    return reverse(f"worship:{name}", kwargs={"public_id": service.public_id})


def finished_run(service, **fields):
    """A finished run with one song placed in the first slot and one other."""
    run = SearchRun.objects.create(
        service=service,
        status=fields.pop("status", Status.DONE),
        message=fields.pop("message", "Ranked 2 worship songs from the pool."),
        finished_at=timezone.now(),
        **fields,
    )
    first_slot = service.template.slots.first()
    placed = make_song(title="Placed Song", worship_check=Song.WorshipCheck.ACCEPTED)
    other = make_song(title="Other Song", worship_check=Song.WorshipCheck.ACCEPTED)
    for rank, (song, slot) in enumerate([(placed, first_slot), (other, None)], 1):
        Suggestion.objects.create(
            run=run,
            song=song,
            rank=rank,
            score=1.0 / rank,
            relevance=1.0,
            familiarity=0,
            season=0,
            recency=0,
            slot=slot,
            reasons=[f"Its lyrics match the theme closely (song {rank})."],
        )
    return run


class SuggestionViewTestCase(TestCase):
    def setUp(self):
        complete_setup()
        self.service = make_service()
        make_theme(self.service)
        self.leader = make_user(roles=["worship_leader"])
        self.pastor = make_user(roles=["pastoral_staff"])
        self.team_member = make_user(roles=["team_member"])


class PanelTests(SuggestionViewTestCase):
    def test_the_worship_leader_and_the_pastor_see_the_panel(self):
        finished_run(self.service)
        for user in (self.leader, self.pastor):
            self.client.force_login(user)
            response = self.client.get(url(self.service, "lineup"))
            self.assertContains(response, "Suggested lineup")
            self.assertContains(response, "Placed Song")
            self.assertContains(
                response, "Its lyrics match the theme closely (song 1)."
            )
            self.assertContains(response, "Other choices (1)")
            self.assertContains(response, "Rank the song pool only")

    def test_a_team_member_sees_no_suggestions_and_reaches_no_suggestion_url(self):
        # Design-Decisions, Phase 5: suggestions are hidden from team members.
        finished_run(self.service)
        self.client.force_login(self.team_member)
        response = self.client.get(url(self.service, "service"))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Suggested lineup")
        self.assertNotContains(response, "Placed Song")
        self.assertNotIn("placed", response.context)
        # The Song Lineup page doesn't exist for them before a lineup does.
        self.assertEqual(self.client.get(url(self.service, "lineup")).status_code, 404)
        self.assertEqual(
            self.client.get(url(self.service, "suggestions")).status_code, 403
        )
        self.assertEqual(
            self.client.post(url(self.service, "suggest")).status_code, 403
        )
        self.assertFalse(
            SearchRun.objects.filter(requested_by=self.team_member).exists()
        )

    def test_the_label_names_the_lineup(self):
        complete_setup(
            labels={"lineup": {"singular": "Set list", "plural": "Set lists"}}
        )
        self.client.force_login(self.leader)
        response = self.client.get(url(self.service, "lineup"))
        self.assertContains(response, "Suggested set list")

    def test_without_a_theme_the_panel_says_to_post_it(self):
        service = make_service()
        self.client.force_login(self.leader)
        response = self.client.get(url(service, "lineup"))
        self.assertContains(response, "Post the theme first")
        self.assertNotContains(response, "Rank the song pool only")

    def test_spotify_search_is_offered_only_when_spotify_is_set_up(self):
        self.client.force_login(self.leader)
        response = self.client.get(url(self.service, "lineup"))
        self.assertNotContains(response, "Find songs")
        self.assertContains(response, "Spotify isn't set up")
        with override_settings(**SPOTIFY_KEYS):
            response = self.client.get(url(self.service, "lineup"))
        self.assertContains(response, "Find songs")

    @override_settings(**SPOTIFY_KEYS)
    def test_a_spotify_pause_is_shown_and_only_the_pool_is_offered(self):
        now = timezone.now()
        SpotifyLimit.objects.create(
            occurred_at=now,
            reason=SpotifyLimit.Reason.QUOTA,
            blocked_until=now + datetime.timedelta(hours=24),
        )
        self.client.force_login(self.leader)
        response = self.client.get(url(self.service, "lineup"))
        self.assertContains(response, "CHORD has paused Spotify until")
        self.assertNotContains(response, "Find songs")
        self.assertContains(response, "Rank the song pool only")

    def test_an_active_run_shows_progress_and_reloads_itself(self):
        SearchRun.objects.create(
            service=self.service,
            status=Status.RUNNING,
            progress=40,
            stage="Looking up lyrics: Morning Song",
        )
        self.client.force_login(self.leader)
        response = self.client.get(url(self.service, "suggestions"))
        self.assertContains(response, 'id="suggestions"')
        self.assertContains(response, 'hx-trigger="every 2s"')
        self.assertContains(response, "Looking up lyrics: Morning Song")
        self.assertNotContains(response, "Rank the song pool only")
        self.assertNotContains(response, "<html")

    def test_a_finished_run_stops_reloading(self):
        finished_run(self.service)
        self.client.force_login(self.leader)
        response = self.client.get(url(self.service, "suggestions"))
        self.assertNotContains(response, "hx-trigger")
        self.assertContains(response, "Placed Song")

    def test_a_long_wait_says_how_to_start_the_worker(self):
        run = SearchRun.objects.create(service=self.service)
        SearchRun.objects.filter(pk=run.pk).update(
            created_at=timezone.now() - datetime.timedelta(minutes=5)
        )
        self.client.force_login(self.leader)
        response = self.client.get(url(self.service, "suggestions"))
        self.assertContains(response, "manage.py run_worker")

    def test_a_failed_run_shows_its_message(self):
        SearchRun.objects.create(
            service=self.service, status=Status.FAILED, message="Spotify answered 503."
        )
        self.client.force_login(self.leader)
        response = self.client.get(url(self.service, "lineup"))
        self.assertContains(response, "Spotify answered 503.")

    def test_run_details_need_the_view_search_run_permission(self):
        finished_run(self.service, phrases=["holy"], spotify_calls=5)
        only_suggest = make_user(
            perms=["worship.view_worshipservice", "worship.suggest_songs"]
        )
        self.client.force_login(only_suggest)
        response = self.client.get(url(self.service, "lineup"))
        self.assertContains(response, "Placed Song")
        self.assertNotContains(response, "About this search")
        self.client.force_login(self.leader)
        response = self.client.get(url(self.service, "lineup"))
        self.assertContains(response, "About this search")
        self.assertContains(response, "5 requests")

    def test_song_links_need_the_view_song_permission(self):
        run = finished_run(self.service)
        song = run.suggestions.first().song
        song_url = reverse("songs:detail", kwargs={"public_id": song.public_id})
        no_songs = make_user(
            perms=["worship.view_worshipservice", "worship.suggest_songs"]
        )
        self.client.force_login(no_songs)
        self.assertNotContains(self.client.get(url(self.service, "lineup")), song_url)
        self.client.force_login(self.leader)
        self.assertContains(self.client.get(url(self.service, "lineup")), song_url)


class SuggestTests(SuggestionViewTestCase):
    def test_asking_for_suggestions_queues_a_run(self):
        self.client.force_login(self.leader)
        response = self.client.post(url(self.service, "suggest"), {"source": "spotify"})
        self.assertRedirects(response, url(self.service, "lineup") + "#suggestions")
        run = SearchRun.objects.get()
        self.assertEqual(run.status, Status.QUEUED)
        self.assertTrue(run.use_spotify)
        self.assertEqual(run.requested_by, self.leader)

    def test_the_pool_only_choice(self):
        self.client.force_login(self.pastor)
        self.client.post(url(self.service, "suggest"), {"source": "pool"})
        self.assertFalse(SearchRun.objects.get().use_spotify)

    def test_a_second_request_while_one_runs_is_refused(self):
        self.client.force_login(self.leader)
        self.client.post(url(self.service, "suggest"))
        response = self.client.post(url(self.service, "suggest"), follow=True)
        self.assertContains(response, "already being found")
        self.assertEqual(SearchRun.objects.count(), 1)

    def test_no_theme_no_run(self):
        service = make_service()
        self.client.force_login(self.leader)
        response = self.client.post(url(service, "suggest"), follow=True)
        self.assertContains(response, "Post the service&#x27;s theme first")
        self.assertFalse(SearchRun.objects.exists())

    def test_only_post(self):
        self.client.force_login(self.leader)
        self.assertEqual(self.client.get(url(self.service, "suggest")).status_code, 405)

    def test_switched_off_module_is_404(self):
        complete_setup(disabled_modules=["worship"])
        self.client.force_login(make_administrator())
        for page in ("suggest", "suggestions"):
            self.assertEqual(self.client.get(url(self.service, page)).status_code, 404)
        self.assertEqual(self.client.get(SETTINGS).status_code, 404)
        self.assertEqual(self.client.get(SEASONS).status_code, 404)


class SuggestionSettingsTests(SuggestionViewTestCase):
    def data(self, **overrides):
        data = {
            "search_genres": " worship , gospel,, ",
            "phrases_per_theme": 3,
            "pages_per_phrase": 2,
            "market": "ph",
            "weight_relevance": 1.0,
            "weight_familiarity": 0.5,
            "weight_season": 0.2,
            "weight_recency": 0.4,
            "weight_feel": 0.2,
            "repeat_window_weeks": 6,
            "suggestions_kept": 20,
        }
        data.update(overrides)
        return data

    def test_the_recalibrated_defaults(self):
        options = SuggestionSettings.load(first_church())
        self.assertEqual(
            options.weights(),
            {
                "relevance": 1.0,
                "familiarity": 0.2,
                "season": 0.15,
                "recency": 0.3,
                "feel": 0.15,
            },
        )

    def test_the_worship_leader_changes_the_settings_and_it_is_audited(self):
        self.client.force_login(self.leader)
        self.assertEqual(self.client.get(SETTINGS).status_code, 200)
        response = self.client.post(SETTINGS, self.data())
        self.assertRedirects(response, SETTINGS)
        options = SuggestionSettings.load(first_church())
        self.assertEqual(options.search_genres, "worship, gospel")
        self.assertEqual(options.genres(), ["worship", "gospel"])
        self.assertEqual(options.market, "PH")
        self.assertEqual(options.weight_familiarity, 0.5)
        self.assertEqual(options.weight_feel, 0.2)
        event = AuditEvent.objects.get(action=AuditEvent.Action.CHANGED)
        self.assertEqual(event.changes["Familiarity weight"], ["0.2", "0.5"])
        self.assertEqual(event.changes["Feel mismatch weight"], ["0.15", "0.2"])

    def test_bad_values_are_refused(self):
        self.client.force_login(self.leader)
        response = self.client.post(SETTINGS, self.data(market="P1", weight_season=11))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "two-letter country code")
        self.assertEqual(SuggestionSettings.load(first_church()).market, "")

    def test_others_may_not_change_them(self):
        for user in (self.pastor, self.team_member):
            self.client.force_login(user)
            self.assertEqual(self.client.get(SETTINGS).status_code, 403)

    def test_the_settings_hub_links_the_new_pages(self):
        self.client.force_login(self.leader)
        response = self.client.get(SETTINGS)
        self.assertContains(response, SEASONS)


class SeasonTests(SuggestionViewTestCase):
    def data(self, **overrides):
        data = {
            "name": "Harvest time",
            "starts_on": "2026-11-01",
            "ends_on": "2026-11-30",
            "tags": [ThemeTag.objects.get(name="Thanksgiving").pk],
            "description": "",
            "sort_order": 0,
            "is_active": "on",
        }
        data.update(overrides)
        return data

    def test_none_are_defined_at_first(self):
        self.assertFalse(Season.objects.exists())

    def test_the_worship_leader_adds_a_season_with_its_tags(self):
        self.client.force_login(self.leader)
        response = self.client.post(NEW_SEASON, self.data())
        self.assertRedirects(response, SEASONS)
        season = Season.objects.get()
        self.assertEqual([tag.name for tag in season.tags.all()], ["Thanksgiving"])
        self.assertTrue(
            AuditEvent.objects.filter(action=AuditEvent.Action.CREATED).exists()
        )
        listing = self.client.get(SEASONS)
        self.assertContains(listing, "Nov 1 to Nov 30, 2026")
        self.assertContains(listing, "Thanksgiving")

    def test_a_dated_season_must_end_after_it_starts(self):
        self.client.force_login(self.leader)
        response = self.client.post(NEW_SEASON, self.data(ends_on="2026-10-01"))
        self.assertContains(response, "must end on or after its start")
        self.assertFalse(Season.objects.exists())

    def test_a_yearly_season_may_run_over_the_new_year(self):
        self.client.force_login(self.leader)
        self.client.post(
            NEW_SEASON,
            self.data(
                starts_on="2026-12-01", ends_on="2026-01-06", repeats_yearly="on"
            ),
        )
        season = Season.objects.get()
        self.assertTrue(season.repeats_yearly)
        self.assertContains(self.client.get(SEASONS), "every year")

    def test_a_season_needs_a_tag(self):
        self.client.force_login(self.leader)
        response = self.client.post(NEW_SEASON, self.data(tags=[]))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Season.objects.exists())

    def test_the_pastor_sees_seasons_and_the_team_does_not(self):
        self.client.force_login(self.pastor)
        self.assertEqual(self.client.get(SEASONS).status_code, 200)
        self.assertEqual(self.client.get(NEW_SEASON).status_code, 403)
        self.client.force_login(self.team_member)
        self.assertEqual(self.client.get(SEASONS).status_code, 403)


class DefaultRoleTests(TestCase):
    def permissions(self, key):
        role = Role.objects.get(key=key)
        return {
            f"{p.content_type.app_label}.{p.codename}" for p in role.permissions.all()
        }

    def test_only_the_planning_roles_may_suggest_songs(self):
        for key in ("worship_leader", "pastoral_staff", "administrator"):
            granted = self.permissions(key)
            self.assertIn("worship.suggest_songs", granted, key)
            self.assertIn("worship.view_searchrun", granted, key)
        for key in ("team_member", "office_staff"):
            granted = self.permissions(key)
            self.assertNotIn("worship.suggest_songs", granted, key)
            self.assertNotIn("worship.view_searchrun", granted, key)

    def test_the_worship_leader_owns_the_suggestion_settings_and_seasons(self):
        granted = self.permissions("worship_leader")
        self.assertIn("worship.change_suggestionsettings", granted)
        self.assertIn("worship.add_season", granted)
        self.assertNotIn(
            "worship.change_suggestionsettings", self.permissions("pastoral_staff")
        )


class CorrectionTests(SuggestionViewTestCase):
    """One-click corrections from the suggestions panel (smoke test fixes)."""

    def setUp(self):
        super().setUp()
        self.run = finished_run(self.service)
        self.placed = self.run.suggestions.get(rank=1)
        self.other = self.run.suggestions.get(rank=2)

    def feel_url(self, suggestion):
        return reverse(
            "worship:suggestion_feel",
            kwargs={"public_id": self.service.public_id, "pk": suggestion.pk},
        )

    def reject_url(self, suggestion):
        return reverse(
            "worship:suggestion_not_worship",
            kwargs={"public_id": self.service.public_id, "pk": suggestion.pk},
        )

    def test_the_panel_offers_corrections_to_people_who_may_correct_songs(self):
        self.client.force_login(self.leader)
        response = self.client.get(url(self.service, "lineup"))
        self.assertContains(response, self.feel_url(self.placed))
        self.assertContains(response, "Not a worship song")
        self.client.force_login(self.pastor)  # may suggest, not edit songs
        response = self.client.get(url(self.service, "lineup"))
        self.assertNotContains(response, self.feel_url(self.placed))

    def test_setting_a_feel_keeps_it_places_again_and_is_audited(self):
        self.client.force_login(self.leader)
        response = self.client.post(
            self.feel_url(self.other), {"feel": "upbeat"}, HTTP_HX_REQUEST="true"
        )
        self.assertContains(response, 'id="suggestions"')
        self.assertNotContains(response, "<html")
        song = self.other.song
        song.refresh_from_db()
        self.assertEqual(song.feel, "upbeat")
        self.assertTrue(song.feel_reviewed)
        self.assertFalse(song.is_reviewed)
        self.other.refresh_from_db()
        self.assertIsNotNone(self.other.slot)  # placed now
        event = AuditEvent.objects.get(object_id=str(song.pk))
        self.assertEqual(event.changes["Feel"], ["", "Upbeat"])

    def test_without_htmx_the_page_reloads(self):
        self.client.force_login(self.leader)
        response = self.client.post(self.feel_url(self.other), {"feel": "slow"})
        self.assertRedirects(response, url(self.service, "lineup") + "#suggestions")

    def test_a_feel_must_be_one_of_the_three(self):
        self.client.force_login(self.leader)
        response = self.client.post(self.feel_url(self.other), {"feel": "fast"})
        self.assertEqual(response.status_code, 400)
        self.assertFalse(AuditEvent.objects.exists())

    def test_not_a_worship_song_leaves_the_lineup_and_is_reviewed(self):
        self.client.force_login(self.leader)
        self.client.post(self.reject_url(self.placed), HTTP_HX_REQUEST="true")
        song = self.placed.song
        song.refresh_from_db()
        self.assertEqual(song.worship_check, Song.WorshipCheck.REJECTED)
        self.assertEqual(song.reviewed_by, self.leader)
        response = self.client.get(url(self.service, "lineup"))
        self.assertNotContains(response, "Placed Song")
        self.other.refresh_from_db()
        self.assertIsNotNone(self.other.slot)  # took the free slot

    def test_corrections_need_both_permissions_and_this_service(self):
        for user in (self.pastor, self.team_member):
            self.client.force_login(user)
            response = self.client.post(self.feel_url(self.other), {"feel": "slow"})
            self.assertEqual(response.status_code, 403)
        elsewhere = make_service()
        self.client.force_login(self.leader)
        response = self.client.post(
            reverse(
                "worship:suggestion_feel",
                kwargs={"public_id": elsewhere.public_id, "pk": self.other.pk},
            ),
            {"feel": "slow"},
        )
        self.assertEqual(response.status_code, 404)


class ThemeNotesHintTests(SuggestionViewTestCase):
    def test_a_theme_without_notes_gets_a_hint(self):
        self.client.force_login(self.pastor)
        response = self.client.get(url(self.service, "lineup"))
        self.assertContains(response, "The theme has no sermon notes yet")
        self.assertContains(response, url(self.service, "theme"))

    def test_notes_are_not_required_and_the_hint_goes_with_them(self):
        theme = self.service.theme
        theme.notes = "The grace that forgives and restores."
        theme.save()
        self.client.force_login(self.leader)
        response = self.client.get(url(self.service, "lineup"))
        self.assertNotContains(response, "has no sermon notes")
