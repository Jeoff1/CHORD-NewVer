"""Registering a church (Phase 9B, decision 0014).

A church needs only its name (decision 0001); since 27 Nov 2026 the person
may also give its details and public profile while registering (address,
contact number, email, logo, description, public or not), all optional.
Registering creates, in one transaction: the person's account (when they aren't signed
in yet), the church with its slug, its defaults (``seed_church``) and the
person's Administrator Membership. If any step fails, nothing is left
behind. A church whose values pass the model's checks is marked set up
(``setup_requirements_met``), so the person goes straight to the dashboard
instead of the setup wizard (owner, 27 Nov 2026).
"""

from django.core.exceptions import ValidationError
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
    church.setup_completed = setup_requirements_met(church)
    if church.setup_completed:
        church.save(update_fields=["setup_completed", "updated_at"])
    record_change(
        user,
        church,
        AuditEvent.Action.CREATED,
        {
            "Church name": ["", church.name],
            "Setup completed": ["", "yes" if church.setup_completed else "no"],
        },
        church=church,
    )
    return church, user


def setup_requirements_met(church):
    """Whether ``church`` needs nothing more from the setup wizard (owner,
    27 Nov 2026). Registration asks for everything the wizard's steps need
    (the name) and offers the rest; every other setting (currency, time
    zone, Labels, Modules, the homepage's switches) starts from a default
    the church changes later in its settings. So a church whose saved values
    pass the model's own checks is set up; one that doesn't still goes
    through the wizard."""
    try:
        church.full_clean()
    except ValidationError:
        return False
    return True


def mark_set_up(church, user):
    """Mark an older church set up once its saved values pass the same
    checks registration uses (owner, 27 Nov 2026: nobody is sent through the
    setup wizard any more; the settings pages hold everything it asked).
    Records the change in the audit trail. Returns whether the church is set
    up; one whose values fail the checks stays not set up, so it stays out
    of the directory until its details are fixed in Settings."""
    if church.setup_completed:
        return True
    if not setup_requirements_met(church):
        return False
    church.setup_completed = True
    church.save(update_fields=["setup_completed", "updated_at"])
    record_change(
        user,
        church,
        AuditEvent.Action.CHANGED,
        {"Setup completed": ["no", "yes"]},
        church=church,
    )
    return True
