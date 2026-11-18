"""Search phrases: the key words and short phrases of a theme.

The theme's title is the first phrase when it is short. The rest are picked
the way KeyBERT does it, with the ML engine's embeddings: every one- to
three-word phrase in the theme is compared with the whole theme, and the
closest are taken, skipping any too close to one already taken (maximal
marginal relevance), so the searches cover different ideas.
"""

import re
from collections import Counter

STOP_WORDS = frozenset(
    """a about above after again against all also am an and any are as at be
    because been before being below between both but by can could did do
    does doing down during each even every few for from further had has have
    having he her here hers him his how i if in into is it its itself just
    let like may me might more most much must my no nor not now of off on
    once only or other our ours out over own same shall she should so some
    such than that the their theirs them then there these they this those
    through to too under until up upon us very was we were what when where
    which while who whom why will with would yet you your yours""".split()
)
MAX_TITLE_WORDS = 5
MAX_CANDIDATES = 150
DIVERSITY = 0.5  # 0 keeps the closest phrases; 1 keeps the most varied


def _words(fragment):
    return re.findall(r"[a-z][a-z']*", fragment.lower())


def candidates(text, max_words=3):
    """One- to three-word phrases that neither start nor end with a stop
    word, most frequent first. Numbers (such as verse references) are left
    out."""
    counts, first_seen = Counter(), {}
    for fragment in re.split(r"[.,;:!?()\[\]\"\n–—-]+", text):
        if re.search(r"\d", fragment):
            fragment = re.sub(r"\S*\d\S*", " ", fragment)
        words = _words(fragment)
        for size in range(1, max_words + 1):
            for start in range(len(words) - size + 1):
                gram = words[start : start + size]
                if gram[0] in STOP_WORDS or gram[-1] in STOP_WORDS:
                    continue
                if size == 1 and len(gram[0]) < 3:
                    continue
                phrase = " ".join(gram)
                counts[phrase] += 1
                first_seen.setdefault(phrase, len(first_seen))
    ranked = sorted(counts, key=lambda p: (-counts[p], first_seen[p]))
    return ranked[:MAX_CANDIDATES]


def _similarity(a, b):
    return sum(x * y for x, y in zip(a, b))


def search_phrases(title, text, count, engine):
    """Up to ``count`` phrases to search for, from a theme's title and its
    whole text."""
    phrases = []
    title_words = _words(title)
    if 0 < len(title_words) <= MAX_TITLE_WORDS:
        phrases.append(" ".join(title_words))
    pool = [p for p in candidates(text) if p not in phrases]
    if len(phrases) >= count or not pool:
        return phrases[:count]

    theme_vector, *vectors = engine.embed([text, *pool])
    closeness = [_similarity(theme_vector, v) for v in vectors]
    chosen = []
    while pool and len(phrases) + len(chosen) < count:
        best, best_score = None, None
        for i, phrase in enumerate(pool):
            if any(set(phrase.split()) <= set(c.split()) for c in phrases):
                continue
            overlap = max(
                (_similarity(vectors[i], vectors[j]) for j in chosen), default=0.0
            )
            score = (1 - DIVERSITY) * closeness[i] - DIVERSITY * overlap
            if best_score is None or score > best_score:
                best, best_score = i, score
        if best is None:
            break
        chosen.append(best)
        phrases.append(pool[best])
        pool[best] = ""  # taken; keeps the indexes of vectors in step
    return [p for p in phrases if p][:count]
