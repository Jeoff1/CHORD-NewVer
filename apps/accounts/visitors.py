"""Accounts made by visitors who request a service (28 Nov 2026).

Once the emailed code is right (``verification.check``), ``create_account``
makes the account from what the visitor gave, with the password hash they
chose, and links it to the church they asked: a Membership with the Church
Member role. They can still request services from other churches.
"""

from django.db import transaction

from apps.audit.models import AuditEvent
from apps.audit.services import record_change

from .forms import username_from_email
from .models import Membership, Role, User
from .roles import CHURCH_MEMBER
from .verification import CodeRefused


@transaction.atomic
def create_account(pending, church):
    """The visitor's new account, a member of ``church``. Raises
    ``CodeRefused`` if another account took the email meanwhile."""
    email = pending["email"]
    if User.objects.filter(email__iexact=email).exists():
        raise CodeRefused("An account already uses this email. Sign in instead.")
    user = User(
        username=username_from_email(email),
        email=email,
        first_name=pending.get("first_name", ""),
        last_name=pending.get("last_name", ""),
        # Already Django's password hash (verification.py never sees the
        # password itself).
        password=pending["password"],
    )
    user.save()
    membership = Membership.objects.create(user=user, church=church)
    roles = list(Role.objects.filter(church=church, key=CHURCH_MEMBER))
    membership.roles.add(*roles)
    record_change(
        user,
        user,
        AuditEvent.Action.CREATED,
        {
            "Account": ["", "Made when requesting a service"],
            "Membership": ["", "Joined this church"],
            "Roles": ["", [role.title for role in roles]],
        },
        church=church,
    )
    return user
