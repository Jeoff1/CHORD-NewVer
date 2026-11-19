"""Lineup rules (``apps/worship/lineups.py``): making a lineup from
suggestions, each review action, and the pastor's final say
(Design-Decisions, Phase 6; decision 0008; workflow review F4, F5, F7)."""

import datetime
import importlib

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from apps.accounts.models import Role
from apps.core.testing import (
    complete_setup,
    make_administrator,
    make_search_run,
    make_service,
    make_song,
    make_theme,
    make_user,
)
from apps.songs.analysis import apply_check_rules
from apps.songs.models import Song, WorshipCheckSettings
from apps.worship import lineups, suggesting
from apps.worship.lineups import LineupRefused
from apps.worship.models import Lineup

ACCEPTED = Song.WorshipCheck.ACCEPTED


def accepted_song(title, **fields):
    fields.setdefault("worship_check", ACCEPTED)
    fields.setdefault("worship_model_score", 0.9)
    fields.setdefault("worship_score", 0.9)
    fields.setdefault("analysed_at", timezone.now())
    return make_song(title=title, **fields)


def fresh(user):
    """The user again, without cached permissions."""
    return get_user_model().objects.get(pk=user.pk)


class LineupTestCase(TestCase):
    """A service with a theme, and a run that ranked six songs: the first
    four placed in the default template's four slots."""

    def setUp(self):
        complete_setup()
        self.service = make_service()
        make_theme(self.service)
        self.slots = list(self.service.template.slots.all())
        self.songs = [accepted_song(f"Song {letter}") for letter in "ABCDEF"]
        self.run = make_search_run(self.service, self.songs)
        self.leader = make_user(roles=["worship_leader"])
        self.pastor = make_user(
            roles=["pastoral_staff"], first_name="Ana", last_name="Cruz"
        )
        self.team_member = make_user(roles=["team_member"])
        self.office = make_user(roles=["office_staff"])

    def make_lineup(self):
        return lineups.create_from_run(self.service, self.leader)

    def items(self, lineup):
        return list(lineup.items.order_by("position"))

    def titles(self, lineup):
        return [item.song.title for item in self.items(lineup)]

    def reload(self, lineup):
        return Lineup.objects.get(pk=lineup.pk)


class CreateTests(LineupTestCase):
    def test_the_placed_suggestions_become_the_lineup_in_slot_order(self):
        lineup = self.make_lineup()
        items = self.items(lineup)
        self.assertEqual(self.titles(lineup), ["Song A", "Song B", "Song C", "Song D"])
        self.assertEqual([i.slot for i in items], self.slots)
        self.assertEqual([i.position for i in items], [0, 1, 2, 3])
        self.assertEqual(items[0].reasons, ["Reason for Song A."])
        self.assertEqual(lineup.status, Lineup.Status.DRAFT)
        self.assertEqual(lineup.run, self.run)

    def test_only_the_theme_reasons_are_kept_the_feel_reason_follows_the_slot(
        self,
    ):
        suggestion = self.run.suggestions.get(rank=1)
        suggestion.slot_reason = "Its feel isn't known yet; this slot asks for slow."
        suggestion.save()
        item = self.items(self.make_lineup())[0]
        self.assertEqual(item.reasons, ["Reason for Song A."])
        # Worked out for the slot it's in now: Opening, upbeat.
        self.assertEqual(
            item.slot_reason, "Its feel isn't known yet; this slot asks for upbeat."
        )

    def test_one_lineup_per_service(self):
        self.make_lineup()
        with self.assertRaisesMessage(LineupRefused, "already has a lineup"):
            self.make_lineup()

    def test_no_suggestions_no_lineup(self):
        service = make_service()
        with self.assertRaisesMessage(LineupRefused, "no suggested songs"):
            lineups.create_from_run(service, self.leader)


