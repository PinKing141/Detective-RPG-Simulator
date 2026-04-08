"""Player-facing guidance for stabilizing early investigation routes."""

from __future__ import annotations

from noir.domain.enums import RoleTag
from noir.presentation.evidence import CCTVReport, ForensicsResult, WitnessStatement


def investigation_guidance_lines(truth, presentation, state) -> list[str]:
    known_ids = set(state.knowledge.known_evidence)
    known_items = [item for item in presentation.evidence if item.id in known_ids]
    known_witness = [item for item in known_items if isinstance(item, WitnessStatement)]
    known_cctv = [item for item in known_items if isinstance(item, CCTVReport)]
    known_physical = [item for item in known_items if isinstance(item, ForensicsResult)]
    witness_count = sum(1 for person in truth.people.values() if RoleTag.WITNESS in person.role_tags)
    interviewed_ids = {
        person_id
        for person_id in state.interviews
        if person_id in {str(person.id) for person in truth.people.values()}
    }

    lines: list[str] = []
    if len(interviewed_ids) == 1 and witness_count > 1:
        lines.append(
            "One witness is only a starting point here. Other witnesses may carry the cleaner suspect read."
        )
    if known_witness and not known_cctv and not known_physical:
        lines.append(
            "The case currently rests on testimony alone. Pull CCTV or lab work before you commit to a theory."
        )
    elif known_witness and not known_physical:
        lines.append(
            "You still lack physical corroboration. Submit forensics before you turn this into an arrest."
        )
    if len(interviewed_ids) < witness_count and (known_cctv or known_physical):
        lines.append(
            "Harder evidence is in play now. Use the remaining witnesses to tighten presence or opportunity rather than broad searching."
        )
    return list(dict.fromkeys(lines))