"""Evidence support helpers for deduction validation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable
from uuid import UUID

from noir.deduction.board import MethodType
from noir.presentation.evidence import CCTVReport, EvidenceItem, ForensicsResult, WitnessStatement


@dataclass
class EvidenceSupport:
    supports: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)


def _known_evidence(presentation, evidence_ids: Iterable[UUID]) -> list[EvidenceItem]:
    id_set = set(evidence_ids)
    return [item for item in presentation.evidence if item.id in id_set]


def support_for_suspect(
    presentation,
    evidence_ids: Iterable[UUID],
    suspect_id: UUID | None,
) -> EvidenceSupport:
    support = EvidenceSupport()
    if suspect_id is None:
        support.missing.append("No suspect selected.")
        return support
    known = _known_evidence(presentation, evidence_ids)
    cctv_hits = [
        item
        for item in known
        if isinstance(item, CCTVReport) and suspect_id in item.observed_person_ids
    ]
    witness_placements = [
        item
        for item in known
        if isinstance(item, WitnessStatement) and suspect_id in item.observed_person_ids
    ]
    if cctv_hits:
        support.supports.append("CCTV places the suspect at the scene.")
    if witness_placements:
        support.supports.append("A witness places the suspect at the scene.")
    if not cctv_hits and not witness_placements:
        support.missing.append("No evidence places the suspect at the scene.")
    witness_hits = [item for item in known if isinstance(item, WitnessStatement)]
    if witness_hits:
        support.supports.append("A witness statement anchors the timeline.")
    else:
        support.missing.append("No witness statement anchors the timeline.")
    return support


def support_for_method(
    presentation,
    evidence_ids: Iterable[UUID],
    method: MethodType | None,
) -> EvidenceSupport:
    support = EvidenceSupport()
    if method is None:
        support.missing.append("No method selected.")
        return support
    if method == MethodType.UNKNOWN:
        support.supports.append("Method left unknown.")
        return support
    known = _known_evidence(presentation, evidence_ids)
    forensic_hits = [
        item
        for item in known
        if isinstance(item, ForensicsResult) and item.method_category == method.value
    ]
    if forensic_hits:
        support.supports.append("Forensics support the chosen method.")
    else:
        support.missing.append("No forensics support the chosen method.")
    return support
