"""The Members Module's section tabs (Phase 9A, A7, part 3)."""

from django import template
from django.urls import reverse

register = template.Library()


@register.simple_tag(takes_context=True)
def members_sections(context):
    """(label, url) for each Members section the person may open."""
    request = context["request"]
    links = [("People", reverse("members:list"))]
    if request.user.has_perm("members.view_household"):
        links.append(("Households", reverse("members:household_list")))
    return links
