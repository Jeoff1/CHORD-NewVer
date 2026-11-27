"""The church banner (owner, 27 Nov 2026; Design-System.md, "Registering a
church"): an optional cover image given while registering or in the Public
homepage settings, checked, saved as a WebP copy at most 1920 px wide, shown
on the church's public page, never on directory cards."""

import os
import shutil
import tempfile
from io import BytesIO

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

from apps.church.forms import ChurchHomepageForm, ChurchRegistrationForm
from apps.church.images import BANNER_MAX_WIDTH, optimize_banner
from apps.church.models import ChurchProfile
from apps.core.testing import complete_setup, first_church, make_administrator

REGISTER = reverse("churches:register")
ACCOUNT = {
    "first_name": "Ruth",
    "last_name": "Ann",
    "email": "ruth@example.com",
    "password1": "a-Long-pass-8472",
    "password2": "a-Long-pass-8472",
}


def picture(
    name="cover.jpg", size=(1920, 640), fmt="JPEG", mode="RGB", exif=None, color="white"
):
    buffer = BytesIO()
    image = Image.new(mode, size, color)
    kwargs = {"exif": exif} if exif is not None else {}
    image.save(buffer, fmt, **kwargs)
    types = {
        "JPEG": "image/jpeg",
        "PNG": "image/png",
        "WEBP": "image/webp",
        "GIF": "image/gif",
    }
    return SimpleUploadedFile(name, buffer.getvalue(), content_type=types[fmt])


class MediaMixin:
    def setUp(self):
        super().setUp()
        self.media = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.media, ignore_errors=True)
        override = override_settings(MEDIA_ROOT=self.media)
        override.enable()
        self.addCleanup(override.disable)


class OptimizeTests(TestCase):
    def test_a_large_banner_is_made_1920_wide_keeping_its_shape(self):
        copy = optimize_banner(picture(size=(3000, 1000)))
        with Image.open(copy) as image:
            self.assertEqual(image.format, "WEBP")
            self.assertEqual(image.size, (BANNER_MAX_WIDTH, 640))
        self.assertEqual(copy.name, "banner.webp")

    def test_a_small_banner_is_never_enlarged_or_cropped(self):
        with Image.open(optimize_banner(picture(size=(900, 500)))) as image:
            self.assertEqual(image.size, (900, 500))

    def test_hidden_details_are_left_out_and_the_photo_turned_upright(self):
        exif = Image.Exif()
        exif[0x0112] = 6  # Orientation: rotate 90 degrees to show it upright
        exif[0x010F] = "Example camera"
        copy = optimize_banner(picture(size=(1200, 400), exif=exif))
        with Image.open(copy) as image:
            self.assertEqual(image.size, (400, 1200))
            self.assertFalse(image.getexif())

    def test_a_transparent_png_keeps_its_transparency(self):
        upload = picture(
            "cover.png",
            size=(600, 200),
            fmt="PNG",
            mode="RGBA",
            color=(255, 255, 255, 0),
        )
        with Image.open(optimize_banner(upload)) as image:
            self.assertEqual(image.mode, "RGBA")


class FormCheckTests(TestCase):
    def check(self, upload):
        form = ChurchRegistrationForm(
            {"church-name": "Grace"}, {"church-banner": upload}, prefix="church"
        )
        form.is_valid()
        return form.errors.get("banner", [])

    def test_jpg_png_and_webp_are_accepted(self):
        for name, fmt in (("a.jpg", "JPEG"), ("a.png", "PNG"), ("a.webp", "WEBP")):
            with self.subTest(fmt=fmt):
                self.assertEqual(self.check(picture(name, fmt=fmt)), [])

    def test_other_files_are_refused(self):
        gif = picture("a.gif", fmt="GIF")
        pdf = SimpleUploadedFile("a.pdf", b"%PDF-1.4", content_type="application/pdf")
        disguised = picture("a.jpg", fmt="GIF")
        for upload in (gif, pdf, disguised):
            with self.subTest(name=upload.name):
                self.assertTrue(self.check(upload))

    def test_more_than_5_mb_is_refused(self):
        noise = Image.frombytes("RGB", (1500, 1250), os.urandom(1500 * 1250 * 3))
        buffer = BytesIO()
        noise.save(buffer, "PNG", compress_level=0)
        self.assertGreater(len(buffer.getvalue()), 5 * 1024 * 1024)
        upload = SimpleUploadedFile(
            "big.png", buffer.getvalue(), content_type="image/png"
        )
        self.assertEqual(self.check(upload), ["The banner must be 5 MB or smaller."])


