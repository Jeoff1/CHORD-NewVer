"""The sidebar of the signed-in pages (dashboard redesign, 27 Nov 2026).

The menu lists only what the person may open: a link shows when its Module
is switched on (``is_enabled``) and the person holds the permission its
page needs; a group or category with nothing left in it disappears. Labels
come from the church (decision 0001).

On screen the Occasions Module is called "Services" under Management, with
"Bookings" beside it (the lead developer's naming, 27 Nov 2026); its code,
routes and data keep the name Occasions. Detailed configuration stays in
the Settings hub.
"""

from dataclasses import dataclass, field

from django.urls import reverse

from .modules import is_enabled

# The Occasions Module's permissions (apps/occasions/rules.py), named here
# because Church Setup never imports a Module.
VIEW_BOOKINGS = "occasions.view_occasion"
REQUEST_SERVICE = "occasions.request_occasion"
APPROVE_REQUESTS = "occasions.approve_occasion"

# The sidebar's remembered state, written by sidebar.js and read here so the
# page arrives drawn the way the person left it (no jump on load):
# "icons" or "full", and which categories and groups are open, as
# "planning:1.songs:0.management-services:0".
MODE_COOKIE = "chord_sidebar"
OPEN_COOKIE = "chord_sidebar_open"


def saved_open(request):
    """{key: is open} from the sidebar's cookie; anything malformed is
    ignored."""
    found = {}
    for part in request.COOKIES.get(OPEN_COOKIE, "").split("."):
        key, _, value = part.partition(":")
        if key and value in ("0", "1") and len(key) <= 60:
            found[key] = value == "1"
    return found


@dataclass
class NavLink:
    label: str
    url: str
    icon: str = ""
    # View names (``namespace:name``) where this link is the current page,
    # and prefixes of them, for pages that belong to it (a service's own page
    # belongs to the schedule). An exact match beats a prefix; a longer
    # prefix beats a shorter one.
    exact: tuple = ()
    prefixes: tuple = ()
    active: bool = False
    # The page's URL name, so the template can add a count (the Service
    # Requests link shows the waiting ones, from Occasions' context).
    key: str = ""

    def score(self, view_name):
        if view_name in self.exact:
            return 1000
        return max(
            (len(prefix) for prefix in self.prefixes if view_name.startswith(prefix)),
            default=0,
        )


@dataclass
class NavGroup:
    key: str
    label: str
    links: list = field(default_factory=list)
    # As the person left it; None until they open or close it.
    saved: bool | None = None

    @property
    def active(self):
        return any(link.active for link in self.links)

    @property
    def open(self):
        """Open when it holds the current page, else as the person left it;
        a group starts open."""
        return self.active or (True if self.saved is None else self.saved)


@dataclass
class NavCategory:
    key: str
    label: str
    icon: str
    links: list = field(default_factory=list)
    groups: list = field(default_factory=list)
    saved: bool | None = None

    @property
    def open(self):
        """Open when it holds the current page, else as the person left it;
        a category starts closed."""
        return self.active or bool(self.saved)

    @property
    def all_links(self):
        return self.links + [link for group in self.groups for link in group.links]

    @property
    def active(self):
        return any(link.active for link in self.all_links)


def _link(user, permission, label, url_name, **kwargs):
    """A NavLink when the person holds ``permission`` (any one of a tuple),
    else None."""
    permissions = permission if isinstance(permission, tuple) else (permission,)
    if not any(user.has_perm(p) for p in permissions):
        return None
    return NavLink(label=label, url=reverse(url_name), key=url_name, **kwargs)


def _kept(*links):
    return [link for link in links if link is not None]