class ClosedServiceTests(LineupTestCase):
    """Workflow review F7: a cancelled or past service gets no suggestions
    and no new lineup."""

    def test_a_cancelled_service_gets_no_lineup(self):
        self.service.is_cancelled = True
        self.service.save()
        with self.assertRaisesMessage(LineupRefused, "is cancelled"):
            self.make_lineup()
        self.assertFalse(Lineup.objects.exists())

    def test_a_past_service_gets_no_lineup(self):
        self.service.starts_at = timezone.now() - datetime.timedelta(days=1)
        self.service.save()
        with self.assertRaisesMessage(LineupRefused, "already taken place"):
            self.make_lineup()

    def test_a_cancelled_or_past_service_gets_no_suggestions(self):
        cancelled = make_service(is_cancelled=True)
        make_theme(cancelled)
        past = make_service(starts_at=timezone.now() - datetime.timedelta(hours=1))
        make_theme(past)
        for service, words in ((cancelled, "is cancelled"), (past, "taken place")):
            with self.assertRaisesMessage(suggesting.RunRefused, words):
                suggesting.request_run(service, self.leader)
        self.assertFalse(cancelled.search_runs.exists() or past.search_runs.exists())

    def test_the_message_uses_the_church_label(self):
        complete_setup(
            labels={"worship_service": {"singular": "Gathering", "plural": "x"}}
        )
        self.service.is_cancelled = True
        self.assertEqual(
            suggesting.planning_closed(self.service),
            "This gathering is cancelled, so no songs are planned for it.",
        )

    def test_a_cancelled_service_lineup_cant_be_confirmed(self):
        lineup = self.make_lineup()
        self.service.is_cancelled = True
        self.service.save()
        with self.assertRaisesMessage(LineupRefused, "is cancelled"):
            lineups.confirm(lineup, self.leader)


class StoredCopyTests(LineupTestCase):
    """Workflow review F4: corrections to the suggestion run never
    rearrange the lineup or remove its songs."""

    def snapshot(self, lineup):
        return [(i.song_id, i.slot_id, i.position) for i in self.items(lineup)]

    def test_one_click_corrections_to_the_run_leave_the_lineup_alone(self):
        lineup = self.make_lineup()
        before = self.snapshot(lineup)
        first = self.songs[0]
        first.worship_check = Song.WorshipCheck.REJECTED
        first.save()
        second = self.songs[1]
        second.feel = "slow"
        second.save()
        suggesting.place_again(self.run)
        self.assertNotEqual(  # the run itself was placed again
            self.run.suggestions.get(song=first).slot, self.slots[0]
        )
        self.assertEqual(self.snapshot(lineup), before)

    def test_a_new_worship_check_leaves_the_lineup_alone(self):
        lineup = self.make_lineup()
        before = self.snapshot(lineup)
        Song.objects.update(reviewed_at=None)
        check = WorshipCheckSettings.load()
        check.pass_mark = 0.95  # every song now fails
        check.save()
        self.assertTrue(apply_check_rules())
        self.assertFalse(Song.objects.accepted().exists())
        self.assertEqual(self.snapshot(lineup), before)


