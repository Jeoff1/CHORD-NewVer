"""The lineup pages: who sees a lineup, by page and by URL; each review
action through its view; confirmation and the final say; the mark; and
the audit trail (Design-Decisions, Phase 6; review F4, F5, F7)."""

import datetime

from django.test import TestCase
from django.urls import reverse
from django.utils import dateformat, timezone

from apps.audit.models import AuditEvent
from apps.core.testing import (
    complete_setup,
    first_church,
    make_administrator,
    make_search_run,
    make_service,
    make_song,
    make_theme,
    make_user,
)
from apps.songs.models import Song
from apps.worship import lineups, scheduling
from apps.worship.models import Lineup, SearchRun

ACCEPTED = Song.WorshipCheck.ACCEPTED


def url(service, name, **kwargs):
    return reverse(f"worship:{name}", kwargs={"public_id": service.public_id, **kwargs})


class LineupViewTestCase(TestCase):
    def setUp(self):
        complete_setup()
        self.service = make_service()
        make_theme(self.service, notes="The message in a few sentences.")
        self.songs = [
            make_song(title=f"Song {letter}", worship_check=ACCEPTED)
            for letter in "ABCDEF"
        ]
        self.run = make_search_run(self.service, self.songs)
        self.leader = make_user(roles=["worship_leader"])
        self.pastor = make_user(
            roles=["pastoral_staff"], first_name="Ana", last_name="Cruz"
        )
        self.team_member = make_user(roles=["team_member"])
        self.office = make_user(roles=["office_staff"])

    def make_lineup(self):
        return lineups.create_from_run(self.service, self.leader)

    def item(self, lineup, title):
        return lineup.items.get(song__title=title)

    def titles(self, lineup):
        return [i.song.title for i in lineup.items.order_by("position")]

    def login(self, user):
        self.client.force_login(user)


class MakingTheLineupTests(LineupViewTestCase):
    def test_the_panel_offers_to_save_the_suggestions(self):
        for user in (self.leader, self.pastor):
            self.login(user)
            response = self.client.get(url(self.service, "lineup"))
            self.assertContains(response, "Save these songs as the lineup")

    def test_the_leader_saves_the_suggestions_as_a_draft(self):
        self.login(self.leader)
        response = self.client.post(url(self.service, "lineup_create"))
        lineup = Lineup.objects.get(service=self.service)
        self.assertRedirects(response, url(self.service, "lineup"))
        self.assertEqual(self.titles(lineup), ["Song A", "Song B", "Song C", "Song D"])
        event = AuditEvent.objects.get(object_id=str(lineup.pk))
        self.assertEqual(event.action, AuditEvent.Action.CREATED)
        self.assertIn("Song A", event.changes["Songs"][1])
        # Once saved, the panel links the lineup instead.
        response = self.client.get(url(self.service, "lineup"))
        self.assertNotContains(response, "Save these songs as the lineup")
        self.assertContains(response, "changes here don't alter it")

    def test_others_may_not_make_it(self):
        for user in (self.team_member, self.office):
            self.login(user)
            self.assertEqual(
                self.client.post(url(self.service, "lineup_create")).status_code, 403
            )
        self.assertFalse(Lineup.objects.exists())

    def test_a_second_lineup_is_refused_with_a_message(self):
        self.make_lineup()
        self.login(self.leader)
        response = self.client.post(url(self.service, "lineup_create"), follow=True)
        self.assertContains(response, "already has a lineup")
        self.assertEqual(Lineup.objects.count(), 1)


class ClosedServiceViewTests(LineupViewTestCase):
    """Workflow review F7."""

    def test_a_cancelled_service_offers_no_suggestions_and_no_lineup(self):
        self.service.is_cancelled = True
        self.service.save()
        self.login(self.leader)
        page = self.client.get(url(self.service, "lineup"))
        self.assertContains(page, "is cancelled, so no songs are planned")
        self.assertNotContains(page, "Rank the song pool only")
        self.assertNotContains(page, "Save these songs as the lineup")
        response = self.client.post(url(self.service, "suggest"), follow=True)
        self.assertContains(response, "is cancelled")
        response = self.client.post(url(self.service, "lineup_create"), follow=True)
        self.assertContains(response, "is cancelled")
        self.assertEqual(self.service.search_runs.count(), 1)  # the setUp run
        self.assertFalse(Lineup.objects.exists())

    def test_a_past_service_offers_no_suggestions_and_no_lineup(self):
        self.service.starts_at = timezone.now() - datetime.timedelta(days=2)
        self.service.save()
        self.login(self.leader)
        response = self.client.post(url(self.service, "suggest"), follow=True)
        self.assertContains(response, "already taken place")
        self.client.post(url(self.service, "lineup_create"))
        self.assertFalse(Lineup.objects.exists())
        self.assertFalse(
            self.service.search_runs.filter(status=SearchRun.Status.QUEUED).exists()
        )


