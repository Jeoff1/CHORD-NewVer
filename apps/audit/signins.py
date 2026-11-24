"""Recording sign-ins in the Audit Trail (Phase 9A, A3).

Connected to Django's ``user_logged_in``, ``user_logged_out`` and
``user_login_failed`` signals in ``AuditConfig.ready()``. A failed sign-in
records only the username that was tried, and the account it names when
there is one; never the password.
"""

from django.contrib.auth import get_user_model

from .models import SignInEvent

Kind = SignInEvent.Kind
USERNAME_LENGTH = SignInEvent._meta.get_field("username").max_length


def on_signed_in(sender, request, user, **kwargs):
    SignInEvent.objects.create(
        kind=Kind.SIGNED_IN, user=user, username=user.get_username()
    )


def on_signed_out(sender, request, user, **kwargs):
    if user is None:  # signing out without a session
        return
    SignInEvent.objects.create(
        kind=Kind.SIGNED_OUT, user=user, username=user.get_username()
    )


def on_failed(sender, credentials, request=None, **kwargs):
    # Django has already masked the password in ``credentials``; only the
    # username is read.
    User = get_user_model()
    username = str(credentials.get(User.USERNAME_FIELD) or "")[:USERNAME_LENGTH]
    SignInEvent.objects.create(
        kind=Kind.FAILED,
        user=User.objects.filter(**{User.USERNAME_FIELD: username}).first()
        if username
        else None,
        username=username,
    )
