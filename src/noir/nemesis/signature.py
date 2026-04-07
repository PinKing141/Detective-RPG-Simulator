"""Fixed nemesis signature helpers for case projection."""

from __future__ import annotations

from typing import TYPE_CHECKING

from noir.util.rng import Rng

if TYPE_CHECKING:
	from noir.nemesis.state import NemesisProfile
	from noir.truth.graph import TruthState


def build_signature_meta(profile: "NemesisProfile", rng: Rng) -> dict[str, str]:
	placement = _placement_hint(profile.signature_staging, rng)
	return {
		"token": profile.signature_token,
		"staging": profile.signature_staging,
		"message": profile.signature_message,
		"placement_hint": placement,
	}


def apply_signature_to_truth(truth: "TruthState", profile: "NemesisProfile", rng: Rng) -> dict[str, str]:
	meta = build_signature_meta(profile, rng)
	truth.case_meta["nemesis_signature"] = meta
	return meta


def _placement_hint(staging: str, rng: Rng) -> str:
	if staging == "posed":
		return rng.choice(["near the body", "in plain view", "where the room narrows"])
	if staging == "covered":
		return rng.choice(["partly obscured by nearby clutter", "under a folded layer of fabric", "beneath a mundane object"])
	if staging == "hidden":
		return rng.choice(["just off the main sightline", "where only a second pass would catch it", "tucked beside the exit path"])
	return rng.choice(["near the point of entry", "close to the victim", "where the scene naturally draws the eye"])