def build(request, settings_menu=None):
    """The sidebar for ``request``: top links, categories, the Settings link,
    and the current page's label for the header."""
    user = request.user
    church = request.church
    labels = church.label_set
    on = {
        code: is_enabled(code, church)
        for code in ("members", "worship", "teams", "occasions", "announcements")
    }
    settings_url = getattr(settings_menu, "home_url", None) if settings_menu else None
    if isinstance(settings_menu, dict):
        settings_url = settings_menu.get("home_url")

    dashboard = NavLink("Dashboard", reverse("home"), icon="home", exact=("home",))

    management = NavCategory("management", "Management", "inbox")
    if on["occasions"]:
        services = NavGroup(
            "services",
            "Services",
            _kept(
                _link(
                    user,
                    APPROVE_REQUESTS,
                    "Service Requests",
                    "occasions:requests",
                    exact=("occasions:requests", "occasions:decide"),
                ),
                _link(
                    user,
                    REQUEST_SERVICE,
                    "Request a Service",
                    "occasions:request",
                    exact=("occasions:request",),
                ),
                _link(
                    user,
                    REQUEST_SERVICE,
                    "My Requests",
                    "occasions:my_requests",
                    exact=("occasions:my_requests", "occasions:withdraw"),
                ),
            ),
        )
        bookings = NavGroup(
            "bookings",
            "Bookings",
            _kept(
                _link(
                    user,
                    VIEW_BOOKINGS,
                    "All Bookings",
                    "occasions:list",
                    exact=(
                        "occasions:home",
                        "occasions:list",
                        "occasions:detail",
                        "occasions:update",
                    ),
                ),
                _link(
                    user,
                    "occasions.add_occasion",
                    "Book a Service",
                    "occasions:create",
                    exact=("occasions:create",),
                ),
            ),
        )
        management.groups = [group for group in (services, bookings) if group.links]

    planning = NavCategory("planning", "Planning", "calendar")
    songs = NavCategory("songs", "Songs", "music-note")
    if on["worship"]:
        planning.links = _kept(
            _link(
                user,
                "worship.view_worshipservice",
                labels.get("worship_service", plural=True),
                "worship:home",
                prefixes=("worship:",),
            ),
            _link(
                user,
                "worship.view_worshipservice",
                "Calendar",
                "worship:calendar",
                exact=("worship:calendar",),
            ),
            _link(
                user,
                "teams.view_assignment",
                "My Schedule",
                "teams:my_schedule",
                prefixes=("teams:my_", "teams:blackout", "teams:reply", "teams:swap"),
            )
            if on["teams"]
            else None,
            _link(
                user,
                "teams.view_teamprofile",
                "Team Roster",
                "teams:roster",
                exact=("teams:roster", "teams:person_parts"),
            )
            if on["teams"]
            else None,
            _link(
                user,
                ("worship.view_song_usage", "worship.record_attendance"),
                "Reports",
                "worship:reports",
                prefixes=("worship:report",),
            ),
        )
        songs.links = _kept(
            _link(
                user, "songs.view_song", "Song Pool", "songs:list", prefixes=("songs:",)
            ),
            _link(
                user,
                "songs.add_song",
                "Find Songs",
                "songs:spotify_search",
                exact=("songs:spotify_search", "songs:spotify_add"),
            ),
        )

    members = NavCategory("members", labels.get("member", plural=True), "people")
    members.links = _kept(
        _link(
            user,
            "members.view_member",
            f"{labels.get('member')} Directory",
            "members:list",
            prefixes=("members:",),
        )
        if on["members"]
        else None,
        _link(
            user,
            "members.view_household",
            "Households",
            "members:household_list",
            prefixes=("members:household",),
        )
        if on["members"]
        else None,
        # Accounts and roles are core, so they stay when Members is off.
        _link(
            user,
            "accounts.view_user",
            "User Accounts",
            "accounts:user_list",
            prefixes=("accounts:user",),
        ),
        _link(
            user,
            "accounts.view_role",
            "Roles & Permissions",
            "accounts:role_list",
            prefixes=("accounts:role", "accounts:permission_matrix"),
        ),
    )

    announcements = (
        NavLink(
            "Announcements",
            reverse("announcements:list"),
            icon="megaphone",
            prefixes=("announcements:",),
        )
        if on["announcements"]
        else None
    )
    settings = NavLink("Settings", settings_url, icon="gear") if settings_url else None

    categories = [
        category
        for category in (management, planning, songs, members)
        if category.all_links
    ]
    every_link = [dashboard, *[link for c in categories for link in c.all_links]]
    every_link += _kept(announcements)

    current = None
    in_settings = bool(
        settings_menu.get("current")
        if isinstance(settings_menu, dict)
        else getattr(settings_menu, "current", None)
    )
    if in_settings and settings is not None:
        settings.active = True
        current = settings
    else:
        match = request.resolver_match
        view_name = match.view_name if match else ""
        scored = [(link.score(view_name), link) for link in every_link]
        best = max(scored, key=lambda pair: pair[0], default=(0, None))
        if best[0] > 0:
            best[1].active = True
            current = best[1]

    remembered = saved_open(request)
    for category in categories:
        category.saved = remembered.get(category.key)
        for group in category.groups:
            group.saved = remembered.get(f"{category.key}-{group.key}")

    section = ""
    for category in categories:
        if category.active:
            section = category.label
    return {
        "dashboard": dashboard,
        "categories": categories,
        "announcements": announcements,
        "settings": settings,
        "current": current,
        "section": section,
    }


def quick_actions(request):
    """The dashboard's shortcuts: only actions that create a record and
    have no place in the sidebar (UI/UX owner, 27 Nov 2026: the sidebar
    navigates, the dashboard acts), each for people who may take it."""
    user = request.user
    church = request.church
    labels = church.label_set
    service = labels.get("worship_service").lower()
    member = labels.get("member").lower()
    actions = []

    def add(allowed, label, url_name, icon):
        if allowed:
            actions.append((label, reverse(url_name), icon))

    add(
        is_enabled("worship", church) and user.has_perm("worship.add_worshipservice"),
        f"Create {service}",
        "worship:service_create",
        "plus",
    )
    add(
        is_enabled("announcements", church)
        and user.has_perm("announcements.add_announcement"),
        "New announcement",
        "announcements:create",
        "megaphone",
    )
    add(
        is_enabled("members", church) and user.has_perm("members.add_member"),
        f"Add {member}",
        "members:create",
        "person-plus",
    )
    return actions


def role_line(user, church):
    """The line under the church's name: "Church Administration" for its
    administrators, else the person's roles there, else nothing."""
    from apps.accounts.roles import ADMINISTRATOR

    roles = list(user.roles_in(church).order_by("title"))
    if any(role.key == ADMINISTRATOR for role in roles):
        return "Church Administration"
    return ", ".join(role.title for role in roles)
