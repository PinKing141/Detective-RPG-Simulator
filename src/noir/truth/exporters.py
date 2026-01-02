"""Truth dump helpers for debugging."""

from __future__ import annotations

from noir.truth.graph import TruthState


def dump_truth(truth: TruthState) -> str:
    lines: list[str] = []
    lines.append(f"Case: {truth.case_id} (seed {truth.seed})")
    if truth.case_meta:
        lines.append("Case meta:")
        for key, value in truth.case_meta.items():
            lines.append(f"- {key}: {value}")
    lines.append("")
    lines.append("People:")
    for person in truth.people.values():
        trait_summary = ", ".join(f"{key}={value}" for key, value in person.traits.items())
        trait_text = f" traits({trait_summary})" if trait_summary else ""
        lines.append(f"- {person.name} [{person.id}]{trait_text}")
    lines.append("")
    lines.append("Locations:")
    for location in truth.locations.values():
        lines.append(f"- {location.name} [{location.id}]")
    lines.append("")
    lines.append("Items:")
    for item in truth.items.values():
        lines.append(f"- {item.name} [{item.id}]")
    lines.append("")
    lines.append("Events:")
    for event in sorted(truth.events.values(), key=lambda e: e.timestamp):
        lines.append(
            f"- t{event.timestamp} {event.kind} "
            f"loc={event.location_id} participants={event.participants}"
        )
    return "\n".join(lines)
