from __future__ import annotations

from noir.domain.enums import RoleTag
from noir.investigation.costs import ActionType
from noir.investigation.dialog_runtime import dialog_relationship_profile, dialog_role_key_for_witness
from noir.investigation.guidance import investigation_guidance_lines
from noir.investigation.results import ActionOutcome, InvestigationState


def maybe_print_investigation_guidance(
    result,
    truth,
    presentation,
    state: InvestigationState,
    board,
    *,
    emit=print,
) -> None:
    if result.outcome != ActionOutcome.SUCCESS:
        return
    if board.hypothesis is not None:
        return
    if result.action not in {
        ActionType.INTERVIEW,
        ActionType.FOLLOW_NEIGHBOR,
        ActionType.REQUEST_CCTV,
        ActionType.SUBMIT_FORENSICS,
        ActionType.VISIT_SCENE,
    }:
        return
    for line in investigation_guidance_lines(truth, presentation, state):
        emit(f"Guidance: {line}")