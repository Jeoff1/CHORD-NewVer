from django import template

from ..models import ChurchProfile

register = template.Library()


@register.simple_tag(takes_context=True)
def label(context, key, plural=False):
    """The church's word for ``key``: ``{% label "officiant" %}``.

    ``{% label "member" plural=True %}`` gives the plural, and
    ``{% label "officiant" as word %}`` stores it for filters like ``lower``.
    """
    labels = context.get("labels") or ChurchProfile.load().label_set
    return labels.get(key, plural=plural)
