"""The model files the ONNX engine runs, and downloading them.

Models are fetched on demand with ``manage.py download_models`` into
``settings.ML_MODELS_DIR`` (which Git ignores), never in tests. Each model
gets its own folder holding ``model.onnx``, ``tokenizer.json`` and
``config.json``.
"""

import shutil
from dataclasses import dataclass
from pathlib import Path

MB = 1024 * 1024
# Room left on the disk after a download, so it never fills the drive.
SPARE_SPACE = 200 * MB


@dataclass(frozen=True)
class ModelSpec:
    folder: str
    repo_id: str
    small_file: str  # quantised ONNX file in the repo, the default
    full_file: str  # unquantised ONNX file, with --full
    small_size: int
    full_size: int
    licence: str

    def files(self, full=False):
        """Repository file -> local name."""
        return {
            self.full_file if full else self.small_file: "model.onnx",
            "tokenizer.json": "tokenizer.json",
            "config.json": "config.json",
        }

    def size(self, full=False):
        return self.full_size if full else self.small_size

    def is_installed(self, models_dir):
        folder = Path(models_dir) / self.folder
        return all((folder / name).is_file() for name in self.files().values())


EMBEDDING = ModelSpec(
    folder="all-MiniLM-L6-v2",
    repo_id="sentence-transformers/all-MiniLM-L6-v2",
    small_file="onnx/model_quint8_avx2.onnx",
    full_file="onnx/model.onnx",
    small_size=24 * MB,
    full_size=91 * MB,
    licence="Apache-2.0",
)
# The smaller xtremedistil zero-shot model (14 MB) was tried and rejected:
# it scored "Amazing Grace" 0.1 as praising God (decision 0006).
ZERO_SHOT = ModelSpec(
    folder="deberta-v3-xsmall-zeroshot",
    repo_id="MoritzLaurer/deberta-v3-xsmall-zeroshot-v1.1-all-33",
    small_file="onnx/model_quantized.onnx",
    full_file="onnx/model.onnx",
    small_size=96 * MB,
    full_size=293 * MB,
    licence="MIT",
)
MODELS = (EMBEDDING, ZERO_SHOT)


class DownloadError(Exception):
    pass


def hub_fetch(repo_id, filename, folder):
    """Download one file from the Hugging Face Hub into ``folder``."""
    from huggingface_hub import hf_hub_download

    return hf_hub_download(repo_id=repo_id, filename=filename, local_dir=folder)


def download(spec, models_dir, *, full=False, fetch=hub_fetch, free_space=None):
    """Download one model into ``models_dir/<folder>``; returns the folder.

    Refuses when the disk would be left with less than ``SPARE_SPACE``.
    """
    models_dir = Path(models_dir)
    models_dir.mkdir(parents=True, exist_ok=True)
    free = free_space if free_space is not None else shutil.disk_usage(models_dir).free
    needed = spec.size(full) + SPARE_SPACE
    if free < needed:
        raise DownloadError(
            f"{spec.folder} needs {needed // MB} MB free (with room to spare), "
            f"but only {free // MB} MB is free."
        )
    folder = models_dir / spec.folder
    staging = folder / ".download"
    staging.mkdir(parents=True, exist_ok=True)
    try:
        for repo_file, local_name in spec.files(full).items():
            fetched = Path(fetch(spec.repo_id, repo_file, staging))
            fetched.replace(folder / local_name)
    finally:
        shutil.rmtree(staging, ignore_errors=True)
    return folder
