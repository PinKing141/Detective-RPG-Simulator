from __future__ import annotations

from noir.domain.enums import RoleTag
from noir.investigation.costs import ActionType
from noir.investigation.guidance import investigation_guidance_lines
from noir.investigation.results import ActionOutcome, InvestigationState
from noir.investigation.dialog_graph import resolve_dialog_role_key


def dialog_relationship_profile(truth, person_id) -> tuple[str | None, str | None]:
    victim = next(
        (candidate for candidate in truth.people.values() if RoleTag.VICTIM in candidate.role_tags),
        None,
    )
    offender = next(
        (candidate for candidate in truth.people.values() if RoleTag.OFFENDER in candidate.role_tags),
        None,
    )
    relations = []
    for related_person in (victim, offender):
        if related_person is None:
            continue
        relation = truth.relationship_between(person_id, related_person.id)
        if relation:
            relations.append(relation)
    for relation in relations:
        if str(relation.get("closeness", "") or "").lower() == "intimate":
            return str(relation.get("closeness", "") or ""), str(
                relation.get("relationship_type", "") or ""
            )
    if relations:
        relation = relations[0]
        return str(relation.get("closeness", "") or ""), str(
            relation.get("relationship_type", "") or ""
        )
    return None, None


def dialog_role_key_for_witness(truth, state: InvestigationState, witness_id) -> str:
    person = truth.people.get(witness_id)
    if person is None:
        return "default"
    interview_state = state.interviews.get(str(witness_id))
    relationship_closeness, relationship_type = dialog_relationship_profile(
        truth, witness_id
    )
    return resolve_dialog_role_key(
        person.role_tags,
        person.traits if isinstance(person.traits, dict) else None,
        motive_to_lie=bool(interview_state and interview_state.motive_to_lie),
        relationship_closeness=relationship_closeness,
        relationship_type=relationship_type,
    )


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