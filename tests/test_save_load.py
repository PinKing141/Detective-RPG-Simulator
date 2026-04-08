from uuid import uuid4

from noir.deduction.board import ClaimType, Hypothesis, ReasoningStep
from noir.domain.enums import RoleTag
from noir.domain.models import Person
from noir.domain.enums import ConfidenceBand, EvidenceType
from noir.investigation.interviews import BaselineProfile, InterviewPhase, InterviewState
from noir.investigation.leads import Lead, LeadStatus, NeighborLead
from noir.investigation.results import InvestigationState, LocationState
from noir.locations.profiles import ScenePOI
from noir.persistence.save_load import (
    delete_save,
    has_save,
    load_investigation,
    restore_saved_hypothesis,
    save_investigation,
)
from noir.presentation.evidence import PresentationCase, WitnessStatement
from noir.profiling.profile import OffenderProfile, ProfileDrive, ProfileMobility, ProfileOrganization
from noir.truth.graph import TruthState


def test_save_load_round_trip_preserves_investigation_state(tmp_path) -> None:
    case_id = "case_roundtrip"
    location_id = uuid4()
    witness_id = uuid4()
    evidence_id = uuid4()
    poi = ScenePOI(
        poi_id="primary|room:door:0",
        label="Door",
        zone_id="room",
        zone_label="Room",
        description="The door sits slightly ajar.",
        tags=["entry"],
    )
    state = InvestigationState(
        time=3,
        pressure=1,
        trust=4,
        cooperation=0.8,
        autonomy_marks={"followed_instinct"},
        style_counts={"social": 2},
        location_states={
            str(location_id): LocationState(
                location_id=location_id,
                name="Riverside Apartment",
                district="riverside",
                scene_pois=[poi],
                visited_poi_ids={poi.poi_id},
                body_poi_id=poi.poi_id,
                neighbor_leads=[NeighborLead("slot:1", "Neighbor witness", 0.55, {"neighbor": 1.0})],
            )
        },
        active_location_id=location_id,
        leads=[Lead("testimonial", "Witness lead", EvidenceType.TESTIMONIAL, 2, "Interview witness", LeadStatus.ACTIVE)],
        scene_pois=[poi],
        visited_poi_ids={poi.poi_id},
        body_poi_id=poi.poi_id,
        interviews={
            str(witness_id): InterviewState(
                phase=InterviewPhase.THEME,
                rapport=0.6,
                resistance=0.4,
                fatigue=0.2,
                baseline_profile=BaselineProfile(8.0, 0.12, "past"),
                last_claims=["presence", "motive"],
                motive_to_lie=True,
                contradiction_emitted=True,
                dialog_node_id="THEME_CIRCUMSTANCE",
                approach_counts={"baseline": 1, "theme:circumstance": 2},
                approach_history=["baseline", "theme:circumstance", "theme:circumstance"],
                prompt_history=["theme:circumstance:Push motive"],
            )
        },
        neighbor_leads=[NeighborLead("slot:2", "Hall witness", 0.35, {"resident": 0.8})],
        analyst_notes=["Camera coverage appears usable for the scene window."],
        warrant_grants={"search"},
    )
    state.knowledge.known_evidence.append(evidence_id)
    state.profile = OffenderProfile(
        organization=ProfileOrganization.ORGANIZED,
        drive=ProfileDrive.MISSION,
        mobility=ProfileMobility.MARAUDER,
        evidence_ids=[evidence_id],
    )
    presentation = PresentationCase(
        case_id=case_id,
        seed=17,
        evidence=[
            WitnessStatement(
                id=evidence_id,
                evidence_type=EvidenceType.TESTIMONIAL,
                summary="Witness statement",
                source="Interview",
                time_collected=3,
                confidence=ConfidenceBand.MEDIUM,
                witness_id=witness_id,
                statement="I heard a disturbance near the apartment.",
                reported_time_window=(20, 21),
                location_id=location_id,
                observed_person_ids=[],
                uncertainty_hooks=["Statement feels rehearsed."],
            )
        ],
    )
    hypothesis = Hypothesis(
        suspect_id=witness_id,
        claims=[ClaimType.PRESENCE],
        evidence_ids=[evidence_id],
        reasoning_steps=[
            ReasoningStep(
                claim=ClaimType.PRESENCE,
                evidence_id=evidence_id,
                note="Witness places the suspect near the apartment in the scene window.",
            )
        ],
    )

    save_investigation(case_id, 17, state, presentation, hypothesis=hypothesis, path=tmp_path)

    loaded = load_investigation(case_id, path=tmp_path)

    assert loaded is not None
    seed, loaded_state, loaded_presentation, loaded_hypothesis = loaded
    assert seed == 17
    assert loaded_state.active_location_id == location_id
    assert loaded_state.profile is not None
    assert loaded_state.profile.drive == ProfileDrive.MISSION
    assert loaded_state.interviews[str(witness_id)].dialog_node_id == "THEME_CIRCUMSTANCE"
    assert loaded_state.interviews[str(witness_id)].approach_counts["theme:circumstance"] == 2
    assert loaded_state.interviews[str(witness_id)].prompt_history == ["theme:circumstance:Push motive"]
    assert loaded_presentation.evidence[0].summary == "Witness statement"
    assert loaded_hypothesis is not None
    assert loaded_hypothesis.suspect_id == witness_id
    assert loaded_hypothesis.claims == [ClaimType.PRESENCE]
    assert loaded_hypothesis.evidence_ids == [evidence_id]
    assert loaded_hypothesis.reasoning_steps == hypothesis.reasoning_steps


