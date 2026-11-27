"""Registering a church (Phase 9B, decision 0014).

A church needs only its name (decision 0001); since 27 Nov 2026 the person
may also give its details and public profile while registering (address,
contact number, email, logo, description, public or not), all optional.
Registering creates, in one transaction: the person's account (when they aren't signed
in yet), the church with its slug, its defaults (``seed_church``) and the
person's Administrator Membership. If any step fails, nothing is left
behind.
"""

from django.db import transaction

from apps.audit.models import AuditEvent
from apps.audit.services import record_change

from .models import ChurchProfile
from .seeding import seed_church


@transaction.atomic
def register_church(name, *, user=None, account_form=None, details=None):
    """Create the church ``name`` with ``user`` (or the account
    ``account_form`` describes, a valid unsaved sign-up form) as its first
    Administrator. ``details`` holds the optional fields of the church
    (``ChurchRegistrationForm.details()``). Returns ``(church, user)``."""
    from apps.accounts.models import Membership, Role
    from apps.accounts.roles import ADMINISTRATOR

    if user is None:
        user = account_form.save()
        record_change(user, user, AuditEvent.Action.CREATED, church=None)
    church = ChurchProfile.objects.create(name=name.strip(), **(details or {}))
    seed_church(church)
    administrator = Role.objects.get(church=church, key=ADMINISTRATOR)
    Membership.objects.create(user=user, church=church).roles.add(administrator)
    record_change(
        user,
        church,
        AuditEvent.Action.CREATED,
        {"Church name": ["", church.name]},
        church=church,
    )
    return church, user