class RegisterWithBannerTests(MediaMixin, TestCase):
    def setUp(self):
        super().setUp()
        complete_setup()

    def test_the_step_shows_the_banner_field_and_both_sizes(self):
        response = self.client.get(REGISTER)
        content = response.content.decode()
        self.assertContains(response, 'name="church-banner"', count=1)
        self.assertContains(response, 'accept="image/jpeg,image/png,image/webp"')
        self.assertContains(
            response, "1920 × 640 px recommended (3:1). JPG, PNG or WebP, 5 MB at most."
        )
        self.assertContains(
            response,
            "512 × 512 px recommended (1:1). PNG, JPEG, GIF or WebP, 2 MB at most.",
        )
        self.assertContains(response, "Drag an image here")
        self.assertContains(response, "data-au-banner-drop")
        self.assertContains(response, "data-au-pv-banner")
        # Between the logo and the description.
        self.assertLess(
            content.index('name="church-logo"'), content.index('name="church-banner"')
        )
        self.assertLess(
            content.index('name="church-banner"'), content.index('name="church-about"')
        )

    def test_registering_saves_an_optimised_banner(self):
        response = self.client.post(
            REGISTER,
            {
                **ACCOUNT,
                "church-name": "Grace Chapel",
                "church-banner": picture(size=(2400, 800)),
            },
        )
        self.assertEqual(response.status_code, 302)
        church = ChurchProfile.objects.get(name="Grace Chapel")
        self.assertRegex(church.banner.name, r"^church/banner/[0-9a-f]{32}\.webp$")
        with Image.open(church.banner.path) as image:
            self.assertEqual(image.size, (1920, 640))

    def test_no_banner_is_fine(self):
        self.client.post(REGISTER, {**ACCOUNT, "church-name": "Grace Chapel"})
        self.assertFalse(ChurchProfile.objects.get(name="Grace Chapel").banner)

    def test_a_bad_banner_opens_the_profile_step_and_makes_nothing(self):
        pdf = SimpleUploadedFile("a.pdf", b"%PDF-1.4", content_type="application/pdf")
        response = self.client.post(
            REGISTER, {**ACCOUNT, "church-name": "Grace Chapel", "church-banner": pdf}
        )
        self.assertContains(response, 'data-au-start="2"')
        self.assertContains(response, 'id="id_church-banner_error"')
        self.assertFalse(ChurchProfile.objects.filter(name="Grace Chapel").exists())

    def test_a_chosen_banner_must_be_chosen_again_after_a_correction(self):
        response = self.client.post(
            REGISTER, {**ACCOUNT, "church-name": "", "church-banner": picture()}
        )
        self.assertContains(response, "Please choose the banner again")


class PublicPageTests(MediaMixin, TestCase):
    def setUp(self):
        super().setUp()
        complete_setup()
        self.church = first_church()
        self.church.show_in_directory = True
        self.church.save()
        self.page = reverse("churches:home", kwargs={"slug": self.church.slug})

    def test_without_a_banner_the_green_and_gold_cover_shows(self):
        response = self.client.get(self.page)
        self.assertContains(
            response, '<div class="pf-banner" aria-hidden="true"></div>'
        )
        self.assertNotContains(response, "pf-banner__img")

    def test_a_banner_fills_the_cover_and_the_logo_still_overlaps(self):
        self.church.banner = optimize_banner(picture())
        self.church.save()
        response = self.client.get(self.page)
        self.assertContains(response, 'class="pf-banner pf-banner--image"')
        self.assertContains(response, f'src="{self.church.banner.url}"')
        self.assertContains(response, 'class="pf-logo')

    def test_directory_cards_show_logos_only(self):
        self.church.banner = optimize_banner(picture())
        self.church.save()
        response = self.client.get(reverse("churches:directory"))
        self.assertNotContains(response, "church/banner/")


class SettingsTests(MediaMixin, TestCase):
    def setUp(self):
        super().setUp()
        complete_setup()
        self.client.force_login(make_administrator())
        self.url = reverse("church:settings", kwargs={"section": "homepage"})
        self.church = first_church()

    def data(self, **extra):
        return {
            "show_in_directory": "on",
            "about": "",
            "accept_outside_requests": "on",
            **extra,
        }

    def test_the_banner_field_is_on_the_public_homepage_settings(self):
        response = self.client.get(self.url)
        self.assertContains(response, 'name="banner"')
        self.assertContains(response, 'enctype="multipart/form-data"')
        self.assertIn("banner", ChurchHomepageForm.Meta.fields)

    def post(self, data):
        # The old file is deleted once the change is saved (on commit).
        with self.captureOnCommitCallbacks(execute=True):
            return self.client.post(self.url, data)

    def test_administrators_add_replace_and_remove_it(self):
        self.post(self.data(banner=picture()))
        self.church.refresh_from_db()
        first = self.church.banner.path
        self.assertTrue(os.path.exists(first))
        # Replacing deletes the old file.
        self.post(self.data(banner=picture("new.png", fmt="PNG")))
        self.church.refresh_from_db()
        self.assertNotEqual(self.church.banner.path, first)
        self.assertFalse(os.path.exists(first))
        second = self.church.banner.path
        # Removing clears it and deletes the file.
        self.post(self.data(**{"banner-clear": "on"}))
        self.church.refresh_from_db()
        self.assertFalse(self.church.banner)
        self.assertFalse(os.path.exists(second))

    def test_a_bad_file_is_refused_here_too(self):
        pdf = SimpleUploadedFile("a.pdf", b"%PDF-1.4", content_type="application/pdf")
        response = self.client.post(self.url, self.data(banner=pdf))
        self.assertEqual(response.status_code, 200)
        self.church.refresh_from_db()
        self.assertFalse(self.church.banner)