def test_has_and_delete_save_manage_lifecycle(tmp_path) -> None:
    state = InvestigationState()
    presentation = PresentationCase(case_id="case_lifecycle", seed=5, evidence=[])

    assert has_save("case_lifecycle", path=tmp_path) is False
    save_investigation("case_lifecycle", 5, state, presentation, path=tmp_path)
    assert has_save("case_lifecycle", path=tmp_path) is True
    assert delete_save("case_lifecycle", path=tmp_path) is True
    assert has_save("case_lifecycle", path=tmp_path) is False


def test_restore_saved_hypothesis_migrates_legacy_reasoning_steps() -> None:
    suspect_id = uuid4()
    evidence_id = uuid4()
    location_id = uuid4()
    state = InvestigationState()
    state.knowledge.known_evidence.append(evidence_id)
    presentation = PresentationCase(
        case_id="case_restore_migration",
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
                statement="I saw the suspect near the scene.",
                reported_time_window=(20, 21),
                location_id=location_id,
                observed_person_ids=[suspect_id],
                uncertainty_hooks=[],
            )
        ],
    )
    hypothesis = Hypothesis(
        suspect_id=suspect_id,
        claims=[ClaimType.PRESENCE, ClaimType.OPPORTUNITY],
        evidence_ids=[evidence_id],
        reasoning_steps=[
            ReasoningStep(
                claim=ClaimType.PRESENCE,
                evidence_id=evidence_id,
                note="Use witness statement to place the suspect near the scene.",
            )
        ],
    )

    restored, note = restore_saved_hypothesis(hypothesis, presentation, state)

    assert restored is not None
    assert restored.claims == [ClaimType.PRESENCE, ClaimType.OPPORTUNITY]
    assert {step.claim for step in restored.reasoning_steps} == {ClaimType.PRESENCE, ClaimType.OPPORTUNITY}
    assert note is not None
    assert "migrated" in note.lower()


def test_restore_saved_hypothesis_clears_unmigratable_state() -> None:
    suspect_id = uuid4()
    evidence_id = uuid4()
    location_id = uuid4()
    state = InvestigationState()
    state.knowledge.known_evidence.append(evidence_id)
    presentation = PresentationCase(
        case_id="case_restore_clear",
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
                statement="I heard something but could not place anyone.",
                reported_time_window=(20, 21),
                location_id=location_id,
                observed_person_ids=[],
                uncertainty_hooks=[],
            )
        ],
    )
    truth = TruthState(case_id="case_restore_clear", seed=1)
    truth.case_meta["motive_category"] = "money"
    truth.add_person(Person(id=suspect_id, name="Mara Flint", role_tags=[RoleTag.OFFENDER, RoleTag.SUSPECT]))
    hypothesis = Hypothesis(
        suspect_id=suspect_id,
        claims=[ClaimType.MOTIVE],
        evidence_ids=[evidence_id],
        reasoning_steps=[],
    )

    restored, note = restore_saved_hypothesis(hypothesis, presentation, state, truth=truth)

    assert restored is None
    assert note is not None
    assert "cleared" in note.lower()