class ReviewActionTests(LineupTestCase):
    def setUp(self):
        super().setUp()
        self.lineup = self.make_lineup()

    def item(self, title):
        return self.lineup.items.get(song__title=title)

    # Swap

    def test_swap_puts_a_ranked_alternative_in_the_same_place(self):
        item = self.item("Song B")
        item.key, item.notes = "G", "Start soft"
        item.save()
        lineups.swap(self.lineup, item, self.songs[4], self.leader)
        item.refresh_from_db()
        self.assertEqual(item.song.title, "Song E")
        self.assertEqual((item.slot, item.position), (self.slots[1], 1))
        self.assertEqual((item.key, item.notes), ("", ""))
        self.assertEqual(item.reasons, ["Reason for Song E."])

    def test_alternatives_leave_out_songs_in_the_lineup_and_same_titles(self):
        accepted_song("Song A (Live)")
        same = accepted_song("Song A (Live)")
        make_search_run(self.service, [*self.songs, same])
        offered = [s.song.title for s in lineups.alternatives(self.lineup)]
        self.assertEqual(offered, ["Song E", "Song F"])

    def test_swap_refuses_a_song_that_isnt_ranked(self):
        outsider = accepted_song("Outsider")
        with self.assertRaisesMessage(LineupRefused, "isn't one of the ranked"):
            lineups.swap(self.lineup, self.item("Song A"), outsider, self.leader)

    def test_swap_refuses_a_song_with_a_title_already_in_the_lineup(self):
        live = accepted_song("Song C (Live)")
        make_search_run(self.service, [*self.songs, live])
        with self.assertRaises(LineupRefused):
            lineups.swap(self.lineup, self.item("Song A"), live, self.leader)

    # Lock

    def test_a_locked_song_isnt_swapped_moved_or_removed(self):
        item = self.item("Song B")
        lineups.set_locked(self.lineup, item, True, self.leader)
        item.refresh_from_db()
        self.assertTrue(item.locked)
        with self.assertRaisesMessage(LineupRefused, "is locked"):
            lineups.swap(self.lineup, item, self.songs[4], self.leader)
        with self.assertRaisesMessage(LineupRefused, "is locked"):
            lineups.move(self.lineup, item, 1, self.leader)
        with self.assertRaisesMessage(
            LineupRefused, "Song A can't move into a locked song's place."
        ):
            lineups.move(self.lineup, self.item("Song A"), 1, self.leader)
        with self.assertRaisesMessage(
            LineupRefused, "Song C can't move into a locked song's place."
        ):
            lineups.move(self.lineup, self.item("Song C"), -1, self.leader)
        with self.assertRaisesMessage(LineupRefused, "is locked"):
            lineups.remove(self.lineup, item, self.leader)
        lineups.set_locked(self.lineup, item, False, self.leader)
        lineups.remove(self.lineup, self.item("Song B"), self.leader)

    # Reorder

    def test_moving_a_song_trades_places_and_slots(self):
        lineups.move(self.lineup, self.item("Song B"), -1, self.leader)
        items = self.items(self.lineup)
        self.assertEqual(self.titles(self.lineup)[:2], ["Song B", "Song A"])
        self.assertEqual([i.slot for i in items[:2]], self.slots[:2])
        lineups.move(self.lineup, self.item("Song B"), 1, self.leader)
        self.assertEqual(self.titles(self.lineup)[:2], ["Song A", "Song B"])

    def test_allowed_moves_match_what_move_refuses(self):
        lineups.set_locked(self.lineup, self.item("Song B"), True, self.leader)
        moves = lineups.allowed_moves(self.items(self.lineup))
        by_title = {
            self.lineup.items.get(pk=pk).song.title: allowed
            for pk, allowed in moves.items()
        }
        self.assertEqual(
            by_title,
            {
                "Song A": (False, False),  # first; below is locked
                "Song B": (False, False),  # locked
                "Song C": (False, True),  # above is locked
                "Song D": (True, False),  # last
            },
        )

    def test_a_moved_songs_feel_reason_names_its_new_slot(self):
        # Opening (upbeat), Praise (mid-tempo), Worship (slow), Response (slow).
        song = self.songs[0]
        song.feel = "mid"
        song.save()
        self.assertEqual(
            self.item("Song A").slot_reason,
            "Its feel (mid-tempo) isn't the upbeat this slot asks for, but it "
            "fit best.",
        )
        lineups.move(self.lineup, self.item("Song A"), 1, self.leader)
        self.assertEqual(self.item("Song A").slot, self.slots[1])
        self.assertEqual(self.item("Song A").slot_reason, "")  # mid in mid
        lineups.move(self.lineup, self.item("Song A"), 1, self.leader)
        moved = self.item("Song A")
        self.assertEqual(moved.slot, self.slots[2])
        self.assertEqual(
            moved.slot_reason,
            "Its feel (mid-tempo) isn't the slow this slot asks for, but it fit best.",
        )
        self.assertEqual(moved.reasons, ["Reason for Song A."])  # theme kept

    def test_swapped_added_and_regenerated_songs_get_their_slots_reason(self):
        # A swapped-in song brings its theme reasons, not the slot reason it
        # had in the run.
        choice = self.run.suggestions.get(song=self.songs[4])
        choice.slot_reason = "Its feel isn't known yet; this slot asks for slow."
        choice.save()
        lineups.swap(self.lineup, self.item("Song A"), self.songs[4], self.leader)
        swapped = self.item("Song E")
        self.assertEqual(swapped.reasons, ["Reason for Song E."])
        self.assertEqual(
            swapped.slot_reason, "Its feel isn't known yet; this slot asks for upbeat."
        )
        # Added into a slot.
        lineups.remove(self.lineup, self.item("Song C"), self.leader)
        slow = accepted_song("Quiet Song", feel="slow")
        lineups.add_from_pool(self.lineup, slow, self.slots[2], self.leader)
        self.assertEqual(self.item("Quiet Song").slot_reason, "")
        # Regenerated: every reason is for the slot the song is in.
        lineups.regenerate(self.lineup, self.leader)
        for item in self.items(self.lineup):
            self.assertNotIn("Its feel", " ".join(item.reasons))
            if item.slot.feel and not item.song.feel:
                self.assertIn(item.slot.get_feel_display().lower(), item.slot_reason)

    def test_a_song_cant_move_past_either_end(self):
        with self.assertRaisesMessage(LineupRefused, "can't move further"):
            lineups.move(self.lineup, self.item("Song A"), -1, self.leader)
        with self.assertRaisesMessage(LineupRefused, "can't move further"):
            lineups.move(self.lineup, self.item("Song D"), 1, self.leader)

    # Remove

    def test_removing_a_song_leaves_its_slot_empty(self):
        lineups.remove(self.lineup, self.item("Song B"), self.leader)
        self.assertEqual(self.titles(self.lineup), ["Song A", "Song C", "Song D"])
        self.assertEqual([i.position for i in self.items(self.lineup)], [0, 1, 2])
        self.assertEqual(lineups.open_slots(self.lineup), [self.slots[1]])

    # Add from the pool

    def test_adding_into_an_empty_slot_keeps_the_service_order(self):
        lineups.remove(self.lineup, self.item("Song B"), self.leader)
        pool_song = accepted_song("From the Pool")
        item = lineups.add_from_pool(self.lineup, pool_song, self.slots[1], self.leader)
        self.assertEqual(
            self.titles(self.lineup), ["Song A", "From the Pool", "Song C", "Song D"]
        )
        self.assertEqual(item.reasons, [lineups.ADDED_FROM_POOL])

    def test_adding_without_a_slot_goes_at_the_end(self):
        lineups.add_from_pool(self.lineup, accepted_song("Extra"), None, self.leader)
        self.assertEqual(self.titles(self.lineup)[-1], "Extra")
        self.assertIsNone(self.items(self.lineup)[-1].slot)

    def test_adding_refuses_a_filled_slot_and_a_same_title(self):
        with self.assertRaisesMessage(LineupRefused, "already has a song"):
            lineups.add_from_pool(
                self.lineup, accepted_song("New"), self.slots[0], self.leader
            )
        with self.assertRaisesMessage(LineupRefused, "already in the lineup"):
            lineups.add_from_pool(
                self.lineup, accepted_song("Song A (Live)"), None, self.leader
            )
        with self.assertRaisesMessage(LineupRefused, "already in it"):
            lineups.add_from_pool(self.lineup, self.songs[0], None, self.leader)

    def test_unchecked_and_failed_songs_can_be_added_with_a_warning(self):
        # The person's choice wins over the model: a song never checked (no
        # lyrics from LRCLIB) or failed by the model may be added.
        unchecked = make_song(
            title="No Lyrics Found", lyrics_status=Song.LyricsStatus.MISSING
        )
        failed = make_song(
            title="Failed By The Model", worship_check=Song.WorshipCheck.REJECTED
        )
        for song in (unchecked, failed):
            lineups.add_from_pool(self.lineup, song, None, self.leader)
        self.assertEqual(self.titles(self.lineup)[-2:], [unchecked.title, failed.title])
        self.assertEqual(
            lineups.check_warning(unchecked), "Not checked as a worship song yet."
        )
        self.assertEqual(
            lineups.check_warning(failed), "Didn't pass the worship check."
        )
        self.assertEqual(lineups.check_warning(self.songs[0]), "")

    def test_a_song_a_person_marked_not_worship_cant_be_added(self):
        marked = make_song(
            title="Marked By A Person",
            worship_check=Song.WorshipCheck.REJECTED,
            reviewed_at=timezone.now(),
            reviewed_by=self.leader,
        )
        with self.assertRaisesMessage(LineupRefused, "marked as not a worship song"):
            lineups.add_from_pool(self.lineup, marked, None, self.leader)
        self.assertNotIn("Marked By A Person", self.titles(self.lineup))
        self.assertEqual(lineups.check_warning(marked), "Marked as not a worship song.")

    def test_the_pool_search_offers_only_songs_that_could_be_added(self):
        accepted_song("Song A (Live)")
        accepted_song("Fresh Song")
        make_song(title="Fresh Unchecked")
        make_song(title="Fresh Failed", worship_check=Song.WorshipCheck.REJECTED)
        make_song(
            title="Fresh Marked",
            worship_check=Song.WorshipCheck.REJECTED,
            reviewed_at=timezone.now(),
        )
        found = sorted(s.title for s in lineups.addable_songs(self.lineup, "fresh"))
        self.assertEqual(found, ["Fresh Failed", "Fresh Song", "Fresh Unchecked"])
        everything = [s.title for s in lineups.addable_songs(self.lineup)]
        self.assertNotIn("Song A (Live)", everything)
        self.assertNotIn("Song A", everything)

    # Key and notes

    def test_key_and_notes(self):
        item = lineups.set_details(
            self.lineup, self.item("Song A"), "Eb", "Two choruses", self.leader
        )
        item.refresh_from_db()
        self.assertEqual((item.key, item.notes), ("Eb", "Two choruses"))

    # Regenerate

    def test_regenerating_keeps_locked_songs_and_refills_the_rest(self):
        locked = self.item("Song B")
        lineups.set_locked(self.lineup, locked, True, self.leader)
        lineups.remove(self.lineup, self.item("Song C"), self.leader)
        lineups.add_from_pool(self.lineup, accepted_song("Extra"), None, self.leader)
        newer = [self.songs[5], self.songs[1], self.songs[4], self.songs[3]]
        newer_run = make_search_run(self.service, newer)
        lineups.regenerate(self.lineup, self.leader)
        items = self.items(self.lineup)
        self.assertEqual(len(items), 4)
        by_slot = {i.slot: i.song.title for i in items}
        self.assertEqual(by_slot[self.slots[1]], "Song B")  # locked, kept
        self.assertEqual(
            sorted(t for t in by_slot.values() if t != "Song B"),
            ["Song D", "Song E", "Song F"],
        )
        self.assertNotIn("Extra", self.titles(self.lineup))
        self.assertEqual([i.slot for i in items], self.slots)
        self.assertEqual(self.reload(self.lineup).run, newer_run)

    def test_regenerating_never_repeats_a_locked_title(self):
        lineups.set_locked(self.lineup, self.item("Song A"), True, self.leader)
        live = accepted_song("Song A (Live)")
        make_search_run(self.service, [live, *self.songs[1:]])
        lineups.regenerate(self.lineup, self.leader)
        self.assertNotIn("Song A (Live)", self.titles(self.lineup))
        self.assertEqual(self.titles(self.lineup).count("Song A"), 1)

    def test_regenerating_needs_suggestions(self):
        service = make_service()
        lineup = Lineup.objects.create(service=service)
        with self.assertRaisesMessage(LineupRefused, "Find songs first"):
            lineups.regenerate(lineup, self.leader)