class StoredCopyViewTests(LineupViewTestCase):
    """Workflow review F4, through the one-click corrections."""

    def test_one_click_corrections_never_change_the_saved_lineup(self):
        lineup = self.make_lineup()
        suggestion = self.run.suggestions.get(song__title="Song A")
        self.login(self.leader)
        self.client.post(
            url(self.service, "suggestion_feel", pk=suggestion.pk), {"feel": "slow"}
        )
        self.client.post(url(self.service, "suggestion_not_worship", pk=suggestion.pk))
        self.assertEqual(
            Song.objects.get(title="Song A").worship_check,
            Song.WorshipCheck.REJECTED,
        )
        self.assertEqual(self.titles(lineup), ["Song A", "Song B", "Song C", "Song D"])
        page = self.client.get(url(self.service, "lineup"))
        self.assertContains(page, "Song A")


class VisibilityTests(LineupViewTestCase):
    """Team members see a lineup only once it is confirmed, by page and by
    URL; a reopened lineup shows them a note instead."""

    def all_urls(self, lineup):
        item = lineup.items.first()
        return {
            "get": [
                url(self.service, "lineup_add"),
                url(self.service, "lineup_swap", pk=item.pk),
                url(self.service, "lineup_item", pk=item.pk),
                url(self.service, "lineup_send_back"),
            ],
            "post": [
                url(self.service, "lineup_confirm"),
                url(self.service, "lineup_reopen"),
                url(self.service, "lineup_regenerate"),
                url(self.service, "lineup_add"),
                url(self.service, "lineup_send_back"),
                url(self.service, "lineup_swap", pk=item.pk),
                url(self.service, "lineup_item", pk=item.pk),
                url(self.service, "lineup_item_action", pk=item.pk, action="remove"),
            ],
        }

    def test_a_team_member_cant_see_an_unconfirmed_lineup_by_page_or_url(self):
        lineup = self.make_lineup()
        self.login(self.team_member)
        page = self.client.get(url(self.service, "service"))
        self.assertNotContains(page, "Song A")
        self.assertIsNone(page.context["lineup"])  # not even the draft object
        self.assertEqual(self.client.get(url(self.service, "lineup")).status_code, 404)
        urls = self.all_urls(lineup)
        for address in urls["get"]:
            self.assertEqual(self.client.get(address).status_code, 403, address)
        for address in urls["post"]:
            self.assertEqual(self.client.post(address).status_code, 403, address)
        self.assertEqual(self.titles(lineup), ["Song A", "Song B", "Song C", "Song D"])
        self.assertFalse(Lineup.objects.get().is_confirmed)

    def test_office_staff_see_no_lineup(self):
        self.make_lineup()
        lineups.confirm(Lineup.objects.get(), self.leader)
        self.login(self.office)
        self.assertEqual(self.client.get(url(self.service, "lineup")).status_code, 403)
        self.assertNotContains(self.client.get(url(self.service, "service")), "Song A")

    def test_a_team_member_sees_a_confirmed_lineup_without_the_planning(self):
        lineup = self.make_lineup()
        item = self.item(lineup, "Song A")
        item.key, item.notes = "G", "Start with the chorus"
        item.save()
        lineups.confirm(lineup, self.leader)
        self.login(self.team_member)
        page = self.client.get(url(self.service, "service"))
        self.assertContains(page, "Song A")
        self.assertContains(page, "Song A</a> · key of G")
        response = self.client.get(url(self.service, "lineup"))
        self.assertContains(response, "Song D")
        self.assertContains(response, "Start with the chorus")
        self.assertContains(response, "Confirmed by")
        self.assertNotContains(response, "Reason for Song A.")  # suggestion reasons
        self.assertNotContains(response, "Swap")
        self.assertNotContains(response, ">Confirm lineup<")
        self.assertNotContains(response, "Send back")

    def test_a_reopened_lineup_shows_the_team_a_note_instead(self):
        lineup = self.make_lineup()
        lineups.confirm(lineup, self.leader)
        lineups.reopen(lineup, self.pastor)
        self.login(self.team_member)
        for page in (
            self.client.get(url(self.service, "service")),
            self.client.get(url(self.service, "lineup")),
        ):
            self.assertEqual(page.status_code, 200)
            self.assertContains(page, "is being revised")
            self.assertNotContains(page, "Song A")
        # Sending back a confirmed lineup reopens it the same way.
        lineups.confirm(Lineup.objects.get(), self.leader)
        lineups.send_back(Lineup.objects.get(), "Change the closer", self.pastor)
        page = self.client.get(url(self.service, "lineup"))
        self.assertContains(page, "is being revised")
        self.assertNotContains(page, "Change the closer")

    def test_planners_see_the_draft(self):
        self.make_lineup()
        for user in (self.leader, self.pastor):
            self.login(user)
            response = self.client.get(url(self.service, "lineup"))
            self.assertContains(response, "Song A")
            self.assertContains(response, "Reason for Song A.")
            self.assertContains(response, "Draft")

    def test_no_lineup_is_404(self):
        # Phase 9C: before a lineup exists, the page holds the suggestions for
        # people who may suggest songs, and doesn't exist for the team.
        self.login(self.leader)
        self.assertContains(
            self.client.get(url(self.service, "lineup")), "Suggested lineup"
        )
        self.assertEqual(
            self.client.get(url(self.service, "lineup_confirm")).status_code, 404
        )
        self.login(self.team_member)
        self.assertEqual(self.client.get(url(self.service, "lineup")).status_code, 404)

    def test_switched_off_module_is_404(self):
        self.make_lineup()
        complete_setup(disabled_modules=["worship"])
        self.login(self.leader)
        self.assertEqual(self.client.get(url(self.service, "lineup")).status_code, 404)
        self.assertEqual(
            self.client.post(url(self.service, "lineup_confirm")).status_code, 404
        )
        self.assertTrue(Lineup.objects.exists())


