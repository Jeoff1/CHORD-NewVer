"""Cleaning up Spotify search results (pipeline stage 4; Design-Decisions,
Phase 5: live versions)."""

from django.test import SimpleTestCase

from apps.songs.cleanup import base_title, clean_tracks, is_version
from apps.songs.spotify import Track


def track(title, artist="Band", album="Album", spotify_id=None):
    return Track(spotify_id or f"{title}-{artist}", title, (artist,), album)


def titles(tracks):
    return [t.title for t in clean_tracks(tracks)]


class CleanupTests(SimpleTestCase):
    def test_a_live_only_song_is_kept(self):
        self.assertEqual(titles([track("Holy Ground (Live)")]), ["Holy Ground (Live)"])

    def test_a_live_duplicate_of_a_studio_song_is_dropped(self):
        studio_first = [track("Holy Ground"), track("Holy Ground (Live)")]
        live_first = [track("Holy Ground - Live"), track("Holy Ground")]
        self.assertEqual(titles(studio_first), ["Holy Ground"])
        self.assertEqual(titles(live_first), ["Holy Ground"])

    def test_two_versions_without_a_studio_one_keep_the_first(self):
        found = [track("Holy Ground (Live)"), track("Holy Ground (Acoustic)")]
        self.assertEqual(titles(found), ["Holy Ground (Live)"])

    def test_karaoke_instrumental_and_backing_tracks_are_always_dropped(self):
        found = [
            track("Holy Ground (Karaoke Version)"),
            track("Holy Ground", album="Instrumental Worship Hits"),
            track("Holy Ground - Backing Track"),
            track("Holy Ground (In the Style of Band)"),
            track("Morning Song"),
        ]
        self.assertEqual(titles(found), ["Morning Song"])

    def test_the_same_track_twice_counts_once(self):
        self.assertEqual(titles([track("Morning Song")] * 2), ["Morning Song"])

    def test_the_same_title_by_another_artist_is_another_song(self):
        found = [track("Holy", artist="Band"), track("Holy", artist="Choir")]
        self.assertEqual(len(clean_tracks(found)), 2)

    def test_first_seen_order_is_kept(self):
        found = [track("B"), track("A"), track("C")]
        self.assertEqual(titles(found), ["B", "A", "C"])

    def test_base_title(self):
        self.assertEqual(base_title("Holy (Live)"), "holy")
        self.assertEqual(base_title("Holy - 2011 Remaster"), "holy")
        self.assertEqual(base_title("Holy (feat. Choir)"), "holy")
        self.assertEqual(base_title("Holy Ground"), "holy ground")
        self.assertTrue(is_version("Holy (Live)"))
        self.assertFalse(is_version("Holy"))
