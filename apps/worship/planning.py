"""Planning Steps (Phase 9C): where planning one service stands.

Four steps for people who plan: Theme, the church's team (only while Teams
is on), Song Lineup and Confirm. ``planning_context`` gives the step bar and
the next-step panel, which names the first step not done and one button for
it (Design-Decisions, "Phase 9C"). Team members never get either.
"""

from django.urls import reverse

from apps.church.modules import is_enabled
from apps.teams import rostering

from . import lineups, suggesting
from .models import Lineup, SearchRun

THEME, TEAM, SONGS, CONFIRM = "theme", "team", "songs", "confirm"


def songs_step_label(labels):
    """ "Song Lineup", or the church's Label alone when it already says
    "song" (a "Song List" doesn't become a "Song Song List")."""
    word = labels.get("lineup")
    return word if "song" in word.lower() else f"Song {word}"


def _plural(count, word):
    return f"{count} {word}{'' if count == 1 else 's'}"


def _url(name, service):
    return reverse(name, kwargs={"public_id": service.public_id})


def planning_context(service, user):
    """The step bar (``steps``) and the next-step panel (``next_step``) for
    ``user``, who plans services."""
    labels = service.church.label_set
    lineup = Lineup.objects.filter(service=service).first()
    run = suggesting.latest_run(service)
    teams_on = is_enabled("teams", service.church)
    song_count = lineup.items.count() if lineup is not None else 0
    ranked = (
        run.suggestions.count() if run and run.status == SearchRun.Status.DONE else 0
    )
    service_url = _url("worship:service", service)
    may_open_songs = songs_open(user, lineup)

    steps = [
        {
            "key": THEME,
            "label": "Theme",
            "state": "Posted" if service.posted_theme else "Not posted",
            "done": service.posted_theme is not None,
            "url": _url("worship:theme", service)
            if user.has_perm("worship.change_theme")
            else f"{service_url}#theme",
        }
    ]
    team_skipped = True
    if teams_on:
        serving = service.assignments.filter(reply__in=rostering.SERVING)
        assigned = serving.count()
        accepted = serving.filter(reply="accepted").count()
        roster_open = not rostering.roster_closed(service)
        # Guided, never required: once songs are being chosen, or the roster
        # can't change any more, the team step stops being the next one.
        team_skipped = not roster_open or run is not None or lineup is not None
        team_url = None
        if user.has_perm("teams.add_assignment") and roster_open:
            team_url = _url("teams:assign", service)
        elif user.has_perm("teams.view_assignment"):
            team_url = f"{service_url}#team"
        steps.append(
            {
                "key": TEAM,
                "label": labels.get("team"),
                "state": f"{assigned} assigned, {accepted} accepted"
                if assigned
                else "Nobody yet",
                "done": assigned > 0,
                "url": team_url,
            }
        )
    if lineup is not None:
        songs_state = _plural(song_count, "song")
        if not lineup.is_confirmed:
            songs_state += ", draft"
    elif run is not None and run.is_active:
        songs_state = "Finding songs"
    elif ranked:
        songs_state = f"{_plural(ranked, 'song')} ranked"
    elif run is not None and run.status == SearchRun.Status.FAILED:
        songs_state = "Search didn't finish"
    else:
        songs_state = "Not started"
    steps.append(
        {
            "key": SONGS,
            "label": songs_step_label(labels),
            "state": songs_state,
            "done": song_count > 0,
            "url": _url("worship:lineup", service) if may_open_songs else None,
        }
    )
    confirmed = lineup is not None and lineup.is_confirmed
    if confirmed:
        confirm_state = "Confirmed"
    elif lineup is not None and lineup.is_being_revised:
        confirm_state = "Being revised"
    else:
        confirm_state = "Not yet"
    steps.append(
        {
            "key": CONFIRM,
            "label": "Confirm",
            "state": confirm_state,
            "done": confirmed,
            "url": _url("worship:lineup_confirm", service)
            if lineup is not None and lineups.sees_drafts(user)
            else None,
        }
    )

    current = next(
        (
            step
            for step in steps
            if not step["done"] and not (step["key"] == TEAM and team_skipped)
        ),
        None,
    )
    if current is not None:
        current["current"] = True
    return {
        "steps": steps,
        "next_step": None
        if service.is_cancelled
        else _next_step(service, user, current, lineup, run, ranked, song_count),
    }


def _next_step(service, user, current, lineup, run, ranked, song_count):
    """What the next-step panel says: a title, why, and one button when the
    person may take the step (otherwise whom it waits for)."""
    labels = service.church.label_set
    lineup_word = labels.get("lineup").lower()
    service_word = labels.get("worship_service").lower()
    team_word = labels.get("team")
    lineup_url = _url("worship:lineup", service)
    panel = {"action": None, "action_url": None, "skip_url": None, "waiting": ""}

    if current is None:
        panel.update(
            done=True,
            title=f"{labels.get('lineup')} confirmed",
            text=f"The team can see the {lineup_word} now.",
            action=f"Open the {lineup_word}",
            action_url=lineup_url,
        )
        return panel

    key = current["key"]
    if key == THEME:
        panel.update(
            title="Next: post the theme",
            text="Song suggestions start from the theme: its title, Bible "
            f"passage and a few sentences about the "
            f"{labels.get('sermon').lower()}.",
        )
        if user.has_perm("worship.change_theme"):
            panel.update(action="Post the theme", action_url=current["url"])
        else:
            panel["waiting"] = "Waiting for the theme to be posted."
    elif key == TEAM:
        panel.update(
            title=f"Next: assign the {team_word}",
            text=f"Choose who serves at this {service_word}. Each person is "
            "asked to accept. You can also do this later.",
        )
        if user.has_perm("teams.add_assignment"):
            panel.update(action=f"Assign the {team_word}", action_url=current["url"])
        else:
            panel["waiting"] = f"Waiting for the {team_word} to be assigned."
        if songs_open(user, lineup):
            panel["skip_url"] = lineup_url
    elif key == SONGS:
        panel["title"] = "Next: choose the songs"
        if lineup is not None:
            panel["text"] = f"The {lineup_word} has no songs yet. Add some."
            action = f"Open the {lineup_word}"
        elif run is not None and run.is_active:
            panel.update(
                title="Finding songs",
                text="The search is running; it can take a few minutes.",
            )
            action = "See the progress"
        elif ranked:
            panel["text"] = (
                f"{_plural(ranked, 'song')} are ranked for the theme. Review "
                f"them and save them as the {lineup_word}."
            )
            action = "Review the songs"
        else:
            panel["text"] = (
                "Find songs that fit the theme, review them and save them as "
                f"the {lineup_word}. You'll hear them before you confirm."
            )
            action = "Choose the songs"
        if songs_open(user, lineup):
            panel.update(action=action, action_url=lineup_url)
        else:
            panel["waiting"] = "Waiting for the worship leader to choose the songs."
    else:  # CONFIRM
        panel.update(
            title=f"Next: confirm the {lineup_word}",
            text=f"Check the rundown of {_plural(song_count, 'song')}, then "
            f"confirm. The team sees the {lineup_word} once it is confirmed.",
        )
        if lineups.may_confirm(lineup, user):
            panel.update(action="Review and confirm", action_url=current["url"])
        else:
            panel["waiting"] = "Waiting for it to be confirmed."
    return panel


def songs_open(user, lineup):
    """Whether ``user`` may work on the songs on the Song Lineup page: make
    the lineup from suggestions while there is none, or review it."""
    if lineup is None:
        return user.has_perm("worship.suggest_songs")
    return user.has_perm("worship.view_lineup") and lineups.sees_drafts(user)