class ReviewActionViewTests(LineupViewTestCase):
    def setUp(self):
        super().setUp()
        self.lineup = self.make_lineup()
        self.login(self.leader)

    def action(self, title, action):
        item = self.item(self.lineup, title)
        return self.client.post(
            url(self.service, "lineup_item_action", pk=item.pk, action=action)
        )

    def test_swap_page_and_swap(self):
        item = self.item(self.lineup, "Song A")
        page = self.client.get(url(self.service, "lineup_swap", pk=item.pk))
        self.assertContains(page, "Song E")
        self.assertNotContains(page, "Song B ·")
        response = self.client.post(
            url(self.service, "lineup_swap", pk=item.pk),
            {"song": self.songs[4].public_id},
        )
        self.assertRedirects(response, url(self.service, "lineup"))
        self.assertEqual(self.titles(self.lineup)[0], "Song E")
        event = AuditEvent.objects.filter(action=AuditEvent.Action.CHANGED).get()
        self.assertIn("Song E", event.changes["Songs"][1])

    def test_lock_unlock_move_and_remove(self):
        self.action("Song B", "lock")
        self.assertTrue(self.item(self.lineup, "Song B").locked)
        response = self.client.post(
            url(
                self.service,
                "lineup_item_action",
                pk=self.item(self.lineup, "Song B").pk,
                action="remove",
            ),
            follow=True,
        )
        self.assertContains(response, "is locked")
        self.action("Song B", "unlock")
        self.action("Song B", "up")
        self.assertEqual(self.titles(self.lineup)[:2], ["Song B", "Song A"])
        self.action("Song B", "down")
        self.assertEqual(self.titles(self.lineup)[:2], ["Song A", "Song B"])
        self.action("Song B", "remove")
        self.assertNotIn("Song B", self.titles(self.lineup))

    def test_an_unknown_action_is_404(self):
        self.assertEqual(self.action("Song A", "explode").status_code, 404)

    def test_add_from_the_pool(self):
        make_song(title="Pool Favourite", worship_check=ACCEPTED)
        page = self.client.get(url(self.service, "lineup_add"), {"q": "favourite"})
        self.assertContains(page, "Pool Favourite")
        self.client.post(
            url(self.service, "lineup_add"),
            {"song": Song.objects.get(title="Pool Favourite").public_id, "slot": ""},
        )
        self.assertEqual(self.titles(self.lineup)[-1], "Pool Favourite")

    def test_unchecked_and_failed_songs_are_added_with_a_warning(self):
        make_song(title="Fresh Unchecked", lyrics_status=Song.LyricsStatus.MISSING)
        make_song(title="Fresh Failed", worship_check=Song.WorshipCheck.REJECTED)
        make_song(
            title="Fresh Marked",
            worship_check=Song.WorshipCheck.REJECTED,
            reviewed_at=timezone.now(),
        )
        page = self.client.get(url(self.service, "lineup_add"), {"q": "fresh"})
        self.assertContains(page, "Fresh Unchecked")
        self.assertContains(page, "Fresh Failed")
        self.assertNotContains(page, "Fresh Marked")
        self.assertContains(page, "Not checked as a worship song yet.")
        self.assertContains(page, "Didn&#x27;t pass the worship check.")
        for title in ("Fresh Unchecked", "Fresh Failed"):
            self.client.post(
                url(self.service, "lineup_add"),
                {"song": Song.objects.get(title=title).public_id, "slot": ""},
            )
        self.assertEqual(
            self.titles(self.lineup)[-2:], ["Fresh Unchecked", "Fresh Failed"]
        )
        review = self.client.get(url(self.service, "lineup"))
        self.assertContains(review, "Not checked as a worship song yet.")
        self.assertContains(review, "Didn&#x27;t pass the worship check.")
        # A song a person marked "Not a worship song" is refused.
        response = self.client.post(
            url(self.service, "lineup_add"),
            {"song": Song.objects.get(title="Fresh Marked").public_id, "slot": ""},
            follow=True,
        )
        self.assertContains(response, "marked as not a worship song")
        self.assertNotIn("Fresh Marked", self.titles(self.lineup))
        # The warning is for the review: the team doesn't see it.
        lineups.confirm(self.lineup, self.leader)
        self.login(self.team_member)
        page = self.client.get(url(self.service, "lineup"))
        self.assertContains(page, "Fresh Failed")
        self.assertNotContains(page, "worship check")

    def test_key_and_notes(self):
        item = self.item(self.lineup, "Song A")
        page = self.client.get(url(self.service, "lineup_item", pk=item.pk))
        self.assertContains(page, "Service key")
        self.client.post(
            url(self.service, "lineup_item", pk=item.pk),
            {"key": "Bb", "notes": "Capo 1 for guitars"},
        )
        item.refresh_from_db()
        self.assertEqual((item.key, item.notes), ("Bb", "Capo 1 for guitars"))
        response = self.client.post(
            url(self.service, "lineup_item", pk=item.pk), {"key": "H", "notes": ""}
        )
        self.assertEqual(response.status_code, 200)  # not a key
        item.refresh_from_db()
        self.assertEqual(item.key, "Bb")

    def test_regenerate(self):
        self.action("Song C", "lock")
        make_search_run(self.service, [self.songs[5], *self.songs[:5]])
        self.client.post(url(self.service, "lineup_regenerate"))
        titles = self.titles(self.lineup)
        self.assertIn("Song F", titles)
        self.assertEqual(self.lineup.items.get(song__title="Song C").locked, True)


