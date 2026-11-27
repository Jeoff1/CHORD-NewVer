from django import template

from ..labels import Labels

register = template.Library()


@register.simple_tag(takes_context=True)
def label(context, key, plural=False):
    """The church's word for ``key``: ``{% label "sermon" %}``.

    ``{% label "member" plural=True %}`` gives the plural, and
    ``{% label "sermon" as word %}`` stores it for filters like ``lower``.
    """
    labels = context.get("labels") or Labels({})
    return labels.get(key, plural=plural)


@register.simple_tag(takes_context=True)
def app_navigation(context):
    """The signed-in sidebar's menu: ``{% app_navigation as nav %}``
    (apps/church/navigation.py)."""
    from ..navigation import build

    request = context["request"]
    return build(request, context.get("settings_menu"))


@register.simple_tag(takes_context=True)
def church_role_line(context):
    """The line under the church's name in the sidebar."""
    from ..navigation import role_line

    request = context["request"]
    return role_line(request.user, request.church)


@register.filter
def initials(name):
    """Up to two capital initials of a name, for a missing logo."""
    words = [word for word in str(name).split() if word[:1].isalnum()]
    return "".join(word[0] for word in words[:2]).upper()


@register.simple_tag(takes_context=True)
def dashboard_overview(context):
    """The dashboard's figures, status bars and shortcuts, each limited to
    what the person may open: ``{% dashboard_overview as overview %}``."""
    from .. import dashboard
    from ..navigation import quick_actions

    request = context["request"]
    found = dashboard.stats(request)
    coming = context.get("coming_up") or []
    breakdowns = dashboard.breakdowns(request)
    for breakdown in breakdowns:
        # (label, count, style, share): the share is a whole percentage, for
        # the bar's description.
        total = breakdown.total
        breakdown.rows = [
            (label, count, style, round(count * 100 / total) if total else 0)
            for label, count, style in breakdown.parts
        ]
    return {
        "primary": [stat for stat in found if stat.primary],
        "secondary": [stat for stat in found if not stat.primary],
        "breakdowns": breakdowns,
        "quick_actions": quick_actions(request),
        "next_up": next((row for row in coming if not row.is_cancelled), None),
    }
