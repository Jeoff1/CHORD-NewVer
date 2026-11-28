"""Proving an email address with a 6-digit code (28 Nov 2026).

A visitor who requests a service without an account gives their name, email
and a password; ``start`` emails them a code, and ``check`` returns what
their account needs once they type it. Only a keyed hash of the code is
stored, and the password only as Django's password hash.

Limits: a code lasts ``CODE_MINUTES``; ``MAX_ATTEMPTS`` wrong tries end it;
a new code can be sent ``RESEND_SECONDS`` after the last one, and at most
``MAX_SENDS_PER_HOUR`` codes go to one address in an hour. A new code ends
the earlier ones.
"""

import datetime
import secrets

from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.crypto import constant_time_compare, salted_hmac

from .models import EmailCode

CODE_MINUTES = 10
MAX_ATTEMPTS = 5
RESEND_SECONDS = 60
MAX_SENDS_PER_HOUR = 5
_SALT = "chord.accounts.verification"


class CodeRefused(Exception):
    """Why a code can't be sent or doesn't match; the message is for the
    person."""


def _hash(email, code):
    return salted_hmac(_SALT, f"{email.lower()}:{code}").hexdigest()


def _normal(email):
    return email.strip().lower()


def _latest(email):
    return (
        EmailCode.objects.filter(email=_normal(email), used_at__isnull=True)
        .order_by("-created_at", "-pk")
        .first()
    )


def seconds_until_resend(email):
    """How long before another code may go to ``email``; 0 when it may."""
    last = (
        EmailCode.objects.filter(email=_normal(email)).order_by("-created_at").first()
    )
    if last is None:
        return 0
    passed = (timezone.now() - last.created_at).total_seconds()
    return max(0, int(RESEND_SECONDS - passed + 0.999))


def start(email, pending):
    """Email a new code to ``email``, keeping ``pending`` for the account.
    Raises ``CodeRefused`` when one was sent too recently or too often."""
    email = _normal(email)
    wait = seconds_until_resend(email)
    if wait:
        raise CodeRefused(f"A code was just sent. You can ask for another in {wait} s.")
    hour_ago = timezone.now() - datetime.timedelta(hours=1)
    if (
        EmailCode.objects.filter(email=email, created_at__gte=hour_ago).count()
        >= MAX_SENDS_PER_HOUR
    ):
        raise CodeRefused("Too many codes were sent to this address. Try again later.")
    code = f"{secrets.randbelow(10**6):06d}"
    now = timezone.now()
    EmailCode.objects.filter(email=email, used_at__isnull=True).update(used_at=now)
    EmailCode.objects.create(
        email=email,
        code_hash=_hash(email, code),
        pending=pending,
        expires_at=now + datetime.timedelta(minutes=CODE_MINUTES),
    )
    context = {"code": code, "minutes": CODE_MINUTES}
    send_mail(
        render_to_string("accounts/email/signup_code_subject.txt", context).strip(),
        render_to_string("accounts/email/signup_code_email.txt", context),
        settings.DEFAULT_FROM_EMAIL,
        [email],
    )


def resend(email):
    """Send a new code for the same pending account."""
    latest = _latest(email)
    if latest is None:
        raise CodeRefused("Start again: fill in your details.")
    start(email, latest.pending)


def check(email, code):
    """The pending account for ``email`` when ``code`` is its current code;
    the code can't be used again. Raises ``CodeRefused`` otherwise."""
    latest = _latest(email)
    code = (code or "").strip().replace(" ", "")
    if latest is None:
        raise CodeRefused("That code has expired. Ask for a new one.")
    if latest.expires_at <= timezone.now():
        raise CodeRefused("That code has expired. Ask for a new one.")
    if latest.attempts >= MAX_ATTEMPTS:
        raise CodeRefused("Too many wrong tries. Ask for a new code.")
    if not constant_time_compare(latest.code_hash, _hash(latest.email, code)):
        latest.attempts += 1
        latest.save(update_fields=["attempts"])
        left = MAX_ATTEMPTS - latest.attempts
        if left <= 0:
            raise CodeRefused("Too many wrong tries. Ask for a new code.")
        raise CodeRefused(
            f"That code isn't right. {left} {'try' if left == 1 else 'tries'} left."
        )
    latest.used_at = timezone.now()
    latest.save(update_fields=["used_at"])
    return latest.pending
