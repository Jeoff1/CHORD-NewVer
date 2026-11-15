from django.http import Http404, HttpResponse
from django.template import Context, Template
from django.test import RequestFactory, TestCase
from django.utils import timezone
from django.views import View

from apps.church.context_processors import module_entries
from apps.church.labels import Labels
from apps.church.middleware import ChurchProfileMiddleware
from apps.church.models import ChurchProfile
from apps.church.modules import MODULES, ModuleRequiredMixin, is_enabled


class ChurchProfileTests(TestCase):
    def test_load_creates_the_single_profile(self):
        profile = ChurchProfile.load()
        self.assertEqual(profile.pk, ChurchProfile.SINGLETON_PK)
        self.assertEqual(ChurchProfile.load().pk, profile.pk)
        self.assertEqual(ChurchProfile.objects.count(), 1)

    def test_a_second_profile_overwrites_the_first(self):
        ChurchProfile.load()
        ChurchProfile(name="Other").save()
        self.assertEqual(ChurchProfile.objects.count(), 1)
        self.assertEqual(ChurchProfile.load().name, "Other")

    def test_defaults_are_neutral(self):
        profile = ChurchProfile.load()
        self.assertEqual(profile.disabled_modules, [])
        self.assertEqual(profile.labels, {})
        self.assertFalse(profile.setup_completed)


class LabelsTests(TestCase):
    def test_defaults_and_church_wording(self):
        labels = Labels({"officiant": {"singular": "Pastor", "plural": "Pastors"}})
        self.assertEqual(labels.get("officiant"), "Pastor")
        self.assertEqual(labels.get("officiant", plural=True), "Pastors")
        self.assertEqual(labels.get("member"), "Member")
        self.assertEqual(labels["member"], "Member")

    def test_blank_wording_falls_back_to_default(self):
        labels = Labels({"member": {"singular": "  ", "plural": ""}})
        self.assertEqual(labels.get("member", plural=True), "Members")

    def test_template_tag(self):
        profile = ChurchProfile.load()
        profile.labels = {"officiant": {"singular": "Priest", "plural": "Priests"}}
        profile.save()
        template = Template(
            "{% load church %}{% label 'officiant' %}|"
            "{% label 'officiant' plural=True %}|"
            "{% label 'officiant' as word %}{{ word|lower }}"
        )
        self.assertEqual(template.render(Context()), "Priest|Priests|priest")


class SampleModuleView(ModuleRequiredMixin, View):
    module = "giving"

    def get(self, request):
        return HttpResponse("giving page")


class ModuleSwitchingTests(TestCase):
    def setUp(self):
        self.profile = ChurchProfile.load()
        self.request = RequestFactory().get("/giving/")
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
        self.profile.disabled_modules = ["giving"]
        self.profile.save()
        with self.assertRaises(Http404):
            SampleModuleView.as_view()(self.request)

    def test_switched_off_module_leaves_navigation(self):
        self.profile.disabled_modules = ["giving", "records"]
        codes = [entry.code for entry in module_entries(self.profile)]
        self.assertNotIn("giving", codes)
        self.assertNotIn("records", codes)
        self.assertIn("members", codes)

    def test_module_names_follow_labels(self):
        self.profile.labels = {"ministry": {"singular": "Group", "plural": "Groups"}}
        names = {e.code: e.name for e in module_entries(self.profile)}
        self.assertEqual(names["ministries"], "Groups")
        self.assertEqual(names["giving"], "Giving")


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

        ChurchProfileMiddleware(view)(RequestFactory().get("/"))
        self.assertEqual(seen["tz"], "America/New_York")
        self.assertEqual(seen["church"].pk, profile.pk)
