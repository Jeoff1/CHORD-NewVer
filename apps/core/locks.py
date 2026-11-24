"""PostgreSQL advisory locks: one process at a time, across the machine.

The search worker holds ``SEARCH_WORKER`` for as long as it runs, so a
second worker (or ``process_songs``) refuses to start. This keeps Spotify
and LRCLIB to one caller (Design-Decisions, Phase 5; decision 0007).

The lock belongs to the database session: it is released when the block
ends, or by PostgreSQL if the process dies.
"""

import hashlib
from contextlib import contextmanager

from django.db import connection as default_connection

SEARCH_WORKER = "chord.search-worker"
# Booking a time on the calendar (Phase 9A, A5).
BOOKINGS = "chord.bookings"


class LockHeld(Exception):
    """Another database session already holds the lock."""


def lock_key(name):
    """The signed 64-bit number PostgreSQL identifies the lock by."""
    digest = hashlib.blake2b(name.encode("utf-8"), digest_size=8).digest()
    return int.from_bytes(digest, "big", signed=True)


@contextmanager
def advisory_lock(name, connection=None):
    """Hold the advisory lock ``name`` for the block; raise ``LockHeld``
    straight away when another session has it."""
    connection = connection or default_connection
    key = lock_key(name)
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_try_advisory_lock(%s)", [key])
        if not cursor.fetchone()[0]:
            raise LockHeld(name)
    try:
        yield
    finally:
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_unlock(%s)", [key])


def wait_for_transaction_lock(name, connection=None):
    """Wait for the advisory lock ``name`` and hold it until the current
    transaction ends. Call it inside ``transaction.atomic()``: two people
    booking the calendar at once take turns (``BOOKINGS``)."""
    connection = connection or default_connection
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_advisory_xact_lock(%s)", [lock_key(name)])
