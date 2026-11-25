"""The settings every test runs under, in the main process and in each
parallel worker.

On Windows, ``manage.py test --parallel`` starts each worker as a fresh
process that runs only Django's own test setup, so ``ChordTestRunner``'s
setup would never reach it. ``ChordParallelTestSuite`` runs ``install()`` in
each worker. A worker imports this module before Django is ready, so it
must not import models (``apps/core/testing.py`` does).
"""

from django.test.runner import ParallelTestSuite

from . import http


def _no_network(method, url, **kwargs):
    raise AssertionError(
        f"A test tried to reach {url}. Tests must not use the network: wrap "
        "the code in FakeHttp (apps/core/testing.py)."
    )


def install():
    """Block the network, use the keyword ML engine, unset Spotify, and hash
    passwords quickly. Returns the transport it replaced."""
    from django.conf import settings

    settings.ML_ENGINE = "keyword"
    settings.SPOTIFY_CLIENT_ID = ""
    settings.SPOTIFY_CLIENT_SECRET = ""
    settings.SPOTIFY_TOKEN_KEY = ""
    settings.SPOTIFY_REDIRECT_URI = ""
    # The real hashers are slow on purpose; tests create thousands of users.
    # Tests only, never in config/settings.py.
    settings.PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
    return http.set_transport(_no_network)


def _worker_setup(*args):
    install()


class ChordParallelTestSuite(ParallelTestSuite):
    # A plain module-level function, as Django's own stub is: Django pickles
    # it (process_setup.__func__) to send it to each worker.
    process_setup = _worker_setup
