"""The sign-in page redesign (27 Nov 2026; Design-System.md, "The sign-in
and sign-up pages"): the sign-up page's split screen, with Django's LoginView,
AuthenticationForm, CSRF protection and redirects unchanged."""

from django.contrib.auth import SESSION_KEY
from django.test import Client, TestCase
from django.urls import reverse

from apps.core.testing import TEST_PASSWORD, make_user

LOGIN = reverse("accounts:login")


class SignInPageTests(TestCase):
    def test_it_shares_the_sign_up_layout(self):
        response = self.client.get(LOGIN)
        self.assertTemplateUsed(response, "accounts/login.html")
        self.assertTemplateUsed(response, "accounts/auth_base.html")
        self.assertTemplateNotUsed(response, "base.html")
        for path in (
            "css/auth.css",
            "accounts/auth.js",
            "images/landing/signup-worship.webp",
            "images/landing/chord-logo-gold.webp",
        ):
            self.assertContains(response, path)
        self.assertContains(response, "Bringing Worship Together")
        self.assertContains(response, 'aria-label="CHORD, home"')

    def test_the_form_and_its_words(self):
        response = self.client.get(LOGIN)
        self.assertContains(response, "<h1", count=1)
        self.assertContains(response, ">Welcome Back</h1>")
        self.assertContains(response, "Sign in to continue to CHORD")
        for name in ("username", "password", "csrfmiddlewaretoken", "next"):
            with self.subTest(field=name):
                self.assertContains(response, f'name="{name}"', count=1)
        self.assertContains(response, 'method="post"')
        self.assertContains(response, "<span data-au-label>Sign In</span></button>")
        self.assertContains(response, 'data-au-busy="Signing in…"')
        self.assertContains(response, 'class="au-spinner" aria-hidden="true" hidden')

    def test_password_managers_still_fill_it(self):
        response = self.client.get(LOGIN)
        self.assertContains(response, 'autocomplete="username"')
        self.assertContains(response, 'autocomplete="current-password"')
        self.assertContains(response, 'type="password"')
        self.assertContains(
            response, 'data-au-reveal="id_password"', count=1
        )  # one show button
        self.assertContains(
            response,
            'aria-pressed="false" hidden><span data-au-reveal-word>Show</span>'
            '<span class="visually-hidden"> password</span></button>',
        )

    def test_links(self):
        response = self.client.get(LOGIN)
        home, register = reverse("home"), reverse("churches:register")
        self.assertNotContains(response, "au-tab")  # no Sign Up / Sign In toggle
        # Sign up leads to registering a church, which also offers a personal account.
        self.assertContains(
            response, f'Don’t have an account? <a href="{register}">Sign up</a>'
        )
        self.assertNotContains(response, "sign in your church")
        # Forgot your password? sits right under the password field.
        content = response.content.decode()
        forgot = f'<a href="{reverse("accounts:password_reset")}">Forgot your password?'
        self.assertIn(forgot, content)
        self.assertLess(content.index('name="password"'), content.index(forgot))
        self.assertLess(content.index(forgot), content.index("data-au-busy"))
        self.assertContains(response, f'href="{home}"', count=3)  # logo, two Back links
        self.assertContains(response, "Back to Home", count=1)

    def test_no_sign_in_with_other_services(self):
        content = self.client.get(LOGIN).content.decode().lower()
        for word in ("google", "facebook", "apple"):
            self.assertNotIn(word, content)

    def test_the_forgot_password_page_still_works(self):
        response = self.client.get(reverse("accounts:password_reset"))
        self.assertEqual(response.status_code, 200)


class SignInBehaviourTests(TestCase):
    """The same sign-in as before: only the page around it changed."""

    def setUp(self):
        self.user = make_user(username="ruth.ann")

    def test_wrong_credentials_show_djangos_message_in_the_error_box(self):
        response = self.client.post(
            LOGIN, {"username": "ruth.ann", "password": "not-the-password"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '<div class="au-alert" role="alert">')
        self.assertContains(response, "Please enter a correct username and password.")
        self.assertTemplateUsed(response, "includes/icons/alert-circle.html")
        # The username stays; the password never comes back.
        self.assertContains(response, 'value="ruth.ann"')
        self.assertNotContains(response, "not-the-password")
        self.assertNotIn(SESSION_KEY, self.client.session)

    def test_empty_fields_show_errors_under_them(self):
        response = self.client.post(LOGIN, {"username": "", "password": ""})
        self.assertContains(response, 'id="id_username_error"')
        self.assertContains(response, 'id="id_password_error"')
        self.assertNotIn(SESSION_KEY, self.client.session)

    def test_an_inactive_account_cannot_sign_in(self):
        self.user.is_active = False
        self.user.save()
        response = self.client.post(
            LOGIN, {"username": "ruth.ann", "password": TEST_PASSWORD}
        )
        self.assertContains(response, 'class="au-alert"')
        self.assertNotIn(SESSION_KEY, self.client.session)

    def test_good_credentials_go_home(self):
        response = self.client.post(
            LOGIN, {"username": "ruth.ann", "password": TEST_PASSWORD}
        )
        self.assertRedirects(response, reverse("home"), fetch_redirect_response=False)
        self.assertEqual(int(self.client.session[SESSION_KEY]), self.user.pk)

    def test_next_is_kept_and_followed(self):
        profile = reverse("accounts:profile")
        page = self.client.get(f"{LOGIN}?next={profile}")
        self.assertContains(page, f'name="next" value="{profile}"')
        response = self.client.post(
            LOGIN,
            {"username": "ruth.ann", "password": TEST_PASSWORD, "next": profile},
        )
        self.assertRedirects(response, profile, fetch_redirect_response=False)

    def test_next_to_another_site_is_ignored(self):
        response = self.client.post(
            LOGIN,
            {
                "username": "ruth.ann",
                "password": TEST_PASSWORD,
                "next": "https://example.com/",
            },
        )
        self.assertRedirects(response, reverse("home"), fetch_redirect_response=False)

    def test_the_form_needs_its_csrf_token(self):
        client = Client(enforce_csrf_checks=True)
        response = client.post(
            LOGIN, {"username": "ruth.ann", "password": TEST_PASSWORD}
        )
        self.assertEqual(response.status_code, 403)
        self.assertNotIn(SESSION_KEY, client.session)
