"""Lightweight grammar normalization for presentation strings."""

from __future__ import annotations

import re

_FIRST_ALPHA = re.compile(r"[A-Za-z]")


def normalize_line(text: str) -> str:
    """Normalize spacing and capitalization without changing meaning."""
    if not text:
        return text
    stripped = " ".join(text.strip().split())
    if not stripped:
        return stripped
    if stripped.isupper():
        return stripped
    match = _FIRST_ALPHA.search(stripped)
    if not match:
        return stripped
    idx = match.start()
    if stripped[idx].isupper():
        return stripped
    return stripped[:idx] + stripped[idx].upper() + stripped[idx + 1 :]


def normalize_lines(lines: list[str]) -> list[str]:
    """Normalize a list of lines, preserving empty lines."""
    return [normalize_line(line) if line else line for line in lines]


def place_with_article(place: str) -> str:
    """Ensure location strings read naturally with an article."""
    trimmed = place.strip()
    lowered = trimmed.lower()
    if lowered.startswith(("the ", "a ", "an ")):
        return trimmed
    return f"the {trimmed}"
