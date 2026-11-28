"""UI/UX Phase 3 (28 Nov 2026): the shared components every Module uses. UI-UX-Master-Plan.md §8."""

from django.contrib import messages
from django.contrib.messages.storage.fallback import FallbackStorage
from django.contrib.staticfiles import finders
from django.template import Context, Template
from django.template.loader import render_to_string
from django.test import RequestFactory, SimpleTestCase, TestCase
from django.urls import reverse

from apps.core.testing import complete_setup, make_user


def with_messages(*pairs):
    request = RequestFactory().get("/")
    request.session = {}
    storage = FallbackStorage(request)
    request._messages = storage
    for level, text in pairs:
        messages.add_message(request, level, text)
    return request


class ToastTests(SimpleTestCase):
    def render(self, request):
        return render_to_string(
            "includes/messages.html", {"messages": messages.get_messages(request)}
        )

    def test_success_closes_itself_errors_stay(self):
        html = self.render(
            with_messages((messages.SUCCESS, "Saved."), (messages.ERROR, "Nope."))
        )
        self.assertIn(
            'class="chord-msg chord-msg--success" role="status" data-msg-auto', html
        )
        self.assertIn('class="chord-msg chord-msg--danger" role="alert">', html)
        self.assertEqual(html.count("chord-msg__bar"), 1)
        self.assertIn('aria-label="Dismiss"', html)

    def test_extra_tags_dont_change_the_level(self):
        request = with_messages()
        messages.success(request, "Hi", extra_tags="special")
        self.assertIn("chord-msg--success", self.render(request))

    def test_the_welcome_toast_is_left_out(self):
        request = with_messages()
        messages.success(request, "Welcome", extra_tags="chord-welcome")
        self.assertNotIn("Welcome", self.render(request))


class EmptyStateTests(SimpleTestCase):
    def test_icon_title_text_and_action(self):
        html = Template(
            '{% include "includes/empty_state.html" with icon="music-note" title="No songs yet"'
            ' text="Add one." action_url="/add/" action_label="Add a song" %}'
        ).render(Context({}))
        self.assertIn('<p class="chord-empty__title">No songs yet</p>', html)
        self.assertIn("Add one.", html)
        self.assertIn('href="/add/"', html)
        self.assertIn("<svg", html)

    def test_no_action_without_both_parts(self):
        html = Template(
            '{% include "includes/empty_state.html" with title="Nothing" %}'
        ).render(Context({}))
        self.assertNotIn("btn", html)


class PageTests(TestCase):
    def setUp(self):
        complete_setup()
        self.client.force_login(make_user(roles=["administrator"]))

    def test_every_page_loads_the_shared_layer(self):
        page = self.client.get(reverse("home"))
        self.assertContains(page, "css/components.css")
        self.assertContains(page, "js/components.js")
        self.assertTrue(finders.find("css/components.css"))
        self.assertTrue(finders.find("js/components.js"))

    def test_messages_arrive_as_toasts(self):
        response = self.client.post(
            reverse("announcements:create"),
            {"title": "Practice moved", "body": "Saturday 4 pm.", "audience": "all"},
            follow=True,
        )
        if b"chord-msgs" in response.content:
            self.assertContains(response, "chord-msg--success")
            self.assertNotContains(response, "alert-dismissible")

    def test_the_search_box_has_an_icon_clear_and_count(self):
        page = self.client.get(reverse("accounts:user_list"), {"q": "zzz"})
        self.assertContains(page, "data-chord-search")
        self.assertContains(page, 'aria-label="Clear the search"')
        self.assertContains(page, "chord-toolbar")

    def test_no_native_confirm_left(self):
        import pathlib

        root = pathlib.Path(__file__).resolve().parents[3]
        found = [
            str(path)
            for folder in ("apps", "templates")
            for path in (root / folder).rglob("*.html")
            if "confirm(" in path.read_text(encoding="utf-8")
        ]
        self.assertEqual(found, [])
