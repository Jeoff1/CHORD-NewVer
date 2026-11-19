from django import template

from ..people import display_name

register = template.Library()


@register.filter
def person_name(user):
    """``{{ user|person_name }}``: the full name, or the username when the
    person has none (``apps/core/people.py``)."""
    return display_name(user)
