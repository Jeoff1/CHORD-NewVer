"""Download the ONNX models that song analysis runs (decision 0006)."""

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.songs.ml import catalog


class Command(BaseCommand):
    help = (
        "Download the song models (sentence embeddings and a zero-shot "
        "classifier) into ML_MODELS_DIR."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--full",
            action="store_true",
            help="Download the unquantised models (larger, slightly more accurate).",
        )
        parser.add_argument(
            "--force", action="store_true", help="Download models already installed."
        )

    def handle(self, *args, full=False, force=False, **options):
        models_dir = settings.ML_MODELS_DIR
        for spec in catalog.MODELS:
            if spec.is_installed(models_dir) and not force:
                self.stdout.write(f"{spec.folder} is already installed.")
                continue
            size = spec.size(full) // catalog.MB
            self.stdout.write(f"Downloading {spec.repo_id} ({size} MB, {spec.licence})")
            try:
                folder = self.download(spec, models_dir, full=full)
            except catalog.DownloadError as error:
                raise CommandError(str(error)) from error
            self.stdout.write(self.style.SUCCESS(f"Saved in {folder}"))

    def download(self, spec, models_dir, *, full):
        return catalog.download(spec, models_dir, full=full)
