"""The shared page patterns (Phase 9A, A7, part 3): page header, "More"
menu, section tabs and status pills."""

from django.template import Context, Template
from django.test import RequestFactory, SimpleTestCase

from apps.core.templatetags.ui import mark_current


def render(source, **context):
    return Template("{% load ui %}" + source).render(Context(context))


class PageHeaderTests(SimpleTestCase):
    def test_title_subtitle_and_actions(self):
        html = render(
            '{% page_header "Worship services" subtitle="Coming up" %}'
            '<a class="btn btn-primary" href="/x/">Add service</a>{% endpage_header %}'
        )
        self.assertIn('<h1 class="h3 mb-0">Worship services</h1>', html)
        self.assertIn("Coming up", html)
        self.assertIn('class="chord-page-header__actions"', html)
        self.assertIn("Add service", html)

    def test_no_actions_no_action_box(self):
        html = render('{% page_header "Plain" %}{% endpage_header %}')
        self.assertNotIn("chord-page-header__actions", html)

    def test_level_two(self):
        html = render('{% page_header "In settings" level=2 %}{% endpage_header %}')
        self.assertIn("<h2", html)


class MoreMenuTests(SimpleTestCase):
    def test_items_show_in_a_dropdown(self):
        html = render(
            '{% more_menu %}{% if allowed %}<li><a class="dropdown-item" '
            'href="/a/">Import</a></li>{% endif %}{% endmore_menu %}',
            allowed=True,
        )
        self.assertIn("dropdown-toggle", html)
        self.assertIn(">More</button>", html)
        self.assertIn("Import", html)

    def test_an_empty_menu_does_not_show(self):
        html = render(
            "{% more_menu %}{% if allowed %}<li>Import</li>{% endif %}{% endmore_menu %}",
            allowed=False,
        )
        self.assertEqual(html.strip(), "")


class SectionTabTests(SimpleTestCase):
    def test_the_longest_matching_link_is_current(self):
        links = [("Schedule", "/worship/"), ("Calendar", "/worship/calendar/")]
        tabs = mark_current("/worship/calendar/", links)
        self.assertEqual([tab["current"] for tab in tabs], [False, True])
        tabs = mark_current("/worship/", links)
        self.assertEqual([tab["current"] for tab in tabs], [True, False])

    def test_the_include_marks_the_current_tab(self):
        request = RequestFactory().get("/worship/calendar/")
        html = render(
            "{% section_tabs links as tabs %}"
            '{% include "includes/section_tabs.html" with tabs=tabs label="Worship" %}',
            request=request,
            links=[("Schedule", "/worship/"), ("Calendar", "/worship/calendar/")],
        )
        self.assertIn(
            'href="/worship/calendar/" class="active" aria-current="page"', html
        )
        self.assertIn('aria-label="Worship"', html)

    def test_one_tab_shows_no_row(self):
        request = RequestFactory().get("/worship/")
        html = render(
            "{% section_tabs links as tabs %}"
            '{% include "includes/section_tabs.html" with tabs=tabs %}',
            request=request,
            links=[("Schedule", "/worship/")],
        )
        self.assertNotIn("chord-tabs", html)


class StatusPillTests(SimpleTestCase):
    def test_each_status_has_its_colours(self):
        expected = {
            "draft": ("chord-pill--warning", "Draft"),
            "confirmed": ("chord-pill--success", "Confirmed"),
            "none": ("chord-pill--neutral", "None yet"),
            "cancelled": ("chord-pill--danger", "Cancelled"),
            "occasion": ("chord-pill--accent", "Occasion"),
        }
        for status, (css, text) in expected.items():
            with self.subTest(status):
                html = Template(
                    '{% include "includes/status_pill.html" with status=status %}'
                ).render(Context({"status": status}))
                self.assertIn(css, html)
                self.assertIn(text, html)
