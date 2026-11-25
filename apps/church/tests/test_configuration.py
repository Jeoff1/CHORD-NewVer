from django.contrib.auth.models import AnonymousUser
from django.http import Http404, HttpResponse
from django.template import Context, Template
from django.test import RequestFactory, TestCase
from django.utils import timezone
from django.views import View

from apps.church.context_processors import module_entries
from apps.church.labels import Labels
from apps.church.middleware import CurrentChurchMiddleware
from apps.church.models import ChurchProfile
from apps.church.modules import MODULES, ModuleRequiredMixin, is_enabled


class ChurchProfileTests(TestCase):
    def test_an_installation_starts_with_one_church(self):
        self.assertEqual(ChurchProfile.objects.count(), 1)
        first = ChurchProfile.objects.get()
        self.assertEqual(ChurchProfile.load().pk, first.pk)
        self.assertTrue(first.members_teams_unlocked)

    def test_a_second_church_is_its_own_record(self):
        first = ChurchProfile.load()
        other = ChurchProfile.objects.create(name="Grace Chapel")
        self.assertEqual(ChurchProfile.objects.count(), 2)
        self.assertEqual(ChurchProfile.load().pk, first.pk)
        self.assertEqual(other.slug, "grace-chapel")
        self.assertFalse(other.members_teams_unlocked)

    def test_slugs_stay_unique(self):
        ChurchProfile.objects.create(name="Grace Chapel")
        again = ChurchProfile.objects.create(name="Grace Chapel")
        self.assertEqual(again.slug, "grace-chapel-2")

    def test_defaults_are_neutral(self):
        profile = ChurchProfile.load()
        self.assertEqual(profile.disabled_modules, [])
        self.assertEqual(profile.labels, {})
        self.assertFalse(profile.setup_completed)


class LabelsTests(TestCase):
    def test_defaults_and_church_wording(self):
        labels = Labels({"sermon": {"singular": "Homily", "plural": "Homilies"}})
        self.assertEqual(labels.get("sermon"), "Homily")
        self.assertEqual(labels.get("sermon", plural=True), "Homilies")
        self.assertEqual(labels.get("member"), "Member")
        self.assertEqual(labels["member"], "Member")

    def test_blank_wording_falls_back_to_default(self):
        labels = Labels({"member": {"singular": "  ", "plural": ""}})
        self.assertEqual(labels.get("member", plural=True), "Members")

    def test_template_tag(self):
        profile = ChurchProfile.load()
        profile.labels = {"sermon": {"singular": "Message", "plural": "Messages"}}
        profile.save()
        template = Template(
            "{% load church %}{% label 'sermon' %}|"
            "{% label 'sermon' plural=True %}|"
            "{% label 'sermon' as word %}{{ word|lower }}"
        )
        self.assertEqual(template.render(Context()), "Message|Messages|message")


class SampleModuleView(ModuleRequiredMixin, View):
    module = "announcements"

    def get(self, request):
        return HttpResponse("announcements page")


class ModuleSwitchingTests(TestCase):
    def setUp(self):
        self.profile = ChurchProfile.load()
        self.request = RequestFactory().get("/announcements/")
        self.request.church = self.profile

    def test_every_module_starts_switched_on(self):
        self.assertTrue(all(is_enabled(m.code) for m in MODULES))

    def test_unknown_module_is_an_error(self):
        with self.assertRaises(ValueError):
            is_enabled("unknown_module")

    def test_switched_on_module_page_opens(self):
        response = SampleModuleView.as_view()(self.request)
        self.assertEqual(response.status_code, 200)

    def test_switched_off_module_page_is_404(self):
        self.profile.disabled_modules = ["announcements"]
        self.profile.save()
        with self.assertRaises(Http404):
            SampleModuleView.as_view()(self.request)

    def test_switched_off_module_leaves_navigation(self):
        self.profile.disabled_modules = ["announcements", "teams"]
        codes = [entry.code for entry in module_entries(self.profile)]
        self.assertNotIn("announcements", codes)
        self.assertNotIn("teams", codes)
        self.assertIn("members", codes)

    def test_module_counts_as_off_while_one_it_needs_is_off(self):
        self.profile.disabled_modules = ["worship"]
        self.assertFalse(is_enabled("teams", self.profile))
        self.assertTrue(is_enabled("announcements", self.profile))
        codes = [entry.code for entry in module_entries(self.profile)]
        self.assertEqual(codes, ["members", "announcements"])

    def test_module_names_follow_labels(self):
        self.profile.labels = {
            "member": {"singular": "Parishioner", "plural": "Parishioners"}
        }
        entries = {e.code: e for e in module_entries(self.profile)}
        self.assertEqual(entries["members"].name, "Parishioners")
        self.assertEqual(entries["worship"].name, "Worship")
        self.assertEqual(entries["teams"].requires, ("Worship",))


class TimeZoneMiddlewareTests(TestCase):
    def test_uses_the_church_time_zone(self):
        profile = ChurchProfile.load()
        profile.time_zone = "America/New_York"
        profile.save()
        seen = {}

        def view(request):
            seen["tz"] = timezone.get_current_timezone_name()
            seen["church"] = request.church
            return HttpResponse()

        request = RequestFactory().get("/")
        request.user = AnonymousUser()
        request.session = {}
        CurrentChurchMiddleware(view)(request)
        self.assertEqual(seen["tz"], "America/New_York")
        self.assertEqual(seen["church"].pk, profile.pk)
