"""Runtime nemesis interference hooks for live case actions."""

from __future__ import annotations

from typing import Any

from noir.domain.enums import ConfidenceBand
from noir.investigation.costs import ActionType, PRESSURE_LIMIT, clamp
from noir.investigation.results import ActionResult, InvestigationState
from noir.presentation.evidence import CCTVReport, ForensicObservation, ForensicsResult, WitnessStatement


_RUNTIME_MARK = "nemesis:runtime_interference"
_ELIGIBLE_ACTIONS = {
	ActionType.VISIT_SCENE,
	ActionType.INTERVIEW,
	ActionType.REQUEST_CCTV,
	ActionType.SUBMIT_FORENSICS,
}


def apply_nemesis_runtime_interference(
	case_facts: dict[str, Any],
	state: InvestigationState,
	result: ActionResult,
) -> list[str]:
	if not case_facts.get("nemesis_case"):
		return []
	if result.action not in _ELIGIBLE_ACTIONS:
		return []
	if _RUNTIME_MARK in state.autonomy_marks:
		return []

	components = dict(case_facts.get("nemesis_components") or {})
	notes = _apply_action_interference(components, state, result)
	if not notes:
		return []
	state.autonomy_marks.add(_RUNTIME_MARK)
	result.notes.extend(notes)
	return notes


def _apply_action_interference(
	components: dict[str, str],
	state: InvestigationState,
	result: ActionResult,
) -> list[str]:
	if result.action == ActionType.VISIT_SCENE:
		_raise_pressure(state)
		target = next(
			(
				item
				for item in result.revealed
				if isinstance(item, (ForensicObservation, ForensicsResult))
			),
			None,
		)
		_downgrade_item(target)
		cleanup = components.get("cleanup", "none")
		if cleanup == "wipe":
			return ["Nemesis interference: the scene looks lightly scrubbed before you can lock it down."]
		if cleanup == "arson":
			return ["Nemesis interference: heat damage has already eaten one promising trace."]
		return ["Nemesis interference: the scene has been worked over just enough to blur one good read."]

	if result.action == ActionType.REQUEST_CCTV:
		_raise_pressure(state)
		target = next((item for item in result.revealed if isinstance(item, CCTVReport)), None)
		_downgrade_item(target)
		exit_style = components.get("exit", "walkaway")
		if exit_style == "misdirection":
			return ["Nemesis interference: the cleanest camera angle nudges you toward the wrong movement pattern."]
		if exit_style == "vehicle":
			return ["Nemesis interference: the useful camera window is partly swallowed by traffic and glare."]
		return ["Nemesis interference: the camera coverage is thinner than it should be when it matters."]

	if result.action == ActionType.INTERVIEW:
		state.cooperation = clamp(state.cooperation - 0.1, 0.0, 1.0)
		target = next((item for item in result.revealed if isinstance(item, WitnessStatement)), None)
		if isinstance(target, WitnessStatement):
			_downgrade_item(target)
			if "Witness seems spooked before the interview starts." not in target.uncertainty_hooks:
				target.uncertainty_hooks.append(
					"Witness seems spooked before the interview starts."
				)
		control = components.get("control", "surprise")
		if control == "intimidation":
			return ["Nemesis interference: someone got to the witness first and left them visibly rattled."]
		if control == "restraints":
			return ["Nemesis interference: the witness keeps focusing on fear instead of detail."]
		return ["Nemesis interference: the witness arrives off-balance and less reliable than they were hours ago."]

	if result.action == ActionType.SUBMIT_FORENSICS:
		_raise_pressure(state)
		target = next(
			(
				item
				for item in result.revealed
				if isinstance(item, (ForensicObservation, ForensicsResult))
			),
			None,
		)
		_downgrade_item(target)
		cleanup = components.get("cleanup", "none")
		if cleanup in {"wipe", "staging"}:
			return ["Nemesis interference: the lab flags one return as compromised by deliberate cleanup."]
		return ["Nemesis interference: the lab gets a thinner sample than the scene should have yielded."]

	return []


def _raise_pressure(state: InvestigationState) -> None:
	state.pressure = int(clamp(state.pressure + 1, 0, PRESSURE_LIMIT))


def _downgrade_item(item) -> None:
	if item is None or not hasattr(item, "confidence"):
		return
	if item.confidence == ConfidenceBand.STRONG:
		item.confidence = ConfidenceBand.MEDIUM
	elif item.confidence == ConfidenceBand.MEDIUM:
		item.confidence = ConfidenceBand.WEAK
