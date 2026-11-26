"""Reading a theme for the models (Phase 9C).

The embedding model reads at most 256 tokens (about 200 words) and the tag
model 512, so one long text, such as a sermon PDF, would be cut off near
its start. A theme longer than one passage is therefore read in passages
of ``PASSAGE_WORDS`` words:

- its **vector** is the heading's vector (title and main passage) plus the
  average of the body's passage vectors (notes and the sermon PDF), so the
  title keeps its weight and every part of the sermon counts;
- its **Theme Tags** are scored on up to ``TAG_PASSAGES`` passages spread
  over the body, each read with the heading, and averaged.

A short theme is read whole, as before. Only the church's own theme text
reaches the models (AGENTS.md).
"""

import math

PASSAGE_WORDS = 150  # well inside the embedding model's 256 tokens
MAX_PASSAGES = 24  # a long sermon is sampled evenly, start to end
TAG_PASSAGES = 6  # the tag model is slower: fewer passages


def passages(text, *, size=PASSAGE_WORDS, limit=MAX_PASSAGES):
    """``text`` in passages of ``size`` words; at most ``limit`` of them,
    spread evenly from the first to the last."""
    words = text.split()
    chunks = [" ".join(words[i : i + size]) for i in range(0, len(words), size)]
    if len(chunks) <= limit:
        return chunks
    if limit == 1:
        return chunks[:1]
    last = len(chunks) - 1
    return [chunks[round(i * last / (limit - 1))] for i in range(limit)]


def is_short(theme):
    return len(theme.text().split()) <= PASSAGE_WORDS


def _normalised(vector):
    length = math.sqrt(sum(value * value for value in vector))
    return [value / length for value in vector] if length else list(vector)


def theme_vector(theme, engine):
    """The theme's embedding, from all of its text."""
    if is_short(theme):
        return engine.embed([theme.text()])[0]
    heading_vector, *vectors = engine.embed([theme.heading(), *passages(theme.body())])
    body = _normalised([sum(values) / len(vectors) for values in zip(*vectors)])
    return _normalised([h + b for h, b in zip(heading_vector, body)])


def tag_texts(theme):
    """The texts the tag model scores for the theme."""
    if is_short(theme):
        return [theme.text()]
    heading = theme.heading()
    return [
        f"{heading}\n{passage}"
        for passage in passages(theme.body(), limit=TAG_PASSAGES)
    ]
