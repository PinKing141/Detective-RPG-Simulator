"""Adaptive MO weighting for persistent nemesis behavior."""

from __future__ import annotations

from typing import TYPE_CHECKING

from noir.util.rng import Rng

if TYPE_CHECKING:
	from noir.nemesis.state import NemesisCasePlan, NemesisComponent, NemesisState


_ADAPT_COOLDOWN = 2
_COMPROMISED_WEIGHT_FACTOR = 0.35
_COOLDOWN_WEIGHT_FACTOR = 0.75
_COMPROMISE_WEIGHT_PENALTY = 0.7
_COMPROMISE_COMPETENCE_PENALTY = 0.12
_USE_WEIGHT_BOOST = 0.06
_USE_COMPETENCE_BOOST = 0.05
_FAILED_USE_WEIGHT_BOOST = 0.02
_FAILED_USE_COMPETENCE_BOOST = 0.03
_UNUSED_WEIGHT_RECOVERY = 0.03
_UNUSED_COMPETENCE_RECOVERY = 0.01
_MIN_WEIGHT = 0.2
_MAX_WEIGHT = 1.9
_MIN_COMPETENCE = 0.15
_MAX_COMPETENCE = 0.98

_COUNTERPLAY_TONES = {
	"aggression_feeder": "baiting",
	"forensic_countermeasures": "sterile",
	"rapport_resistant": "distant",
}


