import shutil
import tempfile

from django.core.files.base import ContentFile
from django.http import Http404
from django.test import SimpleTestCase, override_settings

from apps.core.storage import (
    PrivateFileInput,
    StoredFile,
    private_file_response,
    private_storage,
)

TEMP_PRIVATE = tempfile.mkdtemp()


@override_settings(PRIVATE_MEDIA_ROOT=TEMP_PRIVATE)
class PrivateStorageTests(SimpleTestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEMP_PRIVATE, ignore_errors=True)

    def test_files_have_no_public_url(self):
        with self.assertRaises(ValueError):
            private_storage.url("anything.pdf")

    def test_files_live_under_the_private_root(self):
        name = private_storage.save("t/doc.txt", ContentFile(b"x"))
        self.assertTrue(private_storage.path(name).startswith(TEMP_PRIVATE))

    def test_response_downloads_unless_inline(self):
        name = private_storage.save("t/page.html", ContentFile(b"<script>"))
        response = private_file_response(name)
        self.assertIn("attachment", response["Content-Disposition"])
        response.close()
        response = private_file_response(name, inline=True)
        self.assertIn("inline", response["Content-Disposition"])
        response.close()

    def test_missing_file_is_404(self):
        with self.assertRaises(Http404):
            private_file_response("t/missing.pdf")
        with self.assertRaises(Http404):
            private_file_response("")


class PrivateFileInputTests(SimpleTestCase):
    def test_shows_current_file_with_given_link(self):
        widget = PrivateFileInput(url="/members/x/photo/")
        html = widget.render("photo", StoredFile("members/photos/abc/me.png"))
        self.assertIn('href="/members/x/photo/"', html)
        self.assertIn("me.png", html)
        self.assertNotIn("abc", html)
