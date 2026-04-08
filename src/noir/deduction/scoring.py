"""Evidence support helpers for deduction validation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable
from uuid import UUID

from noir.deduction.board import ClaimType, ReasoningStep
from noir.domain.enums import ConfidenceBand, RoleTag
from noir.profiling.profile import ProfileDrive, ProfileMobility, ProfileOrganization
from noir.presentation.evidence import CCTVReport, EvidenceItem, ForensicsResult, WitnessStatement


@dataclass
class EvidenceSupport:
    supports: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)


def evidence_item_by_id(presentation, evidence_id: UUID) -> EvidenceItem | None:
    return next((item for item in presentation.evidence if item.id == evidence_id), None)


def _known_evidence(presentation, evidence_ids: Iterable[UUID]) -> list[EvidenceItem]:
    id_set = set(evidence_ids)
    return [item for item in presentation.evidence if item.id in id_set]


def _presence_hits(known: list[EvidenceItem], suspect_id: UUID) -> tuple[bool, bool]:
    cctv_hits = [
        item
        for item in known
        if isinstance(item, CCTVReport) and suspect_id in item.observed_person_ids
    ]
    witness_hits = [
        item
        for item in known
        if isinstance(item, WitnessStatement) and suspect_id in item.observed_person_ids
    ]
    return bool(cctv_hits), bool(witness_hits)


def _temporal_status(known: list[EvidenceItem], suspect_id: UUID) -> str:
    windows: list[tuple[int, int]] = []
    suspect_seen = False
    for item in known:
        if isinstance(item, WitnessStatement):
            windows.append(item.reported_time_window)
            if suspect_id in item.observed_person_ids:
                suspect_seen = True
        if isinstance(item, CCTVReport):
            windows.append(item.time_window)
            if suspect_id in item.observed_person_ids:
                suspect_seen = True
    if not windows:
        return "none"
    if not suspect_seen:
        return "no_link"
    start = max(window[0] for window in windows)
    end = min(window[1] for window in windows)
    if start > end:
        return "conflict"
    if (end - start) > 2:
        return "broad"
    return "tight"


def support_for_claims(
    presentation,
    evidence_ids: Iterable[UUID],
    suspect_id: UUID | None,
    claims: Iterable[ClaimType],
    truth=None,
    state=None,
) -> EvidenceSupport:
    support = EvidenceSupport()
    if suspect_id is None:
        support.missing.append("No suspect selected.")
        return support
    known = _known_evidence(presentation, evidence_ids)
    claim_set = set(claims)

    if ClaimType.PRESENCE in claim_set:
        cctv_hit, witness_hit = _presence_hits(known, suspect_id)
        if cctv_hit or witness_hit:
            support.supports.append("Evidence suggests the suspect was near the location.")
        else:
            support.missing.append("No evidence suggests proximity to the location.")

    if ClaimType.OPPORTUNITY in claim_set:
        status = _temporal_status(known, suspect_id)
        if status == "tight":
            support.supports.append("Evidence narrows the opportunity window.")
        elif status == "conflict":
            support.missing.append("Temporal sources conflict; opportunity is unstable.")
        elif status == "broad":
            support.missing.append("Timeline is too broad to close opportunity.")
        elif status == "no_link":
            support.missing.append("No evidence ties the suspect to the opportunity window.")
        else:
            support.missing.append("No evidence constrains an opportunity window.")

    if ClaimType.MOTIVE in claim_set:
        if _motive_supported(truth, state, known):
            support.supports.append("Working profile aligns with the case motive.")
        else:
            support.missing.append("No supported motive read ties the suspect to the victim.")

    if ClaimType.BEHAVIOR in claim_set:
        if _behavior_supported(state, known):
            support.supports.append("Working profile aligns with the behavior suggested by the evidence.")
        else:
            support.missing.append("No supported behavioral read is anchored to the selected evidence.")

    return support


def describe_reasoning_step(
    presentation,
    evidence_id: UUID,
    claim: ClaimType,
) -> str:
    item = evidence_item_by_id(presentation, evidence_id)
    summary = item.summary if item is not None else "selected evidence"
    claim_labels = {
        ClaimType.PRESENCE: "place the suspect near the scene",
        ClaimType.OPPORTUNITY: "argue the suspect had the time window",
        ClaimType.MOTIVE: "argue motive",
        ClaimType.BEHAVIOR: "argue behavior",
    }
    return f"Use {summary} to {claim_labels.get(claim, claim.value)}."


def supports_reasoning_step(
    presentation,
    evidence_id: UUID,
    suspect_id: UUID | None,
    claim: ClaimType,
    *,
    truth=None,
    state=None,
) -> tuple[bool, str]:
    item = evidence_item_by_id(presentation, evidence_id)
    if item is None:
        return False, "Reasoning chain references evidence that is no longer available."
    if suspect_id is None:
        return False, "Reasoning chain has no suspect to evaluate."

    if claim == ClaimType.PRESENCE:
        if isinstance(item, CCTVReport) and suspect_id in item.observed_person_ids:
            return True, "Reasoning chain uses CCTV to place the suspect near the scene."
        if isinstance(item, WitnessStatement) and suspect_id in item.observed_person_ids:
            return True, "Reasoning chain uses testimony to place the suspect near the scene."
        return False, "Reasoning chain does not actually place the suspect near the scene."

    if claim == ClaimType.OPPORTUNITY:
        if isinstance(item, CCTVReport) and suspect_id in item.observed_person_ids:
            return True, "Reasoning chain uses CCTV timing to argue opportunity."
        if isinstance(item, WitnessStatement) and suspect_id in item.observed_person_ids:
            return True, "Reasoning chain uses witness timing to argue opportunity."
        return False, "Reasoning chain does not tie the suspect to the opportunity window."

    if claim == ClaimType.MOTIVE:
        if _motive_supported(truth, state, [item]):
            return True, "Reasoning chain uses profile-backed evidence to argue motive."
        return False, "Reasoning chain does not anchor motive in the selected evidence."

    if claim == ClaimType.BEHAVIOR:
        if _behavior_supported(state, [item]):
            return True, "Reasoning chain uses profile-backed evidence to argue behavior."
        return False, "Reasoning chain does not anchor behavior in the selected evidence."

    return False, "Reasoning chain does not support the selected claim."


def auto_build_reasoning_steps(
    presentation,
    evidence_ids: Iterable[UUID],
    suspect_id: UUID | None,
    claims: Iterable[ClaimType],
    *,
    truth=None,
    state=None,
) -> list[ReasoningStep]:
    steps: list[ReasoningStep] = []
    ordered_claims = list(dict.fromkeys(claims))
    ordered_evidence = list(dict.fromkeys(evidence_ids))
    used_evidence_ids: set[UUID] = set()
    for claim in ordered_claims:
        fallback_evidence_id: UUID | None = None
        for evidence_id in ordered_evidence:
            supported, _ = supports_reasoning_step(
                presentation,
                evidence_id,
                suspect_id,
                claim,
                truth=truth,
                state=state,
            )
            if not supported:
                continue
            if fallback_evidence_id is None:
                fallback_evidence_id = evidence_id
            if evidence_id in used_evidence_ids:
                continue
            steps.append(
                ReasoningStep(
                    claim=claim,
                    evidence_id=evidence_id,
                    note=describe_reasoning_step(presentation, evidence_id, claim),
                )
            )
            used_evidence_ids.add(evidence_id)
            break
        else:
            if fallback_evidence_id is not None:
                steps.append(
                    ReasoningStep(
                        claim=claim,
                        evidence_id=fallback_evidence_id,
                        note=describe_reasoning_step(presentation, fallback_evidence_id, claim),
                    )
                )
    return steps


def recommended_hypothesis_evidence_ids(
    presentation,
    evidence_ids: Iterable[UUID],
    suspect_id: UUID | None,
    claims: Iterable[ClaimType],
    *,
    truth=None,
    state=None,
    limit: int = 3,
) -> list[UUID]:
    ordered_claims = list(dict.fromkeys(claims))
    if limit <= 0:
        return []
    candidates = _ranked_hypothesis_evidence(
        presentation,
        evidence_ids,
        suspect_id,
        ordered_claims,
        truth=truth,
        state=state,
    )
    if not candidates:
        return []

    selected: list[UUID] = []
    selected_set: set[UUID] = set()
    covered_claims: set[ClaimType] = set()
    selected_classes: set[str] = set()
    for item, supported_claims, _, _ in candidates:
        item_claims = [claim for claim in supported_claims if claim not in covered_claims]
        if not item_claims:
            continue
        selected.append(item.id)
        selected_set.add(item.id)
        covered_claims.update(item_claims)
        selected_classes.add(_validation_class(item))
        if len(selected) >= limit:
            return selected

    physical_candidates = [
        item
        for item, _, _, _ in candidates
        if isinstance(item, ForensicsResult)
        and item.id not in selected_set
        and _confidence_score(getattr(item, "confidence", ConfidenceBand.WEAK)) >= 2
    ]
    if physical_candidates and "physical" not in selected_classes and len(selected) < limit:
        selected.append(physical_candidates[0].id)
        selected_set.add(physical_candidates[0].id)
        selected_classes.add("physical")

    for item, supported_claims, observed, _ in candidates:
        if item.id in selected_set:
            continue
        item_class = _validation_class(item)
        confidence_score = _confidence_score(getattr(item, "confidence", ConfidenceBand.WEAK))
        if item_class in selected_classes and confidence_score < 3:
            continue
        if supported_claims or observed or item_class not in selected_classes:
            selected.append(item.id)
            selected_set.add(item.id)
            selected_classes.add(item_class)
            if len(selected) >= limit:
                return selected
    return selected


def suspect_candidate_ids(
    truth,
    presentation,
    evidence_ids: Iterable[UUID],
) -> list[UUID]:
    id_set = set(evidence_ids)
    scores: dict[UUID, int] = {}
    for item in presentation.evidence:
        if item.id not in id_set:
            continue
        for person_id in getattr(item, "observed_person_ids", []) or []:
            scores[person_id] = scores.get(person_id, 0) + 3

    red_herring_id = getattr(truth, "case_meta", {}).get("red_herring_suspect_id")
    if isinstance(red_herring_id, str):
        try:
            red_herring_uuid = UUID(red_herring_id)
        except ValueError:
            red_herring_uuid = None
        if red_herring_uuid is not None and red_herring_uuid in truth.people:
            scores[red_herring_uuid] = max(scores.get(red_herring_uuid, 0), 2)

    for person in truth.people.values():
        if RoleTag.VICTIM in person.role_tags:
            continue
        scores.setdefault(person.id, 0)
        if RoleTag.OFFENDER in person.role_tags:
            scores[person.id] += 1

    return sorted(
        scores,
        key=lambda person_id: (-scores[person_id], truth.people[person_id].name),
    )


def _ranked_hypothesis_evidence(
    presentation,
    evidence_ids: Iterable[UUID],
    suspect_id: UUID | None,
    claims: list[ClaimType],
    *,
    truth=None,
    state=None,
) -> list[tuple[EvidenceItem, list[ClaimType], bool, tuple]]:
    id_set = set(evidence_ids)
    ranked: list[tuple[EvidenceItem, list[ClaimType], bool, tuple]] = []
    for item in presentation.evidence:
        if item.id not in id_set:
            continue
        supported_claims: list[ClaimType] = []
        for claim in claims:
            supported, _ = supports_reasoning_step(
                presentation,
                item.id,
                suspect_id,
                claim,
                truth=truth,
                state=state,
            )
            if supported:
                supported_claims.append(claim)
        observed = bool(
            suspect_id is not None
            and suspect_id in (getattr(item, "observed_person_ids", []) or [])
        )
        sort_key = (
            len(supported_claims),
            1 if observed else 0,
            _confidence_score(getattr(item, "confidence", ConfidenceBand.WEAK)),
            1 if isinstance(item, ForensicsResult) else 0,
            1 if isinstance(item, CCTVReport) else 0,
            -presentation.evidence.index(item),
        )
        ranked.append((item, supported_claims, observed, sort_key))
    return sorted(
        ranked,
        key=lambda entry: (
            -entry[3][0],
            -entry[3][1],
            -entry[3][2],
            -entry[3][3],
            -entry[3][4],
            entry[0].summary,
        ),
    )


def _confidence_score(confidence) -> int:
    value = confidence.value if hasattr(confidence, "value") else str(confidence)
    order = {ConfidenceBand.WEAK.value: 1, ConfidenceBand.MEDIUM.value: 2, ConfidenceBand.STRONG.value: 3}
    return order.get(value, 0)


def _validation_class(item: EvidenceItem) -> str:
    if isinstance(item, ForensicsResult):
        return "physical"
    return "testimonial"


def _motive_supported(truth, state, known: list[EvidenceItem]) -> bool:
    if truth is None or state is None or state.profile is None:
        return False
    drive = state.profile.drive
    if drive == ProfileDrive.UNKNOWN:
        return False
    motive = str(getattr(truth, "case_meta", {}).get("motive_category", "") or "")
    if not motive:
        return False
    drive_map = {
        "money": {ProfileDrive.MISSION},
        "concealment": {ProfileDrive.MISSION, ProfileDrive.POWER_CONTROL},
        "revenge": {ProfileDrive.POWER_CONTROL},
        "obsession": {ProfileDrive.POWER_CONTROL, ProfileDrive.VISIONARY},
        "thrill": {ProfileDrive.HEDONISTIC},
    }
    if drive not in drive_map.get(motive, set()):
        return False
    return bool(set(state.profile.evidence_ids).intersection(item.id for item in known))


def _behavior_supported(state, known: list[EvidenceItem]) -> bool:
    if state is None or state.profile is None:
        return False
    profile = state.profile
    supported_ids = set(profile.evidence_ids).intersection(item.id for item in known)
    if not supported_ids:
        return False
    has_behavior = profile.organization != ProfileOrganization.UNKNOWN or profile.mobility != ProfileMobility.UNKNOWN
    return has_behavior