def plan_case_mo(state: "NemesisState", rng: Rng) -> "NemesisCasePlan":
	from noir.nemesis.state import NemesisCasePlan, NemesisComponentType

	_decay_cooldowns(state)

	component_values: dict[str, str] = {}
	degraded_execution = False
	for component_type in NemesisComponentType:
		selected, degraded = _select_component(state, component_type.value, rng)
		if selected is None:
			continue
		component_values[component_type.value] = selected.value
		degraded_execution = degraded_execution or degraded

	visibility = min(state.escalation_cap, 1 + state.exposure // 2)
	return NemesisCasePlan(
		is_nemesis_case=True,
		method_category=component_values.get(NemesisComponentType.METHOD.value),
		visibility=visibility,
		degraded_execution=degraded_execution,
		taunt_style=_resolve_taunt_style(state, visibility, degraded_execution, rng),
		component_values=component_values,
	)


def apply_case_feedback(
	state: "NemesisState",
	visibility: int,
	arrest_result: str,
	selected_components: dict[str, str],
	compromised_components: dict[str, str],
	rng: Rng,
) -> list[str]:
	notes: list[str] = []
	_adjust_exposure(state, visibility, arrest_result)
	_evolve_components(state, selected_components, arrest_result, visibility)

	for component_type, value in compromised_components.items():
		component = _find_component(state, component_type, value)
		if component is None and component_type == "method":
			component = _highest_weight_component(state, component_type)
		if component is None:
			continue
		_mark_compromised(component)
		label = "method" if component_type == "method" else component_type.replace("_", " ")
		notes.append(f"Pattern file notes a compromised {label}.")

	state.profile.failure_echo = _resolve_failure_echo(state, arrest_result, visibility, rng)
	return notes


def _decay_cooldowns(state: "NemesisState") -> None:
	for component in state.mo_components:
		if component.avoid_cooldown > 0:
			component.avoid_cooldown -= 1


def _select_component(
	state: "NemesisState", component_type: str, rng: Rng
) -> tuple["NemesisComponent | None", bool]:
	candidates = [
		component
		for component in state.mo_components
		if component.component_type.value == component_type
	]
	if not candidates:
		return None, False

	weighted_candidates: list[tuple["NemesisComponent", float]] = []
	for component in candidates:
		weight = max(_MIN_WEIGHT, component.weight)
		if component.compromised:
			if component.avoid_cooldown > 0:
				weight *= _COOLDOWN_WEIGHT_FACTOR
			else:
				weight *= _COMPROMISED_WEIGHT_FACTOR
		weight *= 0.75 + (component.competence * 0.5)
		weighted_candidates.append((component, weight))

	selected = rng.weighted_choice(weighted_candidates)
	degraded_execution = bool(selected.compromised and selected.avoid_cooldown > 0)
	for component in candidates:
		if component.compromised and component.avoid_cooldown == 0:
			component.avoid_cooldown = _ADAPT_COOLDOWN
	return selected, degraded_execution


def _evolve_components(
	state: "NemesisState",
	selected_components: dict[str, str],
	arrest_result: str,
	visibility: int,
) -> None:
	for component in state.mo_components:
		selected_value = selected_components.get(component.component_type.value)
		if selected_value == component.value:
			_reinforce_component(component, arrest_result, visibility)
		else:
			_recover_component(component)


def _reinforce_component(
	component: "NemesisComponent", arrest_result: str, visibility: int
) -> None:
	weight_boost = _USE_WEIGHT_BOOST
	competence_boost = _USE_COMPETENCE_BOOST
	if arrest_result == "failed":
		weight_boost = _FAILED_USE_WEIGHT_BOOST
		competence_boost = _FAILED_USE_COMPETENCE_BOOST
	if component.compromised and component.avoid_cooldown > 0:
		competence_boost = min(competence_boost, 0.01)
	if visibility >= 3:
		weight_boost = max(0.0, weight_boost - 0.01)

	component.weight = _clamp(component.weight + weight_boost, _MIN_WEIGHT, _MAX_WEIGHT)
	component.competence = _clamp(
		component.competence + competence_boost,
		_MIN_COMPETENCE,
		_MAX_COMPETENCE,
	)


def _recover_component(component: "NemesisComponent") -> None:
	if component.compromised:
		return
	if component.weight < 1.0:
		component.weight = _clamp(
			component.weight + _UNUSED_WEIGHT_RECOVERY,
			_MIN_WEIGHT,
			_MAX_WEIGHT,
		)
	elif component.weight > 1.0:
		component.weight = _clamp(
			component.weight - _UNUSED_WEIGHT_RECOVERY,
			_MIN_WEIGHT,
			_MAX_WEIGHT,
		)
	if component.competence < 0.55:
		component.competence = _clamp(
			component.competence + _UNUSED_COMPETENCE_RECOVERY,
			_MIN_COMPETENCE,
			_MAX_COMPETENCE,
		)


def _mark_compromised(component: "NemesisComponent") -> None:
	component.compromised = True
	component.avoid_cooldown = 0
	component.weight = _clamp(
		component.weight * _COMPROMISE_WEIGHT_PENALTY,
		_MIN_WEIGHT,
		_MAX_WEIGHT,
	)
	component.competence = _clamp(
		component.competence - _COMPROMISE_COMPETENCE_PENALTY,
		_MIN_COMPETENCE,
		_MAX_COMPETENCE,
	)


def _adjust_exposure(state: "NemesisState", visibility: int, arrest_result: str) -> None:
	current = state.exposure
	delta = max(0, visibility - 1)
	if arrest_result == "failed":
		current += max(1, delta)
	elif arrest_result == "partial":
		current += delta
	elif visibility <= 1 and current > state.exposure_baseline:
		current -= 1
	else:
		current += delta

	state.exposure = max(state.exposure_baseline, current)
	if state.exposure > state.exposure_baseline:
		state.exposure_baseline = max(state.exposure_baseline, state.exposure - 1)


def _resolve_taunt_style(
	state: "NemesisState", visibility: int, degraded_execution: bool, rng: Rng
) -> str | None:
	options: list[str] = []
	counter_tone = _counterplay_tone(state)
	if counter_tone:
		options.append(counter_tone)
	if state.profile.failure_echo:
		options.append(state.profile.failure_echo)
	if degraded_execution:
		options.append("frayed")
	if visibility >= state.escalation_cap:
		options.append("brazen")
	elif state.exposure > state.exposure_baseline:
		options.append("watchful")

	unique_options = _unique(options)
	if not unique_options:
		return None
	if len(unique_options) == 1:
		return unique_options[0]
	return rng.choice(unique_options)


def _resolve_failure_echo(
	state: "NemesisState", arrest_result: str, visibility: int, rng: Rng
) -> str | None:
	counter_tone = _counterplay_tone(state)
	if arrest_result == "failed":
		if counter_tone:
			return counter_tone
		return rng.choice(["irritated", "defensive", "taunting", "quiet"])
	if arrest_result == "partial":
		return counter_tone or state.profile.failure_echo or "watchful"
	if visibility <= 1 and state.exposure == state.exposure_baseline:
		return "quiet"
	return counter_tone or state.profile.failure_echo


def _counterplay_tone(state: "NemesisState") -> str | None:
	for trait in state.profile.counterplay_traits:
		tone = _COUNTERPLAY_TONES.get(trait)
		if tone:
			return tone
	return None


def _find_component(
	state: "NemesisState", component_type: str, value: str
) -> "NemesisComponent | None":
	if value:
		for component in state.mo_components:
			if component.component_type.value == component_type and component.value == value:
				return component
	return None


def _highest_weight_component(
	state: "NemesisState", component_type: str
) -> "NemesisComponent | None":
	candidates = [
		component
		for component in state.mo_components
		if component.component_type.value == component_type
	]
	if not candidates:
		return None
	candidates.sort(key=lambda component: component.weight, reverse=True)
	return candidates[0]


def _clamp(value: float, minimum: float, maximum: float) -> float:
	return round(max(minimum, min(maximum, value)), 2)


def _unique(values: list[str]) -> list[str]:
	seen: set[str] = set()
	ordered: list[str] = []
	for value in values:
		if value in seen:
			continue
		seen.add(value)
		ordered.append(value)
	return ordered