class ConfirmationViewTests(LineupViewTestCase):
    """Design-Decisions, Phase 6 tests through the pages, for every role."""

    def setUp(self):
        super().setUp()
        self.lineup = self.make_lineup()

    def reload(self):
        return Lineup.objects.get(pk=self.lineup.pk)

    def test_the_leader_confirms(self):
        self.login(self.leader)
        page = self.client.get(url(self.service, "lineup"))
        # Phase 9C: the lineup page leads to the rundown, which confirms.
        self.assertContains(page, ">Continue to confirm<")
        rundown = self.client.get(url(self.service, "lineup_confirm"))
        self.assertContains(rundown, ">Confirm lineup<")
        self.assertNotContains(page, "Send back")
        self.assertNotContains(page, ">Reopen<")
        self.client.post(url(self.service, "lineup_confirm"))
        lineup = self.reload()
        self.assertTrue(lineup.is_confirmed)
        self.assertFalse(lineup.pastor_locked)
        self.assertTrue(
            AuditEvent.objects.filter(changes__Status=["Draft", "Confirmed"]).exists()
        )

    def test_team_members_and_office_staff_may_not_confirm(self):
        for user in (self.team_member, self.office):
            self.login(user)
            self.assertEqual(
                self.client.post(url(self.service, "lineup_confirm")).status_code, 403
            )
        self.assertFalse(self.reload().is_confirmed)

    def test_the_pastors_confirmation_blocks_the_leader(self):
        self.login(self.pastor)
        self.client.post(url(self.service, "lineup_confirm"))
        self.assertTrue(self.reload().pastor_locked)
        self.login(self.leader)
        page = self.client.get(url(self.service, "lineup"))
        self.assertContains(page, "only pastors can change it")
        self.assertNotContains(page, "Swap")
        item = self.item(self.lineup, "Song A")
        response = self.client.get(url(self.service, "lineup_swap", pk=item.pk))
        self.assertRedirects(response, url(self.service, "lineup"))
        response = self.client.post(
            url(self.service, "lineup_swap", pk=item.pk),
            {"song": self.songs[4].public_id},
            follow=True,
        )
        self.assertContains(response, "has the final say")
        self.assertEqual(self.titles(self.lineup)[0], "Song A")
        for name in ("lineup_add", "lineup_send_back"):
            response = self.client.get(url(self.service, name))
            self.assertIn(response.status_code, (302, 403))

    def test_the_pastors_edit_keeps_it_confirmed_and_everyone_sees_the_mark(self):
        lineups.confirm(self.lineup, self.leader)
        self.login(self.pastor)
        item = self.item(self.lineup, "Song A")
        self.client.post(
            url(self.service, "lineup_swap", pk=item.pk),
            {"song": self.songs[4].public_id},
        )
        lineup = self.reload()
        self.assertTrue(lineup.is_confirmed)
        self.assertTrue(lineup.pastor_locked)
        stamp = self.stamp(lineup)
        for user in (self.leader, self.pastor, self.team_member):
            self.login(user)
            for address in (url(self.service, "lineup"), url(self.service, "service")):
                page = self.client.get(address)
                self.assertContains(page, f"Edited by Pastor (Ana Cruz), {stamp}")

    def stamp(self, lineup):
        """The mark's time as the pages show it, in the church's time zone."""
        with timezone.override(scheduling.church_time_zone(first_church())):
            return dateformat.format(timezone.localtime(lineup.edited_at), "M j, g:i A")

    def test_the_leaders_edit_to_a_confirmed_lineup_shows_changed_by(self):
        leader = make_user(
            roles=["worship_leader"], first_name="Ben", last_name="Reyes"
        )
        lineups.confirm(self.lineup, leader)
        self.login(leader)
        item = self.item(self.lineup, "Song B")
        self.client.post(
            url(self.service, "lineup_item_action", pk=item.pk, action="up")
        )
        lineup = self.reload()
        self.assertTrue(lineup.is_confirmed)
        self.assertFalse(lineup.pastor_locked)
        stamp = self.stamp(lineup)
        for user in (leader, self.pastor, self.team_member):
            self.login(user)
            for address in (url(self.service, "lineup"), url(self.service, "service")):
                page = self.client.get(address)
                self.assertContains(page, f"Changed by Ben Reyes, {stamp}")
                self.assertNotContains(page, "Edited by")
        # The leader can still edit: no lock.
        self.login(leader)
        self.assertContains(self.client.get(url(self.service, "lineup")), "Swap")

    def test_only_the_latest_mark_shows_and_reopening_clears_it(self):
        leader = make_user(
            roles=["worship_leader"], first_name="Ben", last_name="Reyes"
        )
        lineups.confirm(self.lineup, leader)
        lineups.move(self.lineup, self.item(self.lineup, "Song A"), 1, leader)
        lineups.move(self.lineup, self.item(self.lineup, "Song C"), 1, self.pastor)
        self.login(self.team_member)
        page = self.client.get(url(self.service, "lineup"))
        self.assertContains(page, "Edited by Pastor (Ana Cruz)")
        self.assertNotContains(page, "Changed by")
        lineups.reopen(self.lineup, self.pastor)
        lineups.confirm(self.lineup, leader)
        for user in (self.team_member, leader):
            self.login(user)
            page = self.client.get(url(self.service, "lineup"))
            self.assertNotContains(page, "Edited by")
            self.assertNotContains(page, "Changed by")

    def test_locking_a_song_leaves_no_mark(self):
        lineups.confirm(self.lineup, self.leader)
        self.login(self.leader)
        item = self.item(self.lineup, "Song A")
        self.client.post(
            url(self.service, "lineup_item_action", pk=item.pk, action="lock")
        )
        self.login(self.team_member)
        page = self.client.get(url(self.service, "lineup"))
        self.assertNotContains(page, "Changed by")
        self.assertIsNone(self.reload().edited_at)

    def test_the_mark_uses_the_church_label(self):
        complete_setup(labels={"pastor": {"singular": "Elder", "plural": "Elders"}})
        lineups.confirm(self.lineup, self.leader)
        lineups.move(self.lineup, self.item(self.lineup, "Song A"), 1, self.pastor)
        self.login(self.team_member)
        page = self.client.get(url(self.service, "lineup"))
        self.assertContains(page, "Edited by Elder (Ana Cruz)")
        self.login(self.leader)
        page = self.client.get(url(self.service, "lineup"))
        self.assertContains(page, "only elders can change it")

    def test_reopening_by_the_pastor_unblocks_the_leader(self):
        lineups.confirm(self.lineup, self.pastor)
        self.login(self.leader)
        self.assertEqual(
            self.client.post(url(self.service, "lineup_reopen")).status_code, 403
        )
        self.assertTrue(self.reload().is_confirmed)
        self.login(self.pastor)
        self.assertContains(self.client.get(url(self.service, "lineup")), ">Reopen<")
        self.client.post(url(self.service, "lineup_reopen"))
        lineup = self.reload()
        self.assertFalse(lineup.is_confirmed)
        self.assertFalse(lineup.pastor_locked)
        self.login(self.leader)
        item = self.item(self.lineup, "Song A")
        self.client.post(
            url(self.service, "lineup_swap", pk=item.pk),
            {"song": self.songs[4].public_id},
        )
        self.assertEqual(self.titles(self.lineup)[0], "Song E")

    def test_sending_back_with_a_note(self):
        lineups.confirm(self.lineup, self.pastor)
        self.login(self.leader)
        self.assertEqual(
            self.client.get(url(self.service, "lineup_send_back")).status_code, 403
        )
        self.login(self.pastor)
        page = self.client.get(url(self.service, "lineup_send_back"))
        self.assertContains(page, "Send the lineup back")
        response = self.client.post(url(self.service, "lineup_send_back"), {"note": ""})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(self.reload().is_confirmed)
        self.client.post(
            url(self.service, "lineup_send_back"), {"note": "A slower closer, please"}
        )
        lineup = self.reload()
        self.assertFalse(lineup.is_confirmed)
        self.assertFalse(lineup.pastor_locked)
        self.login(self.leader)
        page = self.client.get(url(self.service, "lineup"))
        self.assertContains(page, "A slower closer, please")
        self.assertContains(page, "Sent back by Ana Cruz")

    def test_send_back_without_a_lineup_is_404(self):
        self.login(self.pastor)
        other = make_service()
        self.assertEqual(
            self.client.get(url(other, "lineup_send_back")).status_code, 404
        )

    def test_a_user_with_the_final_say_but_not_the_role(self):
        elder = make_user(
            perms=[
                "worship.view_worshipservice",
                "worship.view_lineup",
                "worship.finalize_lineup",
            ]
        )
        self.login(elder)
        self.client.post(url(self.service, "lineup_confirm"))
        self.assertTrue(self.reload().pastor_locked)
        self.client.post(url(self.service, "lineup_reopen"))
        self.assertFalse(self.reload().is_confirmed)

    def test_the_administrator(self):
        self.login(make_administrator())
        self.client.post(url(self.service, "lineup_confirm"))
        self.assertTrue(self.reload().pastor_locked)


