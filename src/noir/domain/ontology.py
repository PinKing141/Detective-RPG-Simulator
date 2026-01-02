"""Ontology helpers for soft matching."""

from __future__ import annotations

SYNONYMS = {
    "stabbed": "attack_with_sharp_object",
    "stabbing": "attack_with_sharp_object",
    "knife": "sharp_object",
}


def normalize_label(label: str) -> str:
    key = label.strip().lower().replace(" ", "_")
    return SYNONYMS.get(key, key)
