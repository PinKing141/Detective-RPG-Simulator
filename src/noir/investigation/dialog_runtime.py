from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from noir.domain.enums import EventKind, RoleTag
from noir.investigation.dialog_graph import DialogChoice, DialogGraph, DialogNode, load_interview_graph, resolve_dialog_role_key
from noir.investigation.results import InvestigationState
from noir.presentation.evidence import CCTVReport, EvidenceItem, PresentationCase, WitnessStatement
from noir.truth.graph import TruthState


@dataclass(frozen=True)
class DialogPromptOption:
    raw_index: int
    choice: DialogChoice


def dialog_relationship_profile(truth: TruthState, person_id: UUID) -> tuple[str | None, str | None]:
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


def dialog_role_key_for_witness(truth: TruthState, state: InvestigationState, witness_id: UUID) -> str:
    person = truth.people.get(witness_id)
    if person is None:
        return "default"
    interview_state = state.interviews.get(str(witness_id))
    relationship_closeness, relationship_type = dialog_relationship_profile(truth, witness_id)
    return resolve_dialog_role_key(
        person.role_tags,
        person.traits if isinstance(person.traits, dict) else None,
        motive_to_lie=bool(interview_state and interview_state.motive_to_lie),
        relationship_closeness=relationship_closeness,
        relationship_type=relationship_type,
    )


def known_confrontation_evidence(
    truth: TruthState,
    presentation: PresentationCase,
    state: InvestigationState,
    person_id: UUID,
) -> list[EvidenceItem]:
    person = truth.people.get(person_id)
    if person is None:
        return []
    if RoleTag.OFFENDER not in person.role_tags and RoleTag.SUSPECT not in person.role_tags:
        return []
    interview_state = state.interviews.get(str(person_id))
    if interview_state and interview_state.confession_recorded:
        return []
    kill_events = [event for event in truth.events.values() if event.kind == EventKind.KILL]
    scene_location_id = None
    if kill_events:
        scene_location_id = sorted(kill_events, key=lambda event: event.timestamp)[0].location_id
    known_ids = set(state.knowledge.known_evidence)
    contradictions: list[EvidenceItem] = []
    for item in presentation.evidence:
        if item.id not in known_ids:
            continue
        if isinstance(item, WitnessStatement):
            if item.witness_id == person_id or person_id not in item.observed_person_ids:
                continue
            if scene_location_id is not None and item.location_id != scene_location_id:
                continue
        elif isinstance(item, CCTVReport):
            if person_id not in item.observed_person_ids:
                continue
            if scene_location_id is not None and item.location_id != scene_location_id:
                continue
        else:
            continue
        contradictions.append(item)
    return contradictions


def confrontation_prompt_unlocked(
    truth: TruthState,
    presentation: PresentationCase,
    state: InvestigationState,
    person_id: UUID,
) -> bool:
    return bool(known_confrontation_evidence(truth, presentation, state, person_id))


def visible_dialog_prompt_options(
    truth: TruthState,
    presentation: PresentationCase,
    state: InvestigationState,
    person_id: UUID,
) -> tuple[DialogGraph | None, DialogNode | None, list[DialogPromptOption]]:
    role_key = dialog_role_key_for_witness(truth, state, person_id)
    graph = load_interview_graph(role_key)
    if graph is None:
        return None, None, []
    interview_state = state.interviews.get(str(person_id))
    node_id = graph.root_node_id
    if interview_state and interview_state.dialog_node_id:
        node_id = interview_state.dialog_node_id
    if not graph.has_node(node_id):
        node_id = graph.root_node_id
    node = graph.node(node_id)
    if not node.choices:
        node = graph.node(graph.root_node_id)
    unlocked = confrontation_prompt_unlocked(truth, presentation, state, person_id)
    options = [
        DialogPromptOption(raw_index=raw_index, choice=choice)
        for raw_index, choice in enumerate(node.choices)
        if unlocked or "contradiction" not in choice.tags
    ]
    if not options and node.node_id != graph.root_node_id:
        node = graph.node(graph.root_node_id)
        options = [
            DialogPromptOption(raw_index=raw_index, choice=choice)
            for raw_index, choice in enumerate(node.choices)
            if unlocked or "contradiction" not in choice.tags
        ]
    return graph, node, options