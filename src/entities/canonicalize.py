"""Canonical name generation utilities."""
from __future__ import annotations

import re

_SUFFIXES = ("llc", "inc", "corp", "ltd", "lp")
_SUFFIX_PATTERN = re.compile(rf"\b({'|'.join(_SUFFIXES)})\b")
_NON_ALNUM_PATTERN = re.compile(r"[^a-z0-9\s]")


def canonicalize(name: str) -> str:
    """Normalize name for matching.

    Raises:
        ValueError: If normalization results in an empty canonical name.
    """
    normalized = name.lower()
    normalized = _NON_ALNUM_PATTERN.sub("", normalized)
    normalized = " ".join(normalized.split())
    normalized = _SUFFIX_PATTERN.sub("", normalized)
    normalized = " ".join(normalized.split())
    normalized = normalized.strip()
    if not normalized:
        raise ValueError(
            f"canonicalize() produced an empty canonical name from input {name!r}"
        )
    return normalized
