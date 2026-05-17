"""Slug generation for agent names. Public URL: `/agents/[slug]`."""

from __future__ import annotations

import re
import unicodedata

_NON_ALNUM = re.compile(r"[^a-z0-9]+")
_LEADING_TRAILING_HYPHENS = re.compile(r"^-+|-+$")


def slugify(name: str) -> str:
    """Lowercase, ASCII-fold, replace non-alphanumeric with `-`, collapse runs.

    >>> slugify("Kevin's Predictor v2")
    'kevin-s-predictor-v2'
    >>> slugify("Tomás-Río")
    'tomas-rio'
    """
    folded = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    lowered = folded.lower()
    hyphenated = _NON_ALNUM.sub("-", lowered)
    return _LEADING_TRAILING_HYPHENS.sub("", hyphenated)
