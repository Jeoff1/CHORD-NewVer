"""Who belongs to a church, and what a church's administrator may do to an
account (Phase 9B, decision 0014).

An account is the person's own and may belong to several churches. A
church's administrator manages its Membership (roles, removal) but may
change the account itself (username, names, email, active, password) only
when it belongs to that church alone, so one church can never take over an
account another church relies on. Superusers' accounts are never managed
by a church.
"""

from django.contrib.auth import get_user_model

from .models import Membership
from .roles import administrators


def belongs_elsewhere(user, church):
    """Whether ``user`` has a Membership (active or not) in another church."""
    return Membership.objects.filter(user=user).exclude(church=church).exists()


def may_manage_account(user, church):
    """Whether ``church``'s administrators may change ``user``'s account
    itself: its username, names, email, active status and password."""
    return not user.is_superuser and not belongs_elsewhere(user, church)


def is_last_administrator(user, church):
    """Whether ``user`` is the only active administrator ``church`` has."""
    admins = administrators(church)
    return (
        admins.filter(pk=user.pk).exists() and not admins.exclude(pk=user.pk).exists()
    )


class AccountNotFound(Exception):
    """No single account matches; the message says why."""


def find_account(identifier):
    """The one account whose username is exactly ``identifier``, or whose
    email is (emails ignore case). Never a partial match, so nobody can
    browse other people's accounts."""
    identifier = identifier.strip()
    User = get_user_model()
    if not identifier:
        raise AccountNotFound("Give a username or an email.")
    user = User.objects.filter(username=identifier).first()
    if user is not None:
        return user
    if "@" in identifier:
        found = list(User.objects.filter(email__iexact=identifier)[:2])
        if len(found) > 1:
            raise AccountNotFound(
                "More than one account uses that email. Ask for the username."
            )
        if found:
            return found[0]
    raise AccountNotFound("No account has that username or email.")
