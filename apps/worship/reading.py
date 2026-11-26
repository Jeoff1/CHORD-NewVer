"""Reading a theme for the models (Phase 9C).

The embedding model reads at most 256 tokens (about 200 words) and the tag
model 512, so one long text, such as a sermon PDF, would be cut off near
its start. A theme longer than one passage is therefore read in passages
of ``PASSAGE_WORDS`` words, and **each part has its own share** (owner,
2026-11-26):

- the **heading** (title and main scripture reference) is half of the
  theme's vector;
- the **body's parts** (the notes, the passage's Bible text and the sermon
  PDF's text) share the other half equally, whatever their length: each
  part is the average of its own passages, so 30 words of notes count as
  much as a 10-page sermon. An empty part is left out and the others share
  its part.
- **Theme Tags** are scored the same way: each part's passages, read with
  the heading, are averaged within the part, then the parts equally.
- **Search phrases** are drawn from every part in equal numbers, so a
  long PDF doesn't crowd the notes out.

A short theme (at most one passage in all) is read whole, as before. Only
the church's own theme text reaches the models (AGENTS.md).
"""

import math

PASSAGE_WORDS = 150  # well inside the embedding model's 256 tokens
MAX_PASSAGES = 24  # shared by the parts; a long one is sampled evenly
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


def parts(theme):
    """The body's parts, each with its own share: the notes, the passage's
    Bible text and the sermon PDF's text, leaving out empty ones."""
    return [
        part
        for part in (theme.notes, theme.scripture_text, theme.document_text)
        if part.strip()
    ]


def _normalised(vector):
    length = math.sqrt(sum(value * value for value in vector))
    return [value / length for value in vector] if length else list(vector)


def _mean(vectors):
    return [sum(values) / len(vectors) for values in zip(*vectors)]


def theme_vector(theme, engine):
    """The theme's embedding, from all of its text."""
    body_parts = parts(theme)
    if is_short(theme) or not body_parts:
        return engine.embed([theme.text()])[0]
    share = max(1, MAX_PASSAGES // len(body_parts))
    groups = [passages(part, limit=share) for part in body_parts]
    heading_vector, *vectors = engine.embed(
        [theme.heading(), *(text for group in groups for text in group)]
    )
    part_vectors, start = [], 0
    for group in groups:
        part_vectors.append(_normalised(_mean(vectors[start : start + len(group)])))
        start += len(group)
    body = _normalised(_mean(part_vectors))
    return _normalised([h + b for h, b in zip(heading_vector, body)])


def tag_texts(theme):
    """The texts the tag model scores, in groups: one group per part, whose
    scores are averaged within it, then across the groups."""
    body_parts = parts(theme)
    if is_short(theme) or not body_parts:
        return [[theme.text()]]
    heading = theme.heading()
    share = max(1, TAG_PASSAGES // len(body_parts))
    return [
        [f"{heading}\n{passage}" for passage in passages(part, limit=share)]
        for part in body_parts
    ]


def phrase_sources(theme):
    """The texts search phrases are drawn from in equal numbers: the
    heading and each part (None for a short theme, read whole)."""
    if is_short(theme):
        return None
    return [theme.heading(), *parts(theme)]
