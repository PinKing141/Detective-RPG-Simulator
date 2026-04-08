from noir.cases.truth_generator import generate_case
from noir.deduction.board import ClaimType, DeductionBoard
from noir.deduction.scoring import auto_build_reasoning_steps, recommended_hypothesis_evidence_ids, support_for_claims
from noir.deduction.validation import validate_hypothesis
from noir.domain.enums import RoleTag
from noir.investigation.actions import arrest, interview, request_cctv, set_hypothesis, submit_forensics
from noir.investigation.leads import build_leads
from noir.investigation.outcomes import resolve_case_outcome
from noir.investigation.results import ActionOutcome, InvestigationState
from noir.presentation.projector import project_case
from noir.util.rng import Rng


def _supported_claims(presentation, evidence_ids, suspect_id, *, truth, state) -> list[ClaimType]:
    claims: list[ClaimType] = []
    for claim in ClaimType:
        support = support_for_claims(
            presentation,
            evidence_ids,
            suspect_id,
            [claim],
            truth=truth,
            state=state,
        )
        if support.supports:
            claims.append(claim)
    return claims


def test_careful_single_case_route_is_playable_end_to_end() -> None:
    clean_results = 0
    validation_tiers: dict[int, str] = {}
    for seed in (19, 37, 41, 73):
        rng = Rng(seed)
        truth, case_facts = generate_case(rng, case_id=f"case_loop_{seed}")
        presentation = project_case(truth, rng.fork("projection"))
        state = InvestigationState()
        state.leads = build_leads(presentation, start_time=state.time)
        board = DeductionBoard()

        witnesses = [
            person for person in truth.people.values() if RoleTag.WITNESS in person.role_tags
        ]
        suspect = next(
            (person for person in truth.people.values() if RoleTag.OFFENDER in person.role_tags),
            None,
        )
        assert witnesses
        assert suspect is not None

        location_id = case_facts["crime_scene_id"]
        item_id = case_facts["weapon_id"]

        interview(truth, presentation, state, witnesses[0].id, location_id)
        request_cctv(truth, presentation, state, location_id)
        submit_forensics(truth, presentation, state, location_id, item_id=item_id)
        for witness in witnesses[1:]:
            interview(truth, presentation, state, witness.id, location_id)

        board.sync_from_state(state)
        candidate_ids = list(board.known_evidence_ids)
        claims = _supported_claims(
            presentation,
            candidate_ids,
            suspect.id,
            truth=truth,
            state=state,
        )[:3]
        assert claims

        evidence_ids = recommended_hypothesis_evidence_ids(
            presentation,
            candidate_ids,
            suspect.id,
            claims,
            truth=truth,
            state=state,
            limit=3,
        )
        assert evidence_ids

        reasoning_steps = auto_build_reasoning_steps(
            presentation,
            evidence_ids,
            suspect.id,
            claims,
            truth=truth,
            state=state,
        )
        result = set_hypothesis(
            state,
            board,
            suspect.id,
            claims,
            evidence_ids,
            reasoning_steps,
        )

        assert result.outcome == ActionOutcome.SUCCESS
        assert board.hypothesis is not None

        validation = validate_hypothesis(truth, board, presentation, state)
        assert validation.probable_cause is True
        assert validation.is_correct_suspect is True
        validation_tiers[seed] = validation.tier.value
        if validation.tier.value == "clean":
            clean_results += 1

        arrest_result = arrest(
            truth,
            presentation,
            state,
            suspect.id,
            location_id,
            has_hypothesis=True,
            board=board,
        )
        assert arrest_result.outcome == ActionOutcome.SUCCESS

        outcome = resolve_case_outcome(validation)
        assert outcome.arrest_result.value != "failed"

    assert validation_tiers == {19: "clean", 37: "clean", 41: "clean", 73: "clean"}
    assert clean_results == 4
