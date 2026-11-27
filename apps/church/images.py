"""The church banner (owner, 27 Nov 2026; Design-System.md, "Registering a
church"): checked, then saved as a small WebP copy.

``optimize_banner`` turns the photo the right way up, leaves out its hidden
details (camera, GPS location), makes it at most ``BANNER_MAX_WIDTH`` wide
(never wider than it was, never cropped or stretched: the height follows the
width) and saves it as WebP. ``BannerFieldMixin`` gives a ModelForm with a
``banner`` field the checks and the copy, and deletes a banner it replaces
or clears once the change is saved.
"""

from io import BytesIO

from django import forms
from django.core.files.base import ContentFile
from django.db import transaction
from PIL import Image, ImageOps

MAX_BANNER_BYTES = 5 * 1024 * 1024
BANNER_EXTENSIONS = ["jpg", "jpeg", "png", "webp"]
BANNER_FORMATS = {"JPEG", "PNG", "WEBP"}
BANNER_MAX_WIDTH = 1920
# Far more than any banner needs; stops an image that would take too much
# memory to open.
BANNER_MAX_PIXELS = 40_000_000
BANNER_QUALITY = 82
BANNER_HELP = "1920 × 640 px recommended (3:1). JPG, PNG or WebP, 5 MB at most."


def optimize_banner(upload):
    """A WebP copy of ``upload`` (an image already opened once by Django's
    ImageField), ready to save as the banner."""
    upload.seek(0)
    with Image.open(upload) as opened:
        image = ImageOps.exif_transpose(opened)
        has_alpha = image.mode in ("RGBA", "LA") or (
            image.mode == "P" and "transparency" in image.info
        )
        image = image.convert("RGBA" if has_alpha else "RGB")
        if image.width > BANNER_MAX_WIDTH:
            height = max(1, round(image.height * BANNER_MAX_WIDTH / image.width))
            image = image.resize((BANNER_MAX_WIDTH, height), Image.Resampling.LANCZOS)
        out = BytesIO()
        image.save(out, "WEBP", quality=BANNER_QUALITY, method=6)
    return ContentFile(out.getvalue(), name="banner.webp")


class BannerFieldMixin:
    """For a ModelForm of the Church Profile with a ``banner`` field."""

    def clean_banner(self):
        banner = self.cleaned_data.get("banner")
        # Nothing new chosen (None or the current file) or cleared (False).
        if not banner or not hasattr(banner, "content_type"):
            return banner
        extension = banner.name.rsplit(".", 1)[-1].lower() if "." in banner.name else ""
        if extension not in BANNER_EXTENSIONS:
            raise forms.ValidationError("Choose a JPG, PNG or WebP image.")
        if banner.size > MAX_BANNER_BYTES:
            raise forms.ValidationError("The banner must be 5 MB or smaller.")
        image = getattr(banner, "image", None)
        if image is None or image.format not in BANNER_FORMATS:
            raise forms.ValidationError("Choose a JPG, PNG or WebP image.")
        if image.width * image.height > BANNER_MAX_PIXELS:
            raise forms.ValidationError(
                "The banner is too large to use. Try a smaller image."
            )
        return optimize_banner(banner)

    def save(self, commit=True):
        old = (
            self.instance.__class__.objects.filter(pk=self.instance.pk)
            .values_list("banner", flat=True)
            .first()
            if self.instance.pk
            else None
        )
        saved = super().save(commit=commit)
        if commit and old and old != saved.banner.name:
            storage = saved.banner.storage
            transaction.on_commit(lambda: storage.delete(old))
        return saved
