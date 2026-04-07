from uuid import uuid4

from noir.deduction.board import ClaimType
from noir.deduction.scoring import support_for_claims
from noir.investigation.results import InvestigationState
from noir.presentation.evidence import PresentationCase, WitnessStatement
from noir.profiling.profile import OffenderProfile, ProfileDrive, ProfileMobility, ProfileOrganization
from noir.truth.graph import TruthState
from noir.domain.enums import ConfidenceBand, EvidenceType


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