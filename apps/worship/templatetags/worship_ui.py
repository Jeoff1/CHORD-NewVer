"""The Worship Module's section tabs (Phase 9A, A7, part 3)."""

from django import template
from django.urls import reverse

register = template.Library()


@register.simple_tag(takes_context=True)
def worship_sections(context):
    """(label, url) for each Worship section the person may open."""
    user = context["request"].user
    links = [
        ("Schedule", reverse("worship:home")),
        ("Calendar", reverse("worship:calendar")),
    ]
    if user.has_perm("songs.view_song"):
        links.append(("Songs", reverse("songs:list")))
    if user.has_perm("worship.view_song_usage") or user.has_perm(
        "worship.record_attendance"
    ):
        links.append(("Reports", reverse("worship:reports")))
    return links
