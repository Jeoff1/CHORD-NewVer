"""The Spotify and LRCLIB clients, against FakeHttp (never the network)."""

from django.test import SimpleTestCase, TestCase

from apps.core import http
from apps.core.testing import FakeHttp
from apps.songs import lyrics, spotify
from apps.songs.lyrics import LrclibClient, LyricsError
from apps.songs.models import Song
from apps.songs.spotify import SpotifyClient, SpotifyError, SpotifyNotConfigured

SEARCH = f"{spotify.API}/search"
GET = f"{lyrics.API}/get"
FIND = f"{lyrics.API}/search"
# Public-domain words (Amazing Grace, 1779).
HYMN = "Amazing grace, how sweet the sound\nThat saved a wretch like me"


def track(n, title="Song", artist="Artist"):
    return {
        "id": f"id{n}",
        "name": f"{title} {n}",
        "artists": [{"name": artist}, {"name": "Guest"}],
        "album": {"name": "Album"},
        "duration_ms": 245_400,
    }


def page(items, more=False):
    return {"tracks": {"items": items, "next": "https://next" if more else None}}


def client(**kwargs):
    kwargs.setdefault("sleep", lambda seconds: None)
    return SpotifyClient("id", "secret", **kwargs)


class SpotifySearchTests(TestCase):
    """Uses the database: every call checks the shared Spotify block.
    The 429 safeguards are tested in ``test_spotify_limits.py``."""

    def web(self):
        web = FakeHttp()
        web.reply("POST", spotify.TOKEN_URL, {"access_token": "t1", "expires_in": 3600})
        return web

    def test_needs_credentials(self):
        with self.assertRaises(SpotifyNotConfigured):
            SpotifyClient("", "")
        with self.assertRaises(SpotifyNotConfigured):
            SpotifyClient.from_settings()  # the test runner clears them

    def test_reads_tracks_and_sends_the_app_token(self):
        with self.web() as web:
            web.reply("GET", SEARCH, page([track(1), None]))
            result = client().search_tracks("grace")
        self.assertEqual(len(result.tracks), 1)
        found = result.tracks[0]
        self.assertEqual(found.spotify_id, "id1")
        self.assertEqual(found.artist, "Artist, Guest")
        self.assertEqual(found.album, "Album")
        self.assertEqual(found.length_seconds, 245)
        token_call, search_call = web.calls
        self.assertTrue(token_call["headers"]["Authorization"].startswith("Basic "))
        self.assertEqual(token_call["body"], "grant_type=client_credentials")
        self.assertEqual(search_call["headers"]["Authorization"], "Bearer t1")
        self.assertEqual(search_call["params"]["type"], "track")
        self.assertEqual(search_call["params"]["limit"], "10")

    def test_reads_pages_until_one_is_short(self):
        def pages(call):
            offset = int(call["params"]["offset"])
            items = [track(offset + i) for i in range(10 if offset < 20 else 3)]
            return 200, page(items, more=True)

        with self.web() as web:
            web.reply("GET", SEARCH, pages)
            result = client().search_tracks("grace", pages=5)
        self.assertEqual(result.pages_read, 3)
        self.assertEqual(len(result.tracks), 23)
        offsets = [c["params"]["offset"] for c in web.calls if c["path"] == SEARCH]
        self.assertEqual(offsets, ["0", "10", "20"])

    def test_stops_when_there_is_no_next_page(self):
        with self.web() as web:
            web.reply("GET", SEARCH, page([track(i) for i in range(10)]))
            result = client().search_tracks("grace", pages=3)
        self.assertEqual(result.pages_read, 1)

    def test_genre_filter_and_retry_without_it(self):
        def reply(call):
            return 200, page([] if "genre:" in call["params"]["q"] else [track(1)])

        with self.web() as web:
            web.reply("GET", SEARCH, reply)
            result = client().search_tracks("grace", genre="christian rock")
        queries = [c["params"]["q"] for c in web.calls if c["path"] == SEARCH]
        self.assertEqual(queries, ['grace genre:"christian rock"', "grace"])
        self.assertTrue(result.genre_dropped)
        self.assertEqual(len(result.tracks), 1)

    def test_genre_filter_kept_when_it_finds_songs(self):
        with self.web() as web:
            web.reply("GET", SEARCH, page([track(1)]))
            result = client().search_tracks("grace", genre="worship", market="PH")
        self.assertFalse(result.genre_dropped)
        self.assertEqual(web.calls[-1]["params"]["q"], "grace genre:worship")
        self.assertEqual(web.calls[-1]["params"]["market"], "PH")

    def test_token_is_reused(self):
        with self.web() as web:
            web.reply("GET", SEARCH, page([]))
            spotify_client = client()
            spotify_client.search_tracks("a")
            spotify_client.search_tracks("b")
        self.assertEqual(web.paths().count(spotify.TOKEN_URL), 1)

    def test_expired_token_is_renewed_once(self):
        answers = iter([(401, {}), (200, page([track(1)]))])
        with self.web() as web:
            web.reply("GET", SEARCH, lambda call: next(answers))
            result = client().search_tracks("grace")
        self.assertEqual(len(result.tracks), 1)
        self.assertEqual(web.paths().count(spotify.TOKEN_URL), 2)

    def test_error_carries_spotify_message(self):
        with self.web() as web:
            web.reply("GET", SEARCH, {"error": {"message": "Bad query"}}, status=400)
            with self.assertRaisesMessage(SpotifyError, "400: Bad query"):
                client().search_tracks("grace")

    def test_refused_credentials(self):
        with FakeHttp() as web:
            web.reply("POST", spotify.TOKEN_URL, {"error": "invalid"}, status=400)
            with self.assertRaisesMessage(SpotifyError, "credentials"):
                client().search_tracks("grace")

    def test_no_network(self):
        def down(*args, **kwargs):
            raise http.HttpError("offline")

        with http.use_transport(down):
            with self.assertRaisesMessage(SpotifyError, "couldn't be reached"):
                client().search_tracks("grace")

    def test_get_track(self):
        with self.web() as web:
            web.reply("GET", f"{spotify.API}/tracks/id7", track(7))
            found = client().get_track("id7")
        self.assertEqual(found.title, "Song 7")


