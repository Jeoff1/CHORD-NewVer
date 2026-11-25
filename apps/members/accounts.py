"""Accounts for members, made in a batch (Phase 9A, A4; Design-Decisions,
"Adviser comments, 24 Nov").

- Only current members without an account get one; the rest are skipped,
  with the reason.
- The username comes from the name ("rosa.lim", then "rosa.lim2", ...);
  the email from the member record. Each account is linked to its member.
- Each gets a random **Temporary Password**, returned to the caller to show
  once. It is never stored in plain text, logged or put in the Audit Trail,
  and the person must change it at first sign-in
  (``User.must_change_password``).
- Each member's row is locked while its account is made, so pressing twice
  never makes two accounts for one person.
"""

import csv
import io
from dataclasses import dataclass

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils.crypto import get_random_string
from django.utils.text import slugify

from apps.accounts.models import Membership
from apps.accounts.views import USER_AUDIT_FIELDS
from apps.audit.models import AuditEvent
from apps.audit.services import diff, record_change, snapshot
from apps.church.models import ChurchProfile

from .models import Member
from .services import member_audit_fields

# No look-alike characters (0/O, 1/l/I), so a password read aloud or from
# paper is typed right.
PASSWORD_CHARACTERS = "abcdefghjkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789"
PASSWORD_LENGTH = 12


@dataclass
class Created:
    member: Member
    user: object
    password: str


@dataclass
class Skipped:
    member: Member
    reason: str


def eligible(members=None):
    """Current members without an account."""
    members = Member.objects.all() if members is None else members
    return members.current().filter(user__isnull=True)


def username_for(member):
    """A free username made from the member's name."""
    User = get_user_model()
    base = slugify(f"{member.first_name} {member.last_name}").replace("-", ".")
    base = (base or "member")[:140]
    candidate, n = base, 1
    while User.objects.filter(username__iexact=candidate).exists():
        n += 1
        candidate = f"{base}{n}"
    return candidate


def temporary_password():
    return get_random_string(PASSWORD_LENGTH, PASSWORD_CHARACTERS)


def create_accounts(members, role, actor):
    """Make an account with ``role`` for each of ``members`` that may get
    one. Returns ``(created, skipped)``; each Created holds the Temporary
    Password, which exists nowhere else."""
    User = get_user_model()
    created, skipped = [], []
    for member in members:
        with transaction.atomic():
            locked = Member.objects.select_for_update().get(pk=member.pk)
            if locked.user_id:
                skipped.append(Skipped(locked, "already has an account"))
                continue
            if locked.is_archived:
                skipped.append(Skipped(locked, "is archived"))
                continue
            password = temporary_password()
            user = User.objects.create_user(
                username=username_for(locked),
                password=password,
                email=locked.email,
                first_name=locked.first_name,
                last_name=locked.last_name,
            )
            user.must_change_password = True
            user.save(update_fields=["must_change_password"])
            # Members is open only to the first church for now (Phase 9B,
            # decision 0014), so batch accounts join that church.
            membership = Membership.objects.create(
                user=user, church=ChurchProfile.load()
            )
            if role is not None:
                membership.roles.add(role)
            record_change(
                actor,
                user,
                AuditEvent.Action.CREATED,
                diff({}, snapshot(user, USER_AUDIT_FIELDS)),
            )
            before = snapshot(locked, member_audit_fields())
            locked.user = user
            locked.save(update_fields=["user", "updated_at"])
            record_change(
                actor,
                locked,
                AuditEvent.Action.CHANGED,
                diff(before, snapshot(locked, member_audit_fields())),
            )
            created.append(Created(locked, user, password))
    return created, skipped


def _safe(value):
    """A CSV cell a spreadsheet won't run as a formula."""
    value = str(value)
    return f"'{value}" if value[:1] in ("=", "+", "-", "@", "\t", "\r") else value


def accounts_csv(created, sign_in_url):
    """The new accounts as CSV text, for the result page to offer once."""
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["Name", "Username", "Temporary password", "Sign in at"])
    for row in created:
        name = f"{row.member.first_name} {row.member.last_name}".strip()
        writer.writerow(
            [_safe(name), _safe(row.user.username), row.password, sign_in_url]
        )
    return "﻿" + buffer.getvalue()  # BOM so Excel reads UTF-8
