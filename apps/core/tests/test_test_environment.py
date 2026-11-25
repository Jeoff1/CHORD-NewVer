"""Every test, in the main process or a parallel worker, runs under the
setup in apps/core/test_environment.py."""

from django.conf import settings
from django.test import SimpleTestCase

from apps.core import http


class TestEnvironmentTests(SimpleTestCase):
    def test_network_is_blocked(self):
        with self.assertRaisesMessage(AssertionError, "must not use the network"):
            http.request("GET", "https://example.com/")

    def test_keyword_engine_and_no_spotify(self):
        self.assertEqual(settings.ML_ENGINE, "keyword")
        self.assertEqual(settings.SPOTIFY_CLIENT_SECRET, "")
        self.assertEqual(settings.SPOTIFY_TOKEN_KEY, "")

    def test_fast_password_hasher(self):
        self.assertEqual(
            settings.PASSWORD_HASHERS,
            ["django.contrib.auth.hashers.MD5PasswordHasher"],
        )
