"""When someone leaves the team (Phase 9A, A2; Design-Decisions, "Adviser
comments, 24 Nov").

A change to a person's roles, or deactivating them, can take away
``teams.view_assignment``, the permission that makes them part of the team.
Their assignments on coming services that aren't cancelled, Pending or
Accepted, are then listed on the user form, and the admin chooses to end
them (each becomes an open place for the leader to fill, and its open swap
request is withdrawn) or to keep them. Past assignments are never touched.

Registered with ``apps.accounts.role_changes`` in ``TeamsConfig.ready()``,
so Accounts never imports Teams.
"""

from django.db import transaction
from django.utils import timezone

from apps.accounts.role_changes import Consequence
from apps.church.modules import is_enabled

from . import rostering
from .models import Assignment


def coming_assignments(person):
    """The person's Pending or Accepted assignments on services that haven't
    started and aren't cancelled, soonest first."""
    return (
        Assignment.objects.filter(
            person=person,
            reply__in=rostering.SERVING,
            service__is_cancelled=False,
            service__starts_at__gt=timezone.now(),
        )
        .select_related("service", "part")
        .order_by("service__starts_at", "part__sort_order", "pk")
    )


def describe(assignment):
    service = assignment.service
    when = timezone.localtime(service.starts_at)
    return (
        f"{assignment.part} at {service.name}, {when:%b} {when.day}, {when.year} "
        f"({assignment.get_reply_display()})"
    )


def end_assignments(person, actor):
    """End the person's coming assignments; returns how many ended."""
    with transaction.atomic():
        assignments = list(coming_assignments(person))
        for assignment in assignments:
            rostering.remove(assignment, actor)
    return len(assignments)


def leaving_team(user, lost_permissions):
    """The Consequence for the user form, or None when the person stays on
    the team, Teams is off, or they have no coming assignments."""
    if rostering.TEAM_PERMISSION not in lost_permissions or not is_enabled("teams"):
        return None
    items = [describe(assignment) for assignment in coming_assignments(user)]
    if not items:
        return None
    return Consequence(
        title="Assignments on coming services",
        items=items,
        end=lambda actor: end_assignments(user, actor),
    )
