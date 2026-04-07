"""Shared phrase libraries for lightweight noir flavor."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml

from noir.util.rng import Rng


def _repo_root() -> Path:
	return Path(__file__).resolve().parents[3]


@lru_cache(maxsize=1)
def load_noir_phrases() -> list[str]:
	path = _repo_root() / "assets" / "text_atoms" / "noir_phrases.yml"
	data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
	phrases = data.get("phrases", []) or []
	return [str(phrase).strip() for phrase in phrases if str(phrase).strip()]


def build_noir_phrase(rng: Rng) -> str | None:
	phrases = load_noir_phrases()
	if not phrases:
		return None
	return rng.choice(phrases)


@lru_cache(maxsize=1)
def load_recurring_npc_lines() -> dict[str, list[str]]:
	path = _repo_root() / "assets" / "text_atoms" / "recurring_npc_lines.yml"
	data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
	cleaned: dict[str, list[str]] = {}
	for key, values in data.items():
		items = [str(value).strip() for value in (values or []) if str(value).strip()]
		cleaned[str(key)] = items
	return cleaned


def build_partner_phrase(rng: Rng) -> str | None:
	lines = load_recurring_npc_lines().get("partner_lines", [])
	if not lines:
		return None
	return rng.choice(lines)


@lru_cache(maxsize=1)
def load_witness_lines() -> dict[str, list[str]]:
	path = _repo_root() / "assets" / "text_atoms" / "witness_lines.yml"
	data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
	cleaned: dict[str, list[str]] = {}
	for key, values in data.items():
		items = [str(value).strip() for value in (values or []) if str(value).strip()]
		cleaned[str(key)] = items
	return cleaned


def build_witness_line(rng: Rng, category: str = "lines") -> str | None:
	bank = load_witness_lines()
	lines = bank.get(category, []) or bank.get("lines", [])
	if not lines:
		return None
	return rng.choice(lines)
