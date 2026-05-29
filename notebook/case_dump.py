"""Headless case generator: build a real game case, return a JSON payload
with every field the notebook (and the TUI) cares about.

This re-uses the same _start_case helper the CLI runs so the notebook
shows the same world the terminal does for a given --seed.
"""
from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any

from noir.cases.archetypes import CaseArchetype
from noir.cli.run_game import _start_case
from noir.domain.enums import EvidenceType, RoleTag
from noir.investigation.costs import PRESSURE_LIMIT, TIME_LIMIT
from noir.investigation.leads import LeadStatus
from noir.investigation.outcomes import TRUST_LIMIT
from noir.narrative.gaze import GazeMode, gaze_label
from noir.narrative.recaps import (
    build_cold_open,
    build_episode_title,
    build_partner_line,
    build_previously_on,
)
from noir.nemesis import PatternTracker
from noir.ui.text import (
    HeaderSnapshot,
    compose_episode_log_line,
    compose_header_line,
    compose_hypothesis_line,
    compose_now_line,
    compose_snapshot_block,
)
from noir.util.rng import Rng
from noir.world.state import WorldState


def _person_view(person, role: str) -> dict[str, Any]:
    return {
        "id": str(person.id),
        "name": person.name,
        "role": role,
        "age_range": getattr(person, "age_range", ""),
        "traits": {k: v for k, v in (person.traits or {}).items() if isinstance(v, str)},
    }


def _evidence_view(item) -> dict[str, Any]:
    out: dict[str, Any] = {
        "id": str(item.id),
        "type": item.evidence_type.value,
        "summary": item.summary,
        "source": item.source,
        "confidence": item.confidence.value,
        "time_collected": item.time_collected,
    }
    if getattr(item, "finding", None):
        out["finding"] = item.finding
    if getattr(item, "method", None):
        out["method"] = item.method
    if getattr(item, "statement", None):
        out["statement"] = item.statement
    return out


def _lead_view(lead) -> dict[str, Any]:
    return {
        "key": lead.key,
        "label": lead.label,
        "evidence_type": lead.evidence_type.value,
        "deadline": lead.deadline,
        "action_hint": lead.action_hint,
        "status": lead.status.value,
    }


def _poi_view(poi) -> dict[str, Any]:
    return {
        "poi_id": poi.poi_id,
        "label": poi.label,
        "zone": poi.zone_label,
        "description": poi.description,
        "tags": list(poi.tags or []),
    }


