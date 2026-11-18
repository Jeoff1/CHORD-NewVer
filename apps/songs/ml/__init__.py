"""The ML engine that reads song lyrics and theme text.

Two engines share one small interface:

- ``embed(texts)`` returns one unit-length vector per text, so the dot
  product of two vectors is their similarity.
- ``score(text, labels)`` returns, for each ``Label``, how likely (0 to 1)
  its hypothesis is true of the text. Labels are scored independently.
- ``similarity_range`` is ``(low, high)``: the similarity of unrelated
  texts and of a close match, so ranking can turn similarities into fixed
  0-to-1 relevance and match labels.

``settings.ML_ENGINE`` picks the engine: "onnx" runs the downloaded models
with ONNX Runtime (decision 0006); "keyword" is a light stand-in that counts
keywords and needs no model files. Tests always use the keyword engine.

Only lyrics and the church's own text go into an engine, never Spotify data.
"""

from dataclasses import dataclass, field

from django.conf import settings


class EngineUnavailable(Exception):
    """The configured engine can't run, e.g. its model files are missing."""


@dataclass(frozen=True)
class Label:
    """Something a text may be: a sentence for a zero-shot model to test,
    and the words the keyword engine looks for instead."""

    hypothesis: str
    keywords: frozenset = field(default_factory=frozenset)


_engines = {}


def get_engine():
    """The engine ``settings.ML_ENGINE`` names, loaded once per process."""
    kind = settings.ML_ENGINE
    if kind not in _engines:
        _engines[kind] = _build(kind)
    return _engines[kind]


def _build(kind):
    if kind == "keyword":
        from .keyword import KeywordEngine

        return KeywordEngine()
    if kind == "onnx":
        from .onnx import OnnxEngine

        return OnnxEngine(settings.ML_MODELS_DIR)
    raise EngineUnavailable(
        f'Unknown ML_ENGINE "{kind}". Use "onnx" or "keyword" in .env.'
    )
