from uuid import uuid4

from noir.deduction.board import ClaimType, DeductionBoard, Hypothesis, ReasoningStep
from noir.deduction.scoring import auto_build_reasoning_steps, support_for_claims, suspect_candidate_ids
from noir.deduction.validation import validate_hypothesis
from noir.domain.enums import ConfidenceBand, EvidenceType, RoleTag
from noir.domain.models import Person
from noir.investigation.results import InvestigationState
from noir.presentation.evidence import PresentationCase, WitnessStatement
from noir.profiling.profile import OffenderProfile, ProfileDrive, ProfileMobility, ProfileOrganization
from noir.truth.graph import TruthState


def test_motive_and_behavior_claims_gain_support_from_profile_alignment() -> None:
    suspect_id = uuid4()
    evidence_id = uuid4()
    location_id = uuid4()
    presentation = PresentationCase(
        case_id="case_support",
        seed=1,
        evidence=[
            WitnessStatement(
                id=evidence_id,
                evidence_type=EvidenceType.TESTIMONIAL,
                summary="Witness statement",
                source="Interview",
                time_collected=1,
                confidence=ConfidenceBand.MEDIUM,
                witness_id=uuid4(),
                statement="I heard a disturbance near the building.",
                reported_time_window=(20, 21),
                location_id=location_id,
                observed_person_ids=[suspect_id],
                uncertainty_hooks=[],
            )
        ],
    )
    truth = TruthState(case_id="case_support", seed=1)
    truth.case_meta["motive_category"] = "money"
    state = InvestigationState()
    state.profile = OffenderProfile(
        organization=ProfileOrganization.ORGANIZED,
        drive=ProfileDrive.MISSION,
        mobility=ProfileMobility.MARAUDER,
        evidence_ids=[evidence_id],
    )

    support = support_for_claims(
        presentation,
        [evidence_id],
        suspect_id,
        [ClaimType.MOTIVE, ClaimType.BEHAVIOR],
        truth=truth,
        state=state,
    )

    assert "Working profile aligns with the case motive." in support.supports
    assert "Working profile aligns with the behavior suggested by the evidence." in support.supports


def test_validate_hypothesis_fails_when_reasoning_chain_uses_wrong_evidence() -> None:
    suspect_id = uuid4()
    wrong_evidence_id = uuid4()
    right_evidence_id = uuid4()
    location_id = uuid4()
    presentation = PresentationCase(
        case_id="case_reasoning_fail",
        seed=1,
        evidence=[
            WitnessStatement(
                id=right_evidence_id,
                evidence_type=EvidenceType.TESTIMONIAL,
                summary="Witness statement",
                source="Interview",
                time_collected=1,
                confidence=ConfidenceBand.MEDIUM,
                witness_id=uuid4(),
                statement="I saw the suspect near the scene.",
                reported_time_window=(20, 21),
                location_id=location_id,
                observed_person_ids=[suspect_id],
                uncertainty_hooks=[],
            ),
            WitnessStatement(
                id=wrong_evidence_id,
                evidence_type=EvidenceType.TESTIMONIAL,
                summary="Witness statement (other)",
                source="Interview",
                time_collected=1,
                confidence=ConfidenceBand.MEDIUM,
                witness_id=uuid4(),
                statement="I heard noise but saw no one clearly.",
                reported_time_window=(20, 21),
                location_id=location_id,
                observed_person_ids=[],
                uncertainty_hooks=[],
            ),
        ],
    )
    truth = TruthState(case_id="case_reasoning_fail", seed=1)
    truth.add_person(Person(id=suspect_id, name="Mara Flint", role_tags=[RoleTag.OFFENDER, RoleTag.SUSPECT]))
    state = InvestigationState()
    board = DeductionBoard(
        hypothesis=Hypothesis(
            suspect_id=suspect_id,
            claims=[ClaimType.PRESENCE],
            evidence_ids=[right_evidence_id, wrong_evidence_id],
            reasoning_steps=[
                ReasoningStep(
                    claim=ClaimType.PRESENCE,
                    evidence_id=wrong_evidence_id,
                    note="Use Witness statement (other) to place the suspect near the scene.",
                )
            ],
        )
    )

    validation = validate_hypothesis(truth, board, presentation, state)

    assert validation.tier.value == "failed"
    assert any("does not actually place the suspect" in line.lower() for line in validation.missing)


def test_auto_reasoning_steps_cover_supported_profile_claims() -> None:
    suspect_id = uuid4()
    evidence_id = uuid4()
    location_id = uuid4()
    presentation = PresentationCase(
        case_id="case_reasoning_auto",
        seed=1,
        evidence=[
            WitnessStatement(
                id=evidence_id,
                evidence_type=EvidenceType.TESTIMONIAL,
                summary="Witness statement",
                source="Interview",
                time_collected=1,
                confidence=ConfidenceBand.MEDIUM,
                witness_id=uuid4(),
                statement="I heard a disturbance near the building.",
                reported_time_window=(20, 21),
                location_id=location_id,
                observed_person_ids=[suspect_id],
                uncertainty_hooks=[],
            )
        ],
    )
    truth = TruthState(case_id="case_reasoning_auto", seed=1)
    truth.case_meta["motive_category"] = "money"
    state = InvestigationState()
    state.profile = OffenderProfile(
        organization=ProfileOrganization.ORGANIZED,
        drive=ProfileDrive.MISSION,
        mobility=ProfileMobility.MARAUDER,
        evidence_ids=[evidence_id],
    )

    steps = auto_build_reasoning_steps(
        presentation,
        [evidence_id],
        suspect_id,
        [ClaimType.MOTIVE, ClaimType.BEHAVIOR],
        truth=truth,
        state=state,
    )

    assert {step.claim for step in steps} == {ClaimType.MOTIVE, ClaimType.BEHAVIOR}


def test_suspect_candidates_include_red_herring_and_exclude_victim() -> None:
    truth = TruthState(case_id="case_candidates", seed=1)
    victim = Person(name="Victim", role_tags=[RoleTag.VICTIM])
    offender = Person(name="Offender", role_tags=[RoleTag.OFFENDER, RoleTag.SUSPECT])
    witness = Person(name="Witness", role_tags=[RoleTag.WITNESS])
    truth.add_person(victim)
    truth.add_person(offender)
    truth.add_person(witness)
    truth.case_meta["red_herring_suspect_id"] = str(witness.id)
    presentation = PresentationCase(case_id="case_candidates", seed=1, evidence=[])

    candidates = suspect_candidate_ids(truth, presentation, [])

    assert victim.id not in candidates
    assert offender.id in candidates
    assert witness.id in candidates