class LrclibTests(SimpleTestCase):
    def setUp(self):
        self.now = 100.0
        self.waits = []

    def sleep(self, seconds):
        self.waits.append(seconds)
        self.now += seconds

    def lrclib(self, **kwargs):
        return LrclibClient(
            "CHORD test", sleep=self.sleep, clock=lambda: self.now, **kwargs
        )

    def test_lookup_by_title_artist_album_and_length(self):
        with FakeHttp() as web:
            web.reply("GET", GET, {"plainLyrics": HYMN, "instrumental": False})
            result = self.lrclib().lookup("Amazing Grace", "Artist", "Hymns", 245)
        self.assertEqual(result, lyrics.LyricsResult(Song.LyricsStatus.FOUND, HYMN))
        call = web.calls[0]
        self.assertEqual(call["headers"]["User-Agent"], "CHORD test")
        self.assertEqual(
            call["params"],
            {
                "track_name": "Amazing Grace",
                "artist_name": "Artist",
                "album_name": "Hymns",
                "duration": "245",
            },
        )

    def test_user_agent_comes_from_settings(self):
        self.assertTrue(LrclibClient().user_agent.startswith("CHORD"))

    def test_synced_lyrics_lose_their_timestamps(self):
        synced = "[00:12.34] Amazing grace\n[00:15.00][01:15.00] How sweet"
        with FakeHttp() as web:
            web.reply("GET", GET, {"plainLyrics": None, "syncedLyrics": synced})
            result = self.lrclib().lookup("Amazing Grace", "Artist")
        self.assertEqual(result.lyrics, "Amazing grace\nHow sweet")

    def test_instrumental_and_empty(self):
        with FakeHttp() as web:
            web.reply("GET", GET, {"instrumental": True})
            self.assertEqual(
                self.lrclib().lookup("Interlude", "Band").status,
                Song.LyricsStatus.INSTRUMENTAL,
            )
        with FakeHttp() as web:
            web.reply("GET", GET, {"plainLyrics": "  "})
            self.assertEqual(
                self.lrclib().lookup("Hum", "Band").status, Song.LyricsStatus.MISSING
            )

    def test_miss_falls_back_to_search_and_picks_the_closest_length(self):
        records = [
            {"duration": 300, "plainLyrics": "Live words"},
            {"duration": 244, "plainLyrics": "Studio words"},
            {"duration": 245, "plainLyrics": None, "syncedLyrics": None},
        ]
        with FakeHttp() as web:
            web.reply("GET", GET, {"name": "TrackNotFound"}, status=404)
            web.reply("GET", FIND, records)
            result = self.lrclib().lookup("Song", "Artist", "Album", 245)
        self.assertEqual(result.lyrics, "Studio words")
        self.assertEqual(
            web.calls[1]["params"], {"track_name": "Song", "artist_name": "Artist"}
        )

    def test_search_with_nothing_usable(self):
        with FakeHttp() as web:
            web.reply("GET", GET, {}, status=404)
            web.reply("GET", FIND, [])
            self.assertEqual(
                self.lrclib().lookup("Song", "Artist").status, Song.LyricsStatus.MISSING
            )
        with FakeHttp() as web:
            web.reply("GET", GET, {}, status=404)
            web.reply("GET", FIND, [{"instrumental": True}])
            self.assertEqual(
                self.lrclib().lookup("Song", "Artist").status,
                Song.LyricsStatus.INSTRUMENTAL,
            )

    def test_requests_are_spaced_out(self):
        with FakeHttp() as web:
            web.reply("GET", GET, {}, status=404)
            web.reply("GET", FIND, [])
            lrclib = self.lrclib(delay=0.4)
            lrclib.lookup("One", "Artist")
            self.now += 0.1
            lrclib.lookup("Two", "Artist")
        # No wait before the first request; then 0.4 s between the rest,
        # less the 0.1 s that had already passed.
        self.assertEqual([round(w, 2) for w in self.waits], [0.4, 0.3, 0.4])

    def test_rate_limit_waits_and_retries(self):
        answers = iter([(429, {}), (200, {"plainLyrics": HYMN})])
        with FakeHttp() as web:
            web.reply(
                "GET", GET, lambda call: next(answers), headers={"retry-after": "7"}
            )
            result = self.lrclib(delay=0).lookup("Song", "Artist")
        self.assertEqual(result.status, Song.LyricsStatus.FOUND)
        self.assertEqual(self.waits, [7.0])

    def test_rate_limit_that_lasts_is_an_error(self):
        with FakeHttp() as web:
            web.reply("GET", GET, {}, status=429, headers={"retry-after": "soon"})
            with self.assertRaisesMessage(LyricsError, "429"):
                self.lrclib(delay=0, max_retries=1).lookup("Song", "Artist")
        self.assertEqual(self.waits, [5])

    def test_server_errors(self):
        with FakeHttp() as web:
            web.reply("GET", GET, {}, status=500)
            with self.assertRaises(LyricsError):
                self.lrclib().lookup("Song", "Artist")
        with FakeHttp() as web:
            web.reply("GET", GET, {}, status=404)
            web.reply("GET", FIND, {}, status=503)
            with self.assertRaises(LyricsError):
                self.lrclib().lookup("Song", "Artist")

    def test_no_network(self):
        def down(*args, **kwargs):
            raise http.HttpError("offline")

        with http.use_transport(down):
            with self.assertRaisesMessage(LyricsError, "couldn't be reached"):
                self.lrclib().lookup("Song", "Artist")

    def test_tests_cannot_reach_the_network(self):
        with self.assertRaisesMessage(AssertionError, "must not use the network"):
            http.request("GET", "https://lrclib.net/api/get")
