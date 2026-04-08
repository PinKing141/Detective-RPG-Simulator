from __future__ import annotations

from uuid import UUID

from noir.domain.enums import ConfidenceBand, EvidenceType
from noir.presentation.evidence import ForensicsResult
from noir.util.rng import Rng


def build_contextual_lab_result(
    weapon_item,
    primary_location_id: UUID,
    method_category: str,
    access_path: str,
    control_style: str,
    cleanup_style: str,
    exit_style: str,
    competence: float,
    rng: Rng,
) -> ForensicsResult | None:
    candidates: list[tuple[dict, float]] = []
    if access_path == "forced_entry":
        candidates.append(
            (
                {
                    "summary": "Forensics result (entry trace)",
                    "finding": "Toolmark comparison confirms fresh entry damage and a deliberate forced approach.",
                    "method": "toolmark",
                    "confidence": ConfidenceBand.MEDIUM,
                },
                1.25,
            )
        )
    if control_style == "restraints":
        candidates.append(
            (
                {
                    "summary": "Forensics result (transfer trace)",
                    "finding": "Fiber and pressure-pattern analysis support close-contact restraint during the assault.",
                    "method": "trace",
                    "confidence": ConfidenceBand.MEDIUM,
                },
                1.3,
            )
        )
    elif control_style == "intimidation":
        candidates.append(
            (
                {
                    "summary": "Forensics result (contact trace)",
                    "finding": "Transfer residue and bruising patterns support close-contact coercion before the fatal act.",
                    "method": "trace",
                    "confidence": ConfidenceBand.MEDIUM,
                },
                1.15,
            )
        )
    if cleanup_style == "staging":
        candidates.append(
            (
                {
                    "summary": "Forensics result (staging trace)",
                    "finding": "Secondary transfer patterns show the body and nearby objects were repositioned after the attack.",
                    "method": "trace",
                    "confidence": ConfidenceBand.MEDIUM,
                },
                1.2,
            )
        )
    elif cleanup_style == "wipe" and competence < 0.85:
        candidates.append(
            (
                {
                    "summary": "Forensics result (wipe trace)",
                    "finding": "Latent residue confirms an attempted wipe-down on touched surfaces around the scene.",
                    "method": "trace",
                    "confidence": ConfidenceBand.MEDIUM,
                },
                1.0,
            )
        )
    if exit_style == "vehicle":
        candidates.append(
            (
                {
                    "summary": "Forensics result (exit trace)",
                    "finding": "Particulate transfer and fresh track residue support a rapid vehicle departure from the scene.",
                    "method": "trace",
                    "confidence": ConfidenceBand.MEDIUM,
                },
                0.9,
            )
        )
    if not candidates and cleanup_style != "arson":
        candidates.append(
            (
                {
                    "summary": "Forensics result (scene trace)",
                    "finding": "Microscopic transfer traces support close-contact movement through the primary scene.",
                    "method": "trace",
                    "confidence": ConfidenceBand.MEDIUM if competence < 0.7 else ConfidenceBand.WEAK,
                },
                0.75,
            )
        )
    if not candidates:
        return None
    payload = rng.weighted_choice(candidates)
    return ForensicsResult(
        evidence_type=EvidenceType.FORENSICS,
        summary=payload["summary"],
        source="Forensics Lab",
        time_collected=0,
        confidence=payload["confidence"],
        item_id=weapon_item.id,
        finding=payload["finding"],
        method=payload["method"],
        method_category=method_category,
        location_id=primary_location_id,
    )