class PlanningNotesTests(LineupViewTestCase):
    """Workflow review F5: ``can_plan`` checks ``worship.change_lineup``,
    which now exists, so the worship leader sees the theme's notes and team
    members still don't."""

    def test_who_sees_the_theme_notes(self):
        for user, sees in (
            (self.leader, True),
            (self.pastor, True),
            (self.team_member, False),
            (self.office, False),
        ):
            self.login(user)
            page = self.client.get(url(self.service, "service"))
            if sees:
                self.assertContains(page, "The message in a few sentences.")
            else:
                self.assertNotContains(page, "The message in a few sentences.")


class ClickThroughFixTests(LineupViewTestCase):
    """Display fixes from the Phase 6 part A click-through (2026-11-19)."""

    def setUp(self):
        super().setUp()
        self.lineup = self.make_lineup()

    def move(self, title, action, **kwargs):
        item = self.item(self.lineup, title)
        return self.client.post(
            url(self.service, "lineup_item_action", pk=item.pk, action=action),
            **kwargs,
        )

    def test_arrows_hide_where_a_move_would_be_refused(self):
        lineups.set_locked(
            self.lineup, self.item(self.lineup, "Song B"), True, self.leader
        )
        self.login(self.leader)
        page = self.client.get(url(self.service, "lineup"))
        for hidden in (
            "Move Song A up",  # first
            "Move Song A down",  # below is locked
            "Move Song B up",  # locked
            "Move Song B down",
            "Move Song C up",  # above is locked
            "Move Song D down",  # last
        ):
            self.assertNotContains(page, f'aria-label="{hidden}"')
        for shown in ("Move Song C down", "Move Song D up"):
            self.assertContains(page, f'aria-label="{shown}"')
        # The server still refuses, worded for the song being moved.
        response = self.move("Song A", "down", follow=True)
        self.assertContains(
            response, "Song A can&#x27;t move into a locked song&#x27;s place."
        )
        self.assertEqual(self.titles(self.lineup)[:2], ["Song A", "Song B"])

    def test_after_a_move_the_reason_names_the_new_slots_feel(self):
        song = Song.objects.get(title="Song A")
        song.feel = "mid"
        song.save()
        self.login(self.leader)
        page = self.client.get(url(self.service, "lineup"))
        self.assertContains(page, "which asks for upbeat, but it fit best")
        self.move("Song A", "down")  # into Praise (mid-tempo)
        self.move("Song A", "down")  # into Worship (slow)
        page = self.client.get(url(self.service, "lineup"))
        self.assertContains(
            page,
            "Its feel (mid-tempo) doesn&#x27;t match this slot, which asks for slow, "
            "but it fit best.",
        )
        self.assertNotContains(page, "which asks for upbeat")
        self.assertContains(page, "Reason for Song A.")  # the theme reason stays

    def test_people_are_named_by_full_name_or_username(self):
        named = make_user(roles=["worship_leader"], first_name="Ben", last_name="Reyes")
        lineups.confirm(self.lineup, named)
        self.run.requested_by = named
        self.run.save()
        self.login(named)
        self.assertContains(
            self.client.get(url(self.service, "lineup")), "Confirmed by Ben Reyes"
        )
        panel = self.client.get(url(self.service, "lineup"))
        self.assertContains(panel, "by Ben Reyes")
        self.assertNotContains(panel, f"by {named.username}")
        # Without a name, the username.
        lineups.reopen(self.lineup, self.pastor)
        lineups.confirm(self.lineup, self.leader)
        self.assertContains(
            self.client.get(url(self.service, "lineup")),
            f"Confirmed by {self.leader.username}",
        )

    def test_the_song_page_names_the_reviewer(self):
        reviewer = make_user(first_name="Ana", last_name="Lim")
        song = Song.objects.get(title="Song A")
        song.reviewed_at, song.reviewed_by = timezone.now(), reviewer
        song.save()
        self.login(self.leader)
        page = self.client.get(
            reverse("songs:detail", kwargs={"public_id": song.public_id})
        )
        self.assertContains(page, "Reviewed by Ana Lim")
