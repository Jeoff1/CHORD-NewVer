"""The Settings hub's menu (Phase 9A, A7, part 3).

Every settings page is registered here once, by the app that owns it, in
its ``AppConfig.ready()``, so core never imports a Module. The menu a
person sees holds only the pages of switched-on Modules that they hold the
permission for, grouped into categories in a fixed order; a category with
no page left is hidden.

``base.html`` shows the hub (the side menu, the "Settings" heading and the
"Category · Group" line) on any page whose path starts with a registered
page's URL: the page itself, and its add and edit pages.
"""

from dataclasses import dataclass, field
from functools import cached_property

from django.urls import reverse

CATEGORIES = (
    ("general", "General"),
    ("people", "People and access"),
    ("members", "Members"),
    ("worship", "Worship"),
    ("teams_occasions", "Teams and occasions"),
    ("integrations", "Integrations"),
)
CATEGORY_TITLES = dict(CATEGORIES)
CATEGORY_ORDER = {key: index for index, (key, _) in enumerate(CATEGORIES)}


@dataclass(frozen=True)
class SettingsPage:
    """One settings page. ``label`` may be a function of the request (for a
    Label such as "Sermon series"); ``permission`` is one permission or a
    tuple of which any one will do; ``module`` is the Module it belongs to,
    or None for core settings."""

    category: str
    label: object
    url_name: str
    permission: object
    module: str | None = None
    group: str = ""
    order: int = 0
    url_kwargs: tuple = ()


_pages = []


def register(*pages):
    for page in pages:
        if page.category not in CATEGORY_TITLES:
            raise ValueError(f"Unknown settings category: {page.category}")
        if page not in _pages:
            _pages.append(page)


def _allowed(user, permission):
    if permission is None:
        return True
    if isinstance(permission, tuple):
        return any(user.has_perm(p) for p in permission)
    return user.has_perm(permission)


@dataclass
class MenuPage:
    label: str
    url: str
    category: str
    group: str
    current: bool = False

    @property
    def category_title(self):
        return CATEGORY_TITLES[self.category]


@dataclass
class MenuCategory:
    key: str
    title: str
    pages: list = field(default_factory=list)

    @property
    def is_open(self):
        return any(page.current for page in self.pages)


class SettingsMenu:
    """The menu for one request. Everything is worked out on first use."""

    def __init__(self, request):
        self.request = request

    @cached_property
    def pages(self):
        user = getattr(self.request, "user", None)
        if not (user and user.is_authenticated):
            return []
        from apps.church.modules import is_enabled

        profile = getattr(self.request, "church", None)
        visible = []
        for page in sorted(_pages, key=lambda p: (CATEGORY_ORDER[p.category], p.order)):
            if page.module and not is_enabled(page.module, profile):
                continue
            if not _allowed(user, page.permission):
                continue
            label = page.label(self.request) if callable(page.label) else page.label
            url = reverse(page.url_name, kwargs=dict(page.url_kwargs))
            visible.append(MenuPage(label, url, page.category, page.group))
        path = self.request.path
        best = max(
            (p for p in visible if path.startswith(p.url)),
            key=lambda p: len(p.url),
            default=None,
        )
        if best is not None:
            best.current = True
        return visible

    @cached_property
    def current(self):
        """The page being shown, when it is a settings page."""
        return next((page for page in self.pages if page.current), None)

    @cached_property
    def categories(self):
        found = {}
        for page in self.pages:
            found.setdefault(
                page.category,
                MenuCategory(page.category, CATEGORY_TITLES[page.category]),
            ).pages.append(page)
        return list(found.values())

    @cached_property
    def home_url(self):
        """The first settings page the person may open, or None."""
        return self.pages[0].url if self.pages else None

    @cached_property
    def category_urls(self):
        """Each category's first page the person may open, by category key:
        the "<Module> settings" links in each Module's "More" menu."""
        urls = {}
        for page in self.pages:
            urls.setdefault(page.category, page.url)
        return urls


def settings_menu(request):
    """Template context: ``settings_menu`` (worked out only when used)."""
    return {"settings_menu": SettingsMenu(request)}
