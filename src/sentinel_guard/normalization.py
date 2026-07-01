from __future__ import annotations

import re
import unicodedata
from typing import Pattern


_NON_BREAKING_SPACE = "\u00A0"
_SPACE_PATTERN: Pattern[str] = re.compile(r"[ \t\u00A0]+")
_PUNCTUATION_NORMALIZATION = str.maketrans({
    "“": '"',
    "”": '"',
    "‘": "'",
    "’": "'",
    "«": '"',
    "»": '"',
})


def normalize_text(text: str) -> str:
    """Normalize text for deterministic verbatim comparison."""
    normalized = unicodedata.normalize("NFC", text)
    normalized = normalized.translate(_PUNCTUATION_NORMALIZATION)
    normalized = normalized.replace(_NON_BREAKING_SPACE, " ")
    normalized = _SPACE_PATTERN.sub(" ", normalized)
    return normalized.strip()


def normalize_numeric(text: str) -> str:
    """Normalize numeric strings for strict tracked data comparison."""
    normalized = normalize_text(text)
    normalized = normalized.replace("\u202F", "")
    normalized = normalized.replace(" ", "")
    return normalized