def build_case_payload(
    seed: int,
    case_index: int = 1,
    case_archetype: CaseArchetype | None = None,
    gaze_mode: GazeMode = GazeMode.FORENSIC,
) -> dict[str, Any]:
    """Build a real case the same way the CLI/TUI do and return a dict
    structured for the detective notebook front-end."""
    base_rng = Rng(seed)
    world = WorldState()
    pattern_tracker = PatternTracker.from_library(base_rng.fork("pattern"))
    (
        truth,
        presentation,
        state,
        board,
        location_id,
        item_id,
        district,
        location_name,
        modifiers,
        case_facts,
    ) = _start_case(
        base_rng, seed, case_index, world, pattern_tracker=pattern_tracker
    )

    # Episode opener — same builders the TUI uses.
    episode_rng = base_rng.fork(f"episode-{case_index}")
    archetype_value = case_facts.get("case_archetype") if isinstance(case_facts, dict) else None
    if world.endgame_ready():
        episode_kind = "nemesis"
    else:
        episode_kind = "copycat" if archetype_value == CaseArchetype.PATTERN.value else "normal"
    case_tags: list[str] = []
    tag_map = {
        CaseArchetype.PRESSURE.value: ["pressure", "escalation"],
        CaseArchetype.PATTERN.value: ["recurrence", "copycat"],
        CaseArchetype.CHARACTER.value: ["identity", "personal"],
        CaseArchetype.FORESHADOWING.value: ["recurrence", "escalation"],
    }
    case_tags = tag_map.get(archetype_value, [])
    episode_title = build_episode_title(
        episode_rng,
        location_name,
        district,
        episode_kind=episode_kind,
        case_tags=case_tags,
        title_state=world.episode_titles,
    )
    season = world.campaign.season_index
    episode_code = f"S{season}E{case_index}"
    previously_on = build_previously_on(world)
    cold_open = build_cold_open(episode_rng.fork("cold-open"), location_name)
    partner = build_partner_line(episode_rng.fork("partner"))
    briefing_lines = list(modifiers.briefing_lines or [])

    # Header / snapshot — exactly the same composer the TUI uses.
    arc = world.campaign.nemesis_arc
    header_snap = HeaderSnapshot(
        case_id=truth.case_id,
        episode_code=episode_code,
        episode_title=episode_title,
        time=state.time,
        pressure=state.pressure,
        trust=state.trust,
        gaze_mode=gaze_mode,
    )
    header_line = compose_header_line(header_snap)
    now_line = compose_now_line(
        pressure=state.pressure,
        trust=state.trust,
        tension=world.campaign.tension.value,
        nemesis_clock=arc.clock,
        nemesis_clock_max=arc.clock_max,
        nemesis_confronted=arc.confronted,
        endgame_ready=world.endgame_ready(),
        pending_lead_count=sum(1 for ld in state.leads if ld.status == LeadStatus.ACTIVE),
    )
    snapshot = compose_snapshot_block(district, location_name, state.pressure, state.trust)
    hypothesis_line = compose_hypothesis_line(None, [], 0)

    # People / suspects / witnesses / victim — pulled from the real TruthState.
    suspects = [
        _person_view(p, "suspect")
        for p in truth.people.values()
        if RoleTag.SUSPECT in p.role_tags
    ]
    witnesses = [
        _person_view(p, "witness")
        for p in truth.people.values()
        if RoleTag.WITNESS in p.role_tags
    ]
    victim = next(
        (
            _person_view(p, "victim")
            for p in truth.people.values()
            if RoleTag.VICTIM in p.role_tags
        ),
        None,
    )

    evidence = [_evidence_view(item) for item in presentation.evidence]
    leads = [_lead_view(ld) for ld in state.leads]
    scene_pois = [_poi_view(p) for p in state.scene_pois]

    # Pattern plan (the cross-case 'Pattern' tab on the TUI).
    pattern_plan = truth.case_meta.get("pattern_plan") or {}

    return {
        "tv_opener": {
            "season": season,
            "episode": case_index,
            "code": episode_code,
            "title": episode_title,
            "kind": episode_kind,
            "previously_on": previously_on,
            "cold_open": cold_open,
            "partner": partner,
            "briefing": briefing_lines,
            "log_line": compose_episode_log_line(episode_code, episode_title),
        },
        "header": {
            "line": header_line,
            "case_id": truth.case_id,
            "episode_code": episode_code,
            "episode_title": episode_title,
            "time": state.time,
            "time_limit": TIME_LIMIT,
            "pressure": state.pressure,
            "pressure_limit": PRESSURE_LIMIT,
            "trust": state.trust,
            "trust_limit": TRUST_LIMIT,
            "gaze": gaze_label(gaze_mode),
            "tension": world.campaign.tension.value,
        },
        "snapshot": {
            "lines": snapshot,
            "district": district,
            "location": location_name,
        },
        "now_line": now_line,
        "hypothesis_line": hypothesis_line,
        "victim": victim,
        "suspects": suspects,
        "witnesses": witnesses,
        "evidence": evidence,
        "leads": leads,
        "scene_pois": scene_pois,
        "pattern": {
            "label": pattern_plan.get("label", ""),
            "summary": pattern_plan.get("summary", ""),
        },
        "seed": seed,
    }


def build_case_json(seed: int, **kwargs) -> str:
    return json.dumps(build_case_payload(seed, **kwargs), default=str)


if __name__ == "__main__":
    import argparse, sys

    p = argparse.ArgumentParser(description="Dump a case as JSON for the notebook.")
    p.add_argument("--seed", type=int, default=101)
    p.add_argument("--case-index", type=int, default=1)
    args = p.parse_args()
    sys.stdout.write(build_case_json(args.seed, case_index=args.case_index))
