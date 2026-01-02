"""Evidence support helpers for deduction validation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable
from uuid import UUID

from noir.deduction.board import ClaimType
from noir.presentation.evidence import CCTVReport, EvidenceItem, ForensicsResult, WitnessStatement


@dataclass
class EvidenceSupport:
    supports: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)


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
        return "none"
    if (end - start) > 2:
        return "broad"
    return "tight"


def support_for_claims(
    presentation,
    evidence_ids: Iterable[UUID],
    suspect_id: UUID | None,
    claims: Iterable[ClaimType],
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
        elif status == "broad":
            support.missing.append("Timeline is too broad to close opportunity.")
        elif status == "no_link":
            support.missing.append("No evidence ties the suspect to the opportunity window.")
        else:
            support.missing.append("No evidence constrains an opportunity window.")

    if ClaimType.MOTIVE in claim_set:
        support.missing.append("No evidence suggests a motive linked to the victim.")

    if ClaimType.BEHAVIOR in claim_set:
        support.missing.append("No evidence suggests behavioral alignment.")

    return support
