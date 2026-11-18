"""The ONNX engine: a sentence-embedding model and a zero-shot classifier
run with ONNX Runtime (decision 0006).

- Embeddings: all-MiniLM-L6-v2, mean-pooled and scaled to unit length.
- Zero-shot: an NLI model asked whether the lyrics entail each label's
  hypothesis ("This song is about grace.").

The runtime and tokenizer are imported only when the engine is built, so
nothing here loads unless ``settings.ML_ENGINE`` is "onnx".
"""

import json
from pathlib import Path

import numpy as np

from . import EngineUnavailable
from .catalog import EMBEDDING, MODELS, ZERO_SHOT

EMBEDDING_TOKENS = 256
CLASSIFIER_TOKENS = 512
BATCH = 8


def mean_pool(hidden, mask):
    """Average each text's token vectors, ignoring padding."""
    mask = mask[..., None].astype(hidden.dtype)
    return (hidden * mask).sum(axis=1) / np.clip(mask.sum(axis=1), 1e-9, None)


def unit_length(vectors):
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    return vectors / np.clip(norms, 1e-12, None)


def label_indices(config):
    """(entailment, contradiction) positions from a model's config.json;
    contradiction is None for a two-way model ("not_entailment")."""
    names = {int(index): name.lower() for index, name in config["id2label"].items()}
    entail = next(i for i, name in names.items() if name.startswith("entail"))
    contra = next((i for i, name in names.items() if name == "contradiction"), None)
    return entail, contra


def entailment_probability(logits, entail, contra=None):
    """Probability of entailment per row. A three-way model compares
    entailment with contradiction only, the usual multi-label zero-shot
    reading."""
    if contra is not None:
        logits = logits[:, [entail, contra]]
        entail = 0
    shifted = logits - logits.max(axis=1, keepdims=True)
    exp = np.exp(shifted)
    return exp[:, entail] / exp.sum(axis=1)


class _Model:
    def __init__(self, folder, max_tokens):
        import onnxruntime
        from tokenizers import Tokenizer

        self.tokenizer = Tokenizer.from_file(str(folder / "tokenizer.json"))
        self.tokenizer.enable_truncation(max_length=max_tokens)
        self.tokenizer.enable_padding()
        options = onnxruntime.SessionOptions()
        options.log_severity_level = 3
        self.session = onnxruntime.InferenceSession(
            str(folder / "model.onnx"), options, providers=["CPUExecutionProvider"]
        )
        self.inputs = {item.name for item in self.session.get_inputs()}
        self.config = json.loads((folder / "config.json").read_text("utf-8"))

    def run(self, encodings):
        feed = {
            "input_ids": [e.ids for e in encodings],
            "attention_mask": [e.attention_mask for e in encodings],
            "token_type_ids": [e.type_ids for e in encodings],
        }
        feed = {
            name: np.array(value, dtype=np.int64)
            for name, value in feed.items()
            if name in self.inputs
        }
        return self.session.run(None, feed)[0], feed["attention_mask"]


class OnnxEngine:
    # Theme-to-lyrics cosines of all-MiniLM-L6-v2 run from about 0.2 (no
    # match) to 0.6 (a close match): measured in the smoke test of
    # 2026-11-18, where "Hark! the Herald" scored 0.59 for a Christmas theme
    # and Rock of Ages 0.18. Ranking maps this range onto 0 to 1.
    similarity_range = (0.20, 0.60)

    def __init__(self, models_dir):
        models_dir = Path(models_dir)
        missing = [spec.folder for spec in MODELS if not spec.is_installed(models_dir)]
        if missing:
            raise EngineUnavailable(
                f"The song models are not installed in {models_dir} (missing: "
                f"{', '.join(missing)}). Run `python manage.py download_models`, "
                "or set ML_ENGINE=keyword in .env."
            )
        self.name = f"onnx:{EMBEDDING.folder}"
        self.embedder = _Model(models_dir / EMBEDDING.folder, EMBEDDING_TOKENS)
        self.classifier = _Model(models_dir / ZERO_SHOT.folder, CLASSIFIER_TOKENS)
        self.classifier.tokenizer.enable_truncation(
            max_length=CLASSIFIER_TOKENS, strategy="only_first"
        )
        self.entail, self.contra = label_indices(self.classifier.config)

    def embed(self, texts):
        vectors = []
        for start in range(0, len(texts), BATCH):
            batch = self.embedder.tokenizer.encode_batch(texts[start : start + BATCH])
            hidden, mask = self.embedder.run(batch)
            vectors.extend(unit_length(mean_pool(hidden, mask)).tolist())
        return vectors

    def score(self, text, labels):
        pairs = [(text, label.hypothesis) for label in labels]
        scores = []
        for start in range(0, len(pairs), BATCH):
            batch = self.classifier.tokenizer.encode_batch(pairs[start : start + BATCH])
            logits, _ = self.classifier.run(batch)
            probability = entailment_probability(logits, self.entail, self.contra)
            scores.extend(float(value) for value in probability)
        return scores
