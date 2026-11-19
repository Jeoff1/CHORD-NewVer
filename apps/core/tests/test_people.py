from django.template import Context, Template
from django.test import SimpleTestCase

from apps.accounts.models import User
from apps.core.people import display_name


class DisplayNameTests(SimpleTestCase):
    def test_full_name_then_username_then_a_former_user(self):
        self.assertEqual(
            display_name(User(username="ana", first_name="Ana", last_name="Cruz")),
            "Ana Cruz",
        )
        self.assertEqual(display_name(User(username="ana")), "ana")
        self.assertEqual(display_name(None), "a former user")

    def test_the_template_filter(self):
        template = Template("{% load people %}{{ user|person_name }}")
        self.assertEqual(
            template.render(Context({"user": User(username="ben", first_name="Ben")})),
            "Ben",
        )
        self.assertEqual(template.render(Context({"user": None})), "a former user")
