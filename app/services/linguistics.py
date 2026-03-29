"""
Deterministic token-level features for perception / evidence UI (negation, intensifiers, diminishers).
"""
from __future__ import annotations

import re
from typing import Any

# Common English forms (lowercase, matching is case-insensitive on word tokens)
NEGATION_WORDS = frozenset(
    {
        "not",
        "no",
        "never",
        "neither",
        "nobody",
        "nothing",
        "nowhere",
        "nor",
        "cannot",
        "can't",
        "cant",
        "don't",
        "dont",
        "doesn't",
        "doesnt",
        "didn't",
        "didnt",
        "won't",
        "wont",
        "wouldn't",
        "wouldnt",
        "shouldn't",
        "shouldnt",
        "couldn't",
        "couldnt",
        "isn't",
        "isnt",
        "aren't",
        "arent",
        "wasn't",
        "wasnt",
        "weren't",
        "werent",
        "haven't",
        "havent",
        "hasn't",
        "hasnt",
        "hadn't",
        "hadnt",
        "ain't",
        "aint",
    }
)

INTENSIFIER_WORDS = frozenset(
    {
        "very",
        "really",
        "extremely",
        "incredibly",
        "absolutely",
        "totally",
        "completely",
        "highly",
        "especially",
        "particularly",
        "exceptionally",
        "remarkably",
        "quite",
        "so",
        "too",
        "utterly",
    }
)

DIMINISHER_WORDS = frozenset(
    {
        "slightly",
        "somewhat",
        "barely",
        "hardly",
        "scarcely",
        "rather",
        "fairly",
        "partially",
        "partly",
        "marginally",
    }
)


def _tokens(text: str) -> list[str]:
    if not text or not str(text).strip():
        return []
    return re.findall(r"\b[\w']+\b", text.lower())


def extract_linguistic_features(text: str) -> dict[str, Any]:
    """
    Returns counts and matched surface forms for negations / intensifiers / diminishers.
    """
    char_count = len(text)
    word_count = len(text.split()) if text.strip() else 0

    toks = _tokens(text)
    if not toks:
        return {
            "word_count": word_count,
            "character_count": char_count,
            "negation_words": [],
            "negations_found": 0,
            "intensifier_words": [],
            "intensifiers_found": 0,
            "diminisher_words": [],
            "diminishers_found": 0,
        }

    neg_hits: list[str] = []
    int_hits: list[str] = []
    dim_hits: list[str] = []
    dim_count = 0

    for w in toks:
        if w in NEGATION_WORDS:
            neg_hits.append(w)
        elif w in INTENSIFIER_WORDS:
            int_hits.append(w)
        elif w in DIMINISHER_WORDS:
            dim_hits.append(w)
            dim_count += 1

    lower = text.lower()
    for phrase in ("kind of", "sort of", "a little bit", "a little"):
        n = lower.count(phrase)
        if n:
            dim_count += n
            dim_hits.extend([phrase] * n)

    return {
        "word_count": word_count,
        "character_count": char_count,
        "negation_words": sorted(set(neg_hits)),
        "negations_found": len(neg_hits),
        "intensifier_words": sorted(set(int_hits)),
        "intensifiers_found": len(int_hits),
        "diminisher_words": sorted(set(dim_hits)),
        "diminishers_found": dim_count,
    }
