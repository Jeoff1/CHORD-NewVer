"""Private file storage: uploads that hold personal data.

Files live under ``PRIVATE_MEDIA_ROOT`` (outside ``MEDIA_ROOT``), have no
public URL, and reach a browser only through a view that checks permission
and returns ``private_file_response``.
"""

import os
import uuid

from django import forms
from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.http import FileResponse, Http404


class PrivateStorage(FileSystemStorage):
    """File storage rooted at ``settings.PRIVATE_MEDIA_ROOT``, read each time
    so tests can point it elsewhere."""

    @property
    def base_location(self):
        return settings.PRIVATE_MEDIA_ROOT

    @property
    def location(self):
        return os.path.abspath(self.base_location)

    def url(self, name):
        raise ValueError("Private files have no public URL; serve them via a view.")


private_storage = PrivateStorage()


def get_private_storage():
    """Callable for ``FileField(storage=...)`` so migrations stay stable."""
    return private_storage


def random_upload_name(folder, filename):
    """``folder/<random>/<name>``: unguessable, and keeps the original name.

    Wrap it in a module-level ``upload_to`` function, since migrations can't
    store closures.
    """
    return f"{folder}/{uuid.uuid4().hex}/{os.path.basename(filename)}"


def private_file_response(name, *, inline=False):
    """Stream a private file. Non-images download as attachments, so an
    uploaded HTML file can never run in the browser."""
    if not name or not private_storage.exists(name):
        raise Http404("File not found.")
    return FileResponse(
        private_storage.open(name, "rb"),
        as_attachment=not inline,
        filename=os.path.basename(name),
    )


class StoredFile(str):
    """A stored private file's name, shown by file inputs as the current
    file and linking to ``url`` (a permission-checked view)."""

    def __new__(cls, name, url="#"):
        stored = super().__new__(cls, name)
        stored.url = url
        return stored

    @property
    def name(self):
        return self.rsplit("/", 1)[-1]

    def __str__(self):
        return self.name


class PrivateFileInput(forms.ClearableFileInput):
    """File input for a private ``FileField``/``ImageField``: shows the
    current file with a link to ``url`` instead of asking storage for a
    public URL (which private storage doesn't have)."""

    def __init__(self, attrs=None, url="#"):
        super().__init__(attrs)
        self.url = url

    def is_initial(self, value):
        return bool(value) and bool(getattr(value, "name", value))

    def format_value(self, value):
        if self.is_initial(value):
            return StoredFile(getattr(value, "name", value), self.url)
        return None
