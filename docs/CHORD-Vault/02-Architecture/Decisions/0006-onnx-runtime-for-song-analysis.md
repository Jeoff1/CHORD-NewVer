---
status: accepted
---

# Song analysis runs ONNX models, with a keyword stand-in

Song analysis (the worship check, theme tags, the feel guess and lyrics
embeddings) runs small Hugging Face models exported to ONNX, with ONNX
Runtime and the `tokenizers` library, not PyTorch. The user chose this on
2026-11-16: the development machine's C: drive had about 3.7 GB free, and
PyTorch with sentence-transformers needs well over 1 GB before any model.
ONNX Runtime, `tokenizers` and NumPy together take about 60 MB.

`settings.ML_ENGINE` picks the engine (`apps/songs/ml/`):

- **`onnx`** (the default): two models fetched by `manage.py
  download_models` into `ML_MODELS_DIR` (`ml_models/`, ignored by Git):
  - embeddings: `sentence-transformers/all-MiniLM-L6-v2`, the quantised
    `model_quint8_avx2.onnx` (23 MB, Apache-2.0), mean-pooled to 384
    numbers;
  - zero-shot: `MoritzLaurer/deberta-v3-xsmall-zeroshot-v1.1-all-33`,
    `model_quantized.onnx` plus its tokenizer (96 MB, MIT).
  - `--full` fetches the unquantised files (91 MB and 293 MB).
- **`keyword`**: counts keywords and hashes words into a vector. It needs
  no files, gives the same answer every time, and is the engine every test
  uses (the test runner sets it).

## Considered Options

- **PyTorch with sentence-transformers and transformers pipelines**: the
  brief's suggestion. Rejected for disk size.
- **The smaller `xtremedistil-l6-h256` zero-shot model** (13 MB): measured
  on 2026-11-17 against four public-domain hymns and four invented secular
  songs. It scored "Amazing Grace" 0.12 for "This text praises God", so it
  couldn't tell worship lyrics apart. DeBERTa-v3-xsmall scored the hymns
  0.86 to 0.999 and the secular songs at most 0.01, in about one second per
  song.

## Consequences

- Hypotheses describe what the words say ("This text praises God."). A
  hypothesis about the kind of text ("This is a Christian worship song.")
  scored hymns near 0 with both models.
- The worship score is the better of "This text praises God." and "This
  text is about God."; a song passes at 0.5. A Trusted Artist adds 0.25.
  An invented love song full of church imagery still passed in the
  measurement, which is why people can correct the check.
- Embeddings from different engines can't be compared, so each song
  records the engine that analysed it (`analysed_with`).
- Web requests never load a model: analysis runs in `manage.py
  process_songs`, and from Phase 5 in the search worker.
- The quantised embedding model needs a CPU with AVX2; use `--full` on one
  without it.
