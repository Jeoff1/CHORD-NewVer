"""How people are named in the app's text."""

FORMER_USER = "a former user"


def display_name(user):
    """A person's full name, or their username when they have none; "a
    former user" when the account is gone. Used wherever text names who did
    something ("Confirmed by …", "Edited by Pastor (…)", "Reviewed by …").
    In templates: ``{{ user|person_name }}`` (``{% load people %}``)."""
    if user is None:
        return FORMER_USER
    return user.get_full_name().strip() or user.get_username()
