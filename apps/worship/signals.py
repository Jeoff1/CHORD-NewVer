"""Signals other Modules listen to, so Worship never depends on them.

``lineup_changed`` is sent, inside the change's transaction, after a lineup
is confirmed (``event=CONFIRMED``) or a confirmed lineup's songs are edited
(``event=EDITED``). Arguments: ``lineup`` and ``user``, the person who did
it. Teams turns it into Notifications (Design-Decisions, Phase 8).
"""

from django.dispatch import Signal

CONFIRMED = "confirmed"
EDITED = "edited"

lineup_changed = Signal()
