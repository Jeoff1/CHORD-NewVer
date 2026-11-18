"""The keyword engine: a light stand-in for the ONNX models.

It needs no model files and gives the same answer every time, so every test
uses it, and a machine without the models can still run CHORD.

- ``score`` counts how many of a label's keywords the text uses:
  ``hits / (hits + 2)``, so one keyword gives 0.33, two give 0.5, four 0.67.
- ``embed`` hashes the text's words into a fixed-size vector (a bag of
  words), so texts sharing words come out similar.
"""

import math
import re
import zlib

DIMENSIONS = 256

STOP_WORDS = frozenset(
    """a an and are as at be but by for from has have he her his i in is it
    its me my of oh on or our she so that the their them they this to was we
    were will with you your yeah""".split()
)


def stem(word):
    """A crude stem so "praises" and "praise" match."""
    word = word.lower().removesuffix("'s")
    if len(word) > 3 and word.endswith("s") and not word.endswith("ss"):
        word = word[:-1]
    return word


def words(text):
    return [stem(word) for word in re.findall(r"[a-z']+", text.lower())]


class KeywordEngine:
    name = "keyword"
    # Bag-of-words cosines: 0 when no words are shared, rarely above 0.4.
    similarity_range = (0.0, 0.40)

    def score(self, text, labels):
        present = set(words(text))
        scores = []
        for label in labels:
            hits = len(present & {stem(word) for word in label.keywords})
            scores.append(hits / (hits + 2))
        return scores

    def embed(self, texts):
        return [self._embed_one(text) for text in texts]

    def _embed_one(self, text):
        vector = [0.0] * DIMENSIONS
        for word in words(text):
            if word not in STOP_WORDS:
                vector[zlib.crc32(word.encode("utf-8")) % DIMENSIONS] += 1.0
        length = math.sqrt(sum(value * value for value in vector))
        return [value / length for value in vector] if length else vector
