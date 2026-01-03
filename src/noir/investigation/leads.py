"""Lead clocks and escalation for Phase 1."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from noir.domain.enums import ConfidenceBand, EvidenceType
from noir.investigation.results import InvestigationState
from noir.presentation.evidence import CCTVReport, ForensicObservation, ForensicsResult, WitnessStatement


class LeadStatus(StrEnum):
    ACTIVE = "active"
    EXPIRED = "expired"
    RESOLVED = "resolved"


@dataclass
class Lead:
    key: str
    label: str
    evidence_type: EvidenceType
    deadline: int
    action_hint: str
    status: LeadStatus = LeadStatus.ACTIVE


LEAD_DEADLINES = {
    EvidenceType.TESTIMONIAL: 2,
    EvidenceType.CCTV: 3,
    EvidenceType.FORENSICS: 4,
}

LEAD_LABELS = {
    EvidenceType.TESTIMONIAL: "Witness lead",
    EvidenceType.CCTV: "CCTV lead",
    EvidenceType.FORENSICS: "Forensics lead",
}

LEAD_ACTIONS = {
    EvidenceType.TESTIMONIAL: "Interview witness",
    EvidenceType.CCTV: "Request CCTV",
    EvidenceType.FORENSICS: "Submit forensics",
}


def build_leads(
    presentation, start_time: int = 0, deadline_delta: int = 0
) -> list[Lead]:
    types_present = {item.evidence_type for item in presentation.evidence}
    leads: list[Lead] = []
    for evidence_type in [EvidenceType.TESTIMONIAL, EvidenceType.CCTV, EvidenceType.FORENSICS]:
        if evidence_type not in types_present:
            continue
        deadline = start_time + max(0, LEAD_DEADLINES[evidence_type] - max(0, deadline_delta))
        leads.append(
            Lead(
                key=evidence_type.value,
                label=LEAD_LABELS[evidence_type],
                evidence_type=evidence_type,
                deadline=deadline,
                action_hint=LEAD_ACTIONS[evidence_type],
            )
        )
    return leads[:3]


def update_lead_statuses(state: InvestigationState) -> list[str]:
    notes: list[str] = []
    for lead in state.leads:
        if lead.status == LeadStatus.ACTIVE and state.time >= lead.deadline:
            lead.status = LeadStatus.EXPIRED
            notes.append(f"Lead went cold: {lead.label}.")
    return notes


def lead_for_type(state: InvestigationState, evidence_type: EvidenceType) -> Lead | None:
    for lead in state.leads:
        if lead.evidence_type == evidence_type:
            return lead
    return None


def mark_lead_resolved(state: InvestigationState, evidence_type: EvidenceType) -> None:
    lead = lead_for_type(state, evidence_type)
    if lead and lead.status == LeadStatus.ACTIVE:
        lead.status = LeadStatus.RESOLVED


def shorten_lead(state: InvestigationState, evidence_type: EvidenceType, delta: int) -> Lead | None:
    lead = lead_for_type(state, evidence_type)
    if lead is None or lead.status != LeadStatus.ACTIVE:
        return None
    lead.deadline = max(state.time, lead.deadline - delta)
    if state.time >= lead.deadline:
        lead.status = LeadStatus.EXPIRED
    return lead


def apply_lead_decay(lead: Lead, items: list) -> list[str]:
    if lead.status != LeadStatus.EXPIRED:
        return []
    if lead.evidence_type == EvidenceType.TESTIMONIAL:
        for item in items:
            if not isinstance(item, WitnessStatement):
                continue
            item.confidence = ConfidenceBand.WEAK
            item.observed_person_ids = []
            item.statement = "I remember someone near the scene, but the details are gone now."
        return ["Witness lead expired; the statement is less certain."]
    if lead.evidence_type == EvidenceType.CCTV:
        for item in items:
            if not isinstance(item, CCTVReport):
                continue
            item.confidence = ConfidenceBand.WEAK
            item.observed_person_ids = []
            item.summary = "CCTV report (partial)"
        return ["CCTV lead expired; only partial footage remains."]
    if lead.evidence_type == EvidenceType.FORENSICS:
        for item in items:
            if not isinstance(item, (ForensicsResult, ForensicObservation)):
                continue
            item.confidence = ConfidenceBand.WEAK
            if isinstance(item, ForensicsResult):
                item.summary = "Forensics result (inconclusive)"
                item.method_category = "unknown"
                item.finding = "The lab could not reach a firm conclusion."
            else:
                item.summary = "Forensic observation (inconclusive)"
                item.observation = "The observation is too degraded to support a clear conclusion."
        return ["Forensics lead expired; the lab report is inconclusive."]
    return []
