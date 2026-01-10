"""Canonical name generation utilities."""
from __future__ import annotations

import re

_SUFFIXES = ("llc", "inc", "corp", "ltd", "lp")
_SUFFIX_PATTERN = re.compile(rf"\b({'|'.join(_SUFFIXES)})\b")
_NON_ALNUM_PATTERN = re.compile(r"[^a-z0-9\s]")


def canonicalize(name: str) -> str:
    """Normalize name for matching."""
    normalized = name.lower()
    normalized = _NON_ALNUM_PATTERN.sub("", normalized)
    normalized = " ".join(normalized.split())
    normalized = _SUFFIX_PATTERN.sub("", normalized)
    normalized = " ".join(normalized.split())
    return normalized.strip()
