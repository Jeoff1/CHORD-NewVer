"""Shared page patterns (Phase 9A, A7, part 3; [[Design-System]]).

- ``{% page_header title subtitle=… level=1 %}…actions…{% endpage_header %}``:
  the heading on the left (with an optional subtitle line) and the page's
  actions on the right, wrapping on a phone. The actions are written
  inside the tag, each behind its own permission check: one primary
  button, and the rest in ``{% more_menu %}``.
- ``{% more_menu %}<li>…</li>{% endmore_menu %}``: the outline "More"
  dropdown. Items the user may not use are left out by the template's own
  ``{% if %}``; when no item is left, nothing renders.
- ``{% section_tabs links as tabs %}``: marks the current tab (the longest
  link that starts the page's path) for ``includes/section_tabs.html``.
"""

from django import template
from django.template.base import token_kwargs
from django.template.loader import render_to_string
from django.utils.safestring import mark_safe

register = template.Library()


class PageHeaderNode(template.Node):
    def __init__(self, nodelist, title, kwargs):
        self.nodelist = nodelist
        self.title = title
        self.kwargs = kwargs

    def render(self, context):
        values = {key: value.resolve(context) for key, value in self.kwargs.items()}
        return render_to_string(
            "includes/page_header.html",
            {
                "title": self.title.resolve(context),
                "subtitle": values.get("subtitle", ""),
                "level": values.get("level", 1),
                "actions": mark_safe(self.nodelist.render(context).strip()),
            },
        )


@register.tag
def page_header(parser, token):
    bits = token.split_contents()
    if len(bits) < 2:
        raise template.TemplateSyntaxError("page_header needs a title.")
    title = parser.compile_filter(bits[1])
    kwargs = token_kwargs(bits[2:], parser)
    nodelist = parser.parse(("endpage_header",))
    parser.delete_first_token()
    return PageHeaderNode(nodelist, title, kwargs)


class MoreMenuNode(template.Node):
    def __init__(self, nodelist, kwargs):
        self.nodelist = nodelist
        self.kwargs = kwargs

    def render(self, context):
        items = self.nodelist.render(context).strip()
        if "<li" not in items:
            return ""
        values = {key: value.resolve(context) for key, value in self.kwargs.items()}
        return render_to_string(
            "includes/more_menu.html",
            {"items": mark_safe(items), "label": values.get("label", "More")},
        )


@register.tag
def more_menu(parser, token):
    kwargs = token_kwargs(token.split_contents()[1:], parser)
    nodelist = parser.parse(("endmore_menu",))
    parser.delete_first_token()
    return MoreMenuNode(nodelist, kwargs)


def mark_current(path, links):
    """``links`` as dicts with ``current`` set on the one whose URL is the
    longest start of ``path``."""
    best = max(
        (url for _, url in links if path == url or path.startswith(url)),
        key=len,
        default=None,
    )
    return [
        {"label": label, "url": url, "current": url == best} for label, url in links
    ]


@register.simple_tag(takes_context=True)
def section_tabs(context, links):
    request = context.get("request")
    return mark_current(request.path if request else "", list(links))