class FinalSayTests(LineupTestCase):
    """Design-Decisions, Phase 6: confirmation, the pastor's lock, the mark,
    reopening and sending back, for every role."""

    def setUp(self):
        super().setUp()
        self.lineup = self.make_lineup()

    def item(self, title):
        return self.lineup.items.get(song__title=title)

    def assert_leader_blocked(self):
        actions = [
            lambda: lineups.swap(
                self.lineup, self.item("Song A"), self.songs[4], self.leader
            ),
            lambda: lineups.move(self.lineup, self.item("Song A"), 1, self.leader),
            lambda: lineups.remove(self.lineup, self.item("Song A"), self.leader),
            lambda: lineups.add_from_pool(
                self.lineup, accepted_song("Blocked Add"), None, self.leader
            ),
            lambda: lineups.set_details(
                self.lineup, self.item("Song A"), "G", "", self.leader
            ),
            lambda: lineups.set_locked(
                self.lineup, self.item("Song A"), True, self.leader
            ),
            lambda: lineups.regenerate(self.lineup, self.leader),
        ]
        for action in actions:
            with self.assertRaisesMessage(LineupRefused, "has the final say"):
                action()
        self.assertFalse(lineups.may_change(self.reload(self.lineup), self.leader))

    def test_the_leader_can_confirm_without_locking(self):
        lineup = lineups.confirm(self.lineup, self.leader)
        self.assertTrue(lineup.is_confirmed)
        self.assertEqual(lineup.confirmed_by, self.leader)
        self.assertFalse(lineup.pastor_locked)
        self.assertIsNone(lineup.edited_at)

    def test_the_leaders_edit_to_a_confirmed_lineup_is_marked_without_a_lock(self):
        lineups.confirm(self.lineup, self.leader)
        before = timezone.now()
        lineups.move(self.lineup, self.item("Song A"), 1, self.leader)
        lineup = self.reload(self.lineup)
        self.assertTrue(lineup.is_confirmed)
        self.assertEqual(lineup.edited_by, self.leader)
        self.assertGreaterEqual(lineup.edited_at, before)
        self.assertFalse(lineup.edited_with_final_say)
        self.assertFalse(lineup.pastor_locked)
        # A later edit by the leader replaces the mark's time; still no lock.
        lineups.set_details(lineup, self.item("Song B"), "D", "", self.leader)
        self.assertTrue(lineups.may_change(self.reload(lineup), self.leader))

    def test_the_pastors_edit_replaces_the_leaders_mark(self):
        lineups.confirm(self.lineup, self.leader)
        lineups.move(self.lineup, self.item("Song A"), 1, self.leader)
        lineups.move(self.lineup, self.item("Song C"), 1, self.pastor)
        lineup = self.reload(self.lineup)
        self.assertEqual(lineup.edited_by, self.pastor)
        self.assertTrue(lineup.edited_with_final_say)
        self.assertTrue(lineup.pastor_locked)

    def test_the_leaders_mark_is_cleared_by_reopening_or_sending_back(self):
        for back_to_draft in (
            lambda: lineups.reopen(self.lineup, self.pastor),
            lambda: lineups.send_back(self.lineup, "Another opener", self.pastor),
        ):
            lineups.confirm(self.lineup, self.leader)
            lineups.move(self.lineup, self.item("Song A"), 1, self.leader)
            self.assertIsNotNone(self.reload(self.lineup).edited_at)
            lineup = back_to_draft()
            self.assertIsNone(lineup.edited_at)
            self.assertIsNone(lineup.edited_by)
            # Edits to the draft leave no mark.
            lineups.move(lineup, self.item("Song A"), -1, self.leader)
            self.assertIsNone(self.reload(lineup).edited_at)

    def test_the_pastor_can_confirm_and_that_locks_the_leader_out(self):
        lineup = lineups.confirm(self.lineup, self.pastor)
        self.assertTrue(lineup.is_confirmed)
        self.assertTrue(lineup.pastor_locked)
        self.assert_leader_blocked()
        # Anyone with the final say is never locked out.
        lineups.move(self.lineup, self.item("Song A"), 1, self.pastor)

    def test_the_pastors_edits_to_a_draft_dont_lock_the_leader_out(self):
        lineups.swap(self.lineup, self.item("Song A"), self.songs[4], self.pastor)
        lineup = self.reload(self.lineup)
        self.assertFalse(lineup.pastor_locked)
        self.assertIsNone(lineup.edited_at)
        self.assertTrue(lineups.may_change(lineup, self.leader))
        lineups.move(lineup, self.item("Song E"), 1, self.leader)

    def test_the_pastors_edit_to_a_confirmed_lineup_keeps_it_confirmed_and_marks_it(
        self,
    ):
        lineups.confirm(self.lineup, self.leader)
        before = timezone.now()
        lineups.swap(self.lineup, self.item("Song D"), self.songs[5], self.pastor)
        lineup = self.reload(self.lineup)
        self.assertTrue(lineup.is_confirmed)
        self.assertEqual(lineup.edited_by, self.pastor)
        self.assertGreaterEqual(lineup.edited_at, before)
        self.assertEqual(lineup.edited_by_name, "Ana Cruz")
        self.assertTrue(lineup.edited_with_final_say)
        self.assertTrue(lineup.pastor_locked)
        self.assert_leader_blocked()

    def test_locking_a_song_isnt_an_edit(self):
        lineups.confirm(self.lineup, self.leader)
        for user in (self.pastor, self.leader):
            lineups.set_locked(self.lineup, self.item("Song A"), True, user)
            lineups.set_locked(self.lineup, self.item("Song A"), False, user)
        lineup = self.reload(self.lineup)
        self.assertIsNone(lineup.edited_at)
        self.assertFalse(lineup.pastor_locked)

    def test_reopening_lifts_the_lock_and_makes_a_draft(self):
        lineups.confirm(self.lineup, self.leader)
        lineups.swap(self.lineup, self.item("Song A"), self.songs[4], self.pastor)
        lineup = lineups.reopen(self.lineup, self.pastor)
        self.assertEqual(lineup.status, Lineup.Status.DRAFT)
        self.assertFalse(lineup.pastor_locked)
        self.assertIsNone(lineup.edited_at)
        self.assertTrue(lineup.is_being_revised)
        self.assertFalse(lineups.visible_to(lineup, self.team_member))
        self.assertTrue(lineups.may_change(lineup, self.leader))
        lineups.move(lineup, self.item("Song E"), 1, self.leader)

    def test_only_the_final_say_reopens_or_sends_back(self):
        lineups.confirm(self.lineup, self.leader)
        for user in (self.leader, self.team_member, self.office):
            with self.assertRaisesMessage(LineupRefused, "final say"):
                lineups.reopen(self.lineup, user)
            with self.assertRaisesMessage(LineupRefused, "final say"):
                lineups.send_back(self.lineup, "Change it", user)
        self.assertTrue(self.reload(self.lineup).is_confirmed)

    def test_reopening_a_draft_is_refused(self):
        with self.assertRaisesMessage(LineupRefused, "isn't confirmed"):
            lineups.reopen(self.lineup, self.pastor)

    def test_sending_back_returns_to_draft_with_a_note(self):
        lineups.confirm(self.lineup, self.pastor)
        lineup = lineups.send_back(self.lineup, "  Use a slower closer.  ", self.pastor)
        self.assertEqual(lineup.status, Lineup.Status.DRAFT)
        self.assertFalse(lineup.pastor_locked)  # sending back reopens it
        self.assertEqual(lineup.sent_back_note, "Use a slower closer.")
        self.assertEqual(lineup.sent_back_by, self.pastor)
        self.assertTrue(lineup.is_being_revised)
        # Confirming again clears the note.
        lineup = lineups.confirm(lineup, self.leader)
        self.assertEqual(lineup.sent_back_note, "")

    def test_sending_back_a_draft_adds_a_note_and_needs_one(self):
        with self.assertRaisesMessage(LineupRefused, "Write a note"):
            lineups.send_back(self.lineup, "   ", self.pastor)
        lineup = lineups.send_back(self.lineup, "More upbeat", self.pastor)
        self.assertEqual(lineup.status, Lineup.Status.DRAFT)
        self.assertFalse(lineup.is_being_revised)

    def test_confirming_is_refused_twice_when_empty_and_for_other_roles(self):
        for user in (self.team_member, self.office):
            self.assertFalse(lineups.may_confirm(self.lineup, user))
            with self.assertRaisesMessage(LineupRefused, "may not confirm"):
                lineups.confirm(self.lineup, user)
        lineups.confirm(self.lineup, self.leader)
        with self.assertRaisesMessage(LineupRefused, "already confirmed"):
            lineups.confirm(self.lineup, self.pastor)
        empty = Lineup.objects.create(service=make_service())
        with self.assertRaisesMessage(LineupRefused, "Add a song"):
            lineups.confirm(empty, self.leader)

    def test_team_members_see_only_a_confirmed_lineup(self):
        self.assertFalse(lineups.visible_to(self.lineup, self.team_member))
        self.assertFalse(lineups.visible_to(self.lineup, self.office))
        for planner in (self.leader, self.pastor):
            self.assertTrue(lineups.visible_to(self.lineup, planner))
        lineup = lineups.confirm(self.lineup, self.leader)
        self.assertTrue(lineups.visible_to(lineup, self.team_member))

    def test_the_final_say_follows_the_permission_not_the_role(self):
        # A user with the permission, but not the Pastoral Staff role.
        elder = make_user(
            perms=[
                "worship.view_lineup",
                "worship.change_lineup",
                "worship.finalize_lineup",
            ]
        )
        lineup = lineups.confirm(self.lineup, elder)
        self.assertTrue(lineup.pastor_locked)
        lineups.reopen(lineup, elder)
        # A Pastoral Staff user whose role lost the permission.
        role = Role.objects.get(key="pastoral_staff")
        role.permissions.remove(Permission.objects.get(codename="finalize_lineup"))
        pastor = fresh(self.pastor)
        self.assertFalse(lineups.has_final_say(pastor))
        lineup = lineups.confirm(self.reload(lineup), pastor)
        self.assertFalse(lineup.pastor_locked)
        with self.assertRaisesMessage(LineupRefused, "final say"):
            lineups.reopen(lineup, pastor)

    def test_the_administrator_has_the_final_say_too(self):
        # Decision 0008: the Administrator holds every permission.
        admin = make_administrator()
        self.assertTrue(lineups.has_final_say(admin))
        self.assertTrue(lineups.confirm(self.lineup, admin).pastor_locked)


class DefaultRoleTests(TestCase):
    """The lineup permissions each default role gets (decision 0008; F5)."""

    def holds(self, key, codename):
        return Role.objects.get(key=key).permissions.filter(codename=codename).exists()

    def test_default_roles(self):
        expected = {
            "pastoral_staff": {"view", "add", "change", "finalize"},
            "worship_leader": {"view", "add", "change"},
            "team_member": {"view"},
            "office_staff": set(),
            "administrator": {"view", "add", "change", "finalize"},
        }
        for key, actions in expected.items():
            for action in ("view", "add", "change", "finalize"):
                with self.subTest(role=key, action=action):
                    self.assertEqual(
                        self.holds(key, f"{action}_lineup"), action in actions
                    )


class SavedReasonTextTests(SimpleTestCase):
    """Migration 0007 tidies reasons saved before the click-through fixes."""

    tidy = importlib.import_module("apps.worship.migrations.0007_lineup_reason_text")

    def test_the_versions_reason_is_rewritten_without_nested_brackets(self):
        old = (
            "Other versions in the pool: Hark! the Herald Angels Sing (Charles "
            "Wesley (1739)), Hark! (Live) (A Choir)."
        )
        self.assertEqual(
            self.tidy.versions_reason(old),
            "Other versions in the pool: Hark! the Herald Angels Sing, Charles "
            "Wesley (1739); Hark! (Live), A Choir.",
        )

    def test_other_reasons_and_unreadable_ones_stay_as_they_are(self):
        for reason in (
            "Its lyrics match the theme closely.",
            "Other versions in the pool: something unexpected.",
            "Other versions in the pool: Hark!, A Choir.",  # already new
        ):
            self.assertEqual(self.tidy.versions_reason(reason), reason)

    def test_stored_feel_reasons_leave_lineup_songs(self):
        self.assertEqual(
            self.tidy.lineup_reasons(
                [
                    "Its lyrics match the theme a little.",
                    "Its feel (mid-tempo) isn't the upbeat this slot asks for, "
                    "but it fit best.",
                    "Its feel isn't known yet; this slot asks for slow.",
                    "Other versions in the pool: Hymn (Choir (1900)).",
                ]
            ),
            [
                "Its lyrics match the theme a little.",
                "Other versions in the pool: Hymn, Choir (1900).",
            ],
        )
