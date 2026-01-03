from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from textual.app import App, ComposeResult
from textual.containers import Vertical, VerticalScroll
from textual.widgets import Input, RichLog, Static

from noir import config
from noir.cases.archetypes import CaseArchetype
from noir.cases.truth_generator import generate_case
from noir.deduction.board import ClaimType, DeductionBoard
from noir.deduction.scoring import support_for_claims
from noir.deduction.validation import validate_hypothesis
from noir.domain.enums import RoleTag
from noir.investigation.actions import (
    arrest,
    interview,
    request_cctv,
    set_hypothesis,
    submit_forensics,
    visit_scene,
)
from noir.investigation.costs import ActionType, PRESSURE_LIMIT, TIME_LIMIT
from noir.investigation.interviews import InterviewApproach, InterviewTheme
from noir.investigation.leads import (
    LeadStatus,
    build_leads,
    build_neighbor_leads,
    format_neighbor_lead,
)
from noir.investigation.outcomes import TRUST_LIMIT, resolve_case_outcome
from noir.investigation.results import ActionOutcome, InvestigationState
from noir.locations.profiles import ScenePOI
from noir.narrative.gaze import (
    GazeMode,
    format_cctv_lines,
    format_forensic_lines,
    format_forensics_result_lines,
    format_witness_lines,
    gaze_label,
)
from noir.narrative.recaps import (
    build_cold_open,
    build_end_tag,
    build_episode_title,
    build_partner_line,
    build_previously_on,
)
from noir.presentation.evidence import (
    CCTVReport,
    ForensicObservation,
    ForensicsResult,
    WitnessStatement,
)
from noir.presentation.projector import project_case
from noir.profiling.summary import build_profiling_summary, format_profiling_summary
from noir.util.rng import Rng
from noir.persistence.db import WorldStore
from noir.world.autonomy import apply_autonomy
from noir.world.state import CaseStartModifiers, PersonRecord, WorldState


@dataclass
class PromptState:
    step: str
    data: dict[str, Any] = field(default_factory=dict)
    options: list[Any] = field(default_factory=list)


class Phase05App(App):
    TITLE = ""
    SUB_TITLE = ""
    BINDINGS = [
        ("f6", "focus_log", "Focus log"),
        ("f7", "focus_detail", "Focus detail"),
        ("f8", "focus_input", "Focus input"),
    ]
    CSS = """
    Screen {
        layout: vertical;
    }
    #header {
        height: auto;
        padding: 1 1;
    }
    #log {
        height: 1fr;
        border: solid $secondary;
        padding: 0 1;
    }
    #detail {
        height: 1fr;
        border: solid $secondary;
        padding: 0 1;
    }
    #detail_view {
        width: 100%;
    }
    #menu {
        height: auto;
        padding: 1 1;
    }
    #command {
        height: 3;
        padding: 0 1;
    }
    """

    def __init__(
        self,
        seed: int | None = None,
        case_id: str | None = None,
        world_db: Path | None = None,
        case_archetype: CaseArchetype | None = None,
        gaze_mode: GazeMode | None = None,
    ) -> None:
        super().__init__()
        self.seed = seed if seed is not None else config.SEED
        self.case_id = case_id
        self.base_rng = Rng(self.seed)
        self.case_index = 1
        self.world_store = WorldStore(world_db) if world_db else None
        self.world = self.world_store.load_world_state() if self.world_store else WorldState()
        self.case_start_tick = self.world.tick
        self.case_archetype = case_archetype
        self.gaze_mode = gaze_mode if gaze_mode is not None else GazeMode.FORENSIC
        self.district = "unknown"
        self.location_name = "unknown"
        self.case_modifiers = None
        self.state: InvestigationState | None = None
        self.board = DeductionBoard()
        self.prompt_state: PromptState | None = None
        self.selected_evidence_id = None
        self.last_result = None
        self.profile_lines: list[str] = []
        self._pending_briefing: list[str] = []
        self._pending_intro: list[str] = []
        self._has_mounted = False

        self._start_case(self.case_index, case_id_override=self.case_id)

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static("", id="header")
            yield RichLog(id="log", wrap=True)
            yield VerticalScroll(Static("", id="detail_view", expand=True), id="detail")
            yield Static(self._menu_text(), id="menu")
            yield Input(placeholder="Enter command (1-7 or q)...", id="command")

    def on_mount(self) -> None:
        self._refresh_header()
        self._refresh_detail(None)
        self._has_mounted = True
        if self._pending_intro:
            for line in self._pending_intro:
                self._write(line)
            self._pending_intro = []
        self._write(f"Case {self.truth.case_id} started.")
        if self._pending_briefing:
            for line in self._pending_briefing:
                self._write(line)
            self._pending_briefing = []
        self._write("Type a number to choose an action. Type 'q' to quit.")
        self._write("Focus: F6 log, F7 detail, F8 input (Tab cycles focus).")
        self.query_one("#command", Input).focus()

    def on_unmount(self) -> None:
        if self.world_store:
            self.world_store.save_world_state(self.world)
            self.world_store.close()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        value = event.value.strip()
        event.input.value = ""
        if not value:
            return
        if self.prompt_state is not None:
            self._handle_prompt_input(value)
            return
        if value.lower() == "q":
            self.exit()
            return
        self._handle_command(value)

    def _menu_text(self) -> str:
        return (
            "Choose action:\n"
            "1) Visit scene\n"
            "2) Interview witness\n"
            "3) Request CCTV\n"
            "4) Submit forensics\n"
            "5) Set hypothesis\n"
            "6) Profiling summary\n"
            "7) Arrest"
        )

    def _write(self, message: str) -> None:
        log = self.query_one("#log", RichLog)
        log.write(message)

    def action_focus_log(self) -> None:
        self.query_one("#log", RichLog).focus()

    def action_focus_detail(self) -> None:
        self.query_one("#detail", VerticalScroll).focus()

    def action_focus_input(self) -> None:
        self.query_one("#command", Input).focus()

    def _refresh_header(self) -> None:
        header = self.query_one("#header", Static)
        time_line = (
            f"Case: {self.truth.case_id}  Investigation Time {self.state.time}/{TIME_LIMIT}  "
            f"Pressure {self.state.pressure}/{PRESSURE_LIMIT}  "
            f"Trust {self.state.trust}/{TRUST_LIMIT}  "
            f"Gaze {gaze_label(self.gaze_mode)}"
        )
        lines = [time_line]
        scene_mode = None
        case_archetype = None
        scene_layout = self.case_facts.get("scene_layout")
        if isinstance(scene_layout, dict):
            scene_mode = scene_layout.get("mode")
        if isinstance(self.case_facts, dict):
            case_archetype = self.case_facts.get("case_archetype")
        if scene_mode or case_archetype:
            parts = []
            if case_archetype:
                parts.append(f"Archetype: {case_archetype}")
            if scene_mode:
                parts.append(f"Scene: {scene_mode}")
            lines.append(" | ".join(parts))
        lines.extend(self._hypothesis_lines())
        header.update("\n".join(lines))

    def _refresh_detail(self, result) -> None:
        detail = self.query_one("#detail_view", Static)
        lines: list[str] = []
        lines.append("Detail")
        lines.append(f"Evidence known: {len(self.state.knowledge.known_evidence)}/{len(self.presentation.evidence)}")
        lead_lines = self._lead_lines()
        if lead_lines and lead_lines != ["(none)"]:
            lines.append(f"Leads ({len(lead_lines)})")
            for line in lead_lines[:2]:
                lines.append(f"- {line}")
            if len(lead_lines) > 2:
                lines.append(f"- ... +{len(lead_lines) - 2} more")
        neighbor_lines = self._neighbor_lead_lines()
        if neighbor_lines and neighbor_lines != ["(none)"]:
            lines.append(f"Neighbor leads ({len(neighbor_lines)})")
            for line in neighbor_lines[:2]:
                lines.append(f"- {line}")
            if len(neighbor_lines) > 2:
                lines.append(f"- ... +{len(neighbor_lines) - 2} more")
        if self.state.scene_pois:
            lines.append(f"Scene POIs ({len(self.state.scene_pois)})")
            body_line = None
            for poi in self.state.scene_pois:
                if poi.poi_id == self.state.body_poi_id:
                    status = "visited" if poi.poi_id in self.state.visited_poi_ids else "unvisited"
                    body_line = f"{self._poi_display_line(poi)} ({status})"
                    break
            shown = 0
            if body_line:
                lines.append(f"- {body_line}")
                shown = 1
            else:
                for poi in self.state.scene_pois[:2]:
                    status = "visited" if poi.poi_id in self.state.visited_poi_ids else "unvisited"
                    lines.append(f"- {self._poi_display_line(poi)} ({status})")
                    shown += 1
            remaining = len(self.state.scene_pois) - shown
            if remaining > 0:
                lines.append(f"- ... +{remaining} more (use Visit scene to list)")
        if self.profile_lines:
            lines.append("Profiling summary")
            for line in self.profile_lines[:4]:
                lines.append(line)
            if len(self.profile_lines) > 4:
                lines.append(f"... +{len(self.profile_lines) - 4} more")
        last_result = result or self.last_result
        if last_result is not None:
            lines.append("")
            lines.append(f"Last action: {last_result.action}")
            lines.append(last_result.summary)
            for note in last_result.notes:
                lines.append(f"- {note}")
        known_ids = list(self.state.knowledge.known_evidence)
        if known_ids:
            lines.append("")
            lines.append(f"Evidence (known) ({len(known_ids)})")
            for idx, evidence_id in enumerate(known_ids[:3], start=1):
                item = next(
                    (e for e in self.presentation.evidence if e.id == evidence_id),
                    None,
                )
                if item is None:
                    continue
                lines.append(f"- {self._format_evidence(idx, item)}")
            if len(known_ids) > 3:
                lines.append(f"- ... +{len(known_ids) - 3} more")
            selected = self._selected_evidence()
            if selected is not None:
                lines.append("")
                lines.append("Selected evidence")
                detail_lines = self._format_evidence_detail(1, selected)
                if detail_lines and detail_lines[0].startswith("1) "):
                    detail_lines[0] = detail_lines[0][3:]
                lines.extend(detail_lines)
        detail.update("\n".join(lines))

    def _format_evidence(self, index: int, item) -> str:
        return f"{index}) {item.summary} ({item.evidence_type}, {item.confidence})"

    def _format_evidence_detail(self, index: int, item) -> list[str]:
        if isinstance(item, WitnessStatement):
            lines = [f"{index}) Witness statement", f"Source: {item.source}"]
            lines.extend(
                format_witness_lines(
                    self._format_time_phrase(item.reported_time_window),
                    item.statement,
                    self._witness_note(item),
                    self._format_confidence(item.confidence),
                    list(item.uncertainty_hooks),
                    self.gaze_mode,
                )
            )
            return lines
        if isinstance(item, ForensicObservation):
            lines = [f"{index}) {item.summary}"]
            poi_label = self._poi_label_for(item.poi_id)
            if poi_label:
                lines.append(f"Location: {poi_label}")
            tod_phrase = self._format_time_phrase(item.tod_window) if item.tod_window else None
            lines.extend(
                format_forensic_lines(
                    item.observation,
                    self._format_confidence(item.confidence),
                    tod_phrase,
                    item.stage_hint,
                    self.gaze_mode,
                )
            )
            return lines
        if isinstance(item, CCTVReport):
            lines = [f"{index}) {item.summary}"]
            lines.extend(
                format_cctv_lines(
                    item.summary,
                    self._format_time_phrase(item.time_window),
                    self._cctv_note(item),
                    self._format_confidence(item.confidence),
                    self.gaze_mode,
                )
            )
            return lines
        if isinstance(item, ForensicsResult):
            lines = [f"{index}) {item.summary}"]
            lines.extend(
                format_forensics_result_lines(
                    item.finding,
                    item.method_category,
                    self._format_confidence(item.confidence),
                    self.gaze_mode,
                )
            )
            return lines
        lines = [self._format_evidence(index, item)]
        if isinstance(item, CCTVReport):
            lines.append(f"Time: {self._format_time_phrase(item.time_window)}")
            note = self._cctv_note(item)
            if note:
                lines.append(note)
        if isinstance(item, ForensicsResult):
            lines.append(f"Finding: {item.finding}")
        return lines

    def _selected_evidence(self):
        if self.selected_evidence_id is None:
            return None
        for item in self.presentation.evidence:
            if item.id == self.selected_evidence_id:
                return item
        return None

    def _format_claim(self, claim: ClaimType) -> str:
        mapping = {
            ClaimType.PRESENCE: "Present near the scene",
            ClaimType.OPPORTUNITY: "Opportunity during the time window",
            ClaimType.MOTIVE: "Motive linked to the victim",
            ClaimType.BEHAVIOR: "Behavior aligns with the crime",
        }
        return mapping.get(claim, claim.value)

    def _interview_approach_label(self, approach: InterviewApproach) -> str:
        mapping = {
            InterviewApproach.BASELINE: "Baseline (rapport)",
            InterviewApproach.PRESSURE: "Pressure (challenge)",
            InterviewApproach.THEME: "Theme framing",
        }
        return mapping.get(approach, approach.value)

    def _interview_theme_label(self, theme: InterviewTheme) -> str:
        mapping = {
            InterviewTheme.BLAME_VICTIM: "Blame the victim",
            InterviewTheme.CIRCUMSTANCE: "Blame the circumstances",
            InterviewTheme.ALTRUISTIC: "Altruistic motive",
            InterviewTheme.ACCIDENTAL: "Accidental outcome",
        }
        return mapping.get(theme, theme.value)

    def _format_hour(self, hour: int) -> str:
        value = hour % 24
        suffix = "am" if value < 12 else "pm"
        display = value % 12
        if display == 0:
            display = 12
        return f"{display}{suffix}"

    def _format_time_phrase(self, window: tuple[int, int]) -> str:
        start, end = window
        if start == end:
            return f"around {self._format_hour(start)}"
        return f"between {self._format_hour(start)} and {self._format_hour(end)}"

    def _format_confidence(self, confidence) -> str:
        value = confidence.value if hasattr(confidence, "value") else str(confidence)
        mapping = {"strong": "High", "medium": "Medium", "weak": "Low"}
        return mapping.get(value, value.capitalize())

    def _primary_role_tag(self, role_tags: list[RoleTag]) -> str:
        if RoleTag.WITNESS in role_tags:
            return RoleTag.WITNESS.value
        if RoleTag.OFFENDER in role_tags:
            return RoleTag.OFFENDER.value
        if RoleTag.VICTIM in role_tags:
            return RoleTag.VICTIM.value
        if RoleTag.SUSPECT in role_tags:
            return RoleTag.SUSPECT.value
        return "unknown"

    def _sync_people(self, case_id: str) -> None:
        for person in self.truth.people.values():
            person_id = str(person.id)
            existing = self.world.people_index.get(person_id)
            country = None
            if isinstance(person.traits, dict):
                country = person.traits.get("country_of_origin")
            record = PersonRecord(
                person_id=person_id,
                name=person.name,
                role_tag=self._primary_role_tag(list(person.role_tags)),
                country_of_origin=country if isinstance(country, str) else None,
                religion_affiliation=None,
                religion_observance=None,
                community_connectedness=None,
                created_in_case_id=existing.created_in_case_id if existing else case_id,
                last_seen_case_id=case_id,
                last_seen_tick=self.world.tick,
            )
            self.world.upsert_person(record)

    def _lead_lines(self) -> list[str]:
        if not self.state.leads:
            return ["(none)"]
        lines: list[str] = []
        for idx, lead in enumerate(self.state.leads, start=1):
            if lead.status == LeadStatus.ACTIVE:
                status = f"active until t{lead.deadline}"
            elif lead.status == LeadStatus.RESOLVED:
                status = "resolved"
            else:
                status = "expired"
            lines.append(f"{idx}) {lead.label} - {status} ({lead.action_hint})")
        return lines

    def _witness_note(self, item: WitnessStatement) -> str | None:
        if item.observed_person_ids:
            person_id = item.observed_person_ids[0]
            person = self.truth.people.get(person_id)
            name = person.name if person else "someone"
            return f"Detective note: Suggests proximity near the location ({name})."
        return "Detective note: Suggests activity near the location."

    def _cctv_note(self, item: CCTVReport) -> str | None:
        if item.observed_person_ids:
            person_id = item.observed_person_ids[0]
            person = self.truth.people.get(person_id)
            name = person.name if person else "someone"
            return f"Detective note: Footage suggests proximity near the location ({name})."
        return "Detective note: Footage suggests movement near the location."

    def _poi_label_for(self, poi_id: str | None) -> str | None:
        if not poi_id:
            return None
        for poi in self.state.scene_pois:
            if poi.poi_id == poi_id:
                return self._poi_display_label(poi)
        return None

    def _poi_display_label(self, poi: ScenePOI) -> str:
        label = f"{poi.zone_label} - {poi.label}"
        if self.state.body_poi_id and poi.poi_id == self.state.body_poi_id:
            return f"{label} (body)"
        return label

    def _poi_display_line(self, poi: ScenePOI) -> str:
        label = self._poi_display_label(poi)
        if poi.description:
            return f"{label}: {poi.description}"
        return label

    def _poi_lines(self) -> list[str]:
        if not self.state.scene_pois:
            return ["(none)"]
        lines: list[str] = []
        for idx, poi in enumerate(self.state.scene_pois, start=1):
            status = "visited" if poi.poi_id in self.state.visited_poi_ids else "unvisited"
            lines.append(f"{idx}) {self._poi_display_line(poi)} ({status})")
        return lines

    def _neighbor_lead_lines(self) -> list[str]:
        if not self.state.neighbor_leads:
            return ["(none)"]
        return [format_neighbor_lead(lead) for lead in self.state.neighbor_leads]

    def _supporting_evidence_lines(self) -> list[str]:
        if self.board.hypothesis is None:
            return []
        id_set = set(self.board.hypothesis.evidence_ids)
        lines: list[str] = []
        for item in self.presentation.evidence:
            if item.id not in id_set:
                continue
            lines.append(f"{item.summary} ({self._format_confidence(item.confidence)})")
        return lines

    def _hypothesis_lines(self) -> list[str]:
        if self.board.hypothesis is None:
            return ["Hypothesis: (none)"]
        suspect = self.truth.people.get(self.board.hypothesis.suspect_id)
        suspect_name = suspect.name if suspect else "Unknown"
        claims = ", ".join(self._format_claim(claim) for claim in self.board.hypothesis.claims)
        evidence_lines = self._supporting_evidence_lines()
        if evidence_lines:
            support_summary = ", ".join(evidence_lines)
        else:
            support_summary = "(none)"
        claim_support = support_for_claims(
            self.presentation,
            self.board.hypothesis.evidence_ids,
            self.board.hypothesis.suspect_id,
            self.board.hypothesis.claims,
        )
        gap_summary = "; ".join(claim_support.missing) if claim_support.missing else "(none)"
        return [
            f"Hypothesis: {suspect_name}",
            f"Claims: {claims or '(none)'}",
            f"Support: {support_summary}",
            f"Gaps: {gap_summary}",
        ]

    def _handle_command(self, value: str) -> None:
        if value == "1":
            body_poi = None
            if self.state.body_poi_id:
                for poi in self.state.scene_pois:
                    if (
                        poi.poi_id == self.state.body_poi_id
                        and poi.poi_id not in self.state.visited_poi_ids
                    ):
                        body_poi = poi
                        break
            auto_body = False
            if body_poi:
                auto_body = True
                result = visit_scene(
                    self.truth,
                    self.presentation,
                    self.state,
                    self.location_id,
                    poi_id=body_poi.poi_id,
                    poi_label=self._poi_display_label(body_poi),
                    poi_description=body_poi.description,
                )
                if any(
                    poi.poi_id not in self.state.visited_poi_ids
                    for poi in self.state.scene_pois
                ):
                    result.notes.append(
                        "Other scene areas remain; visit the scene again to inspect another area."
                    )
                self._apply_action_result(result)
                return
            unvisited = [
                poi for poi in self.state.scene_pois if poi.poi_id not in self.state.visited_poi_ids
            ]
            if unvisited:
                self.prompt_state = PromptState(step="visit_poi", options=unvisited)
                self._write("Choose a scene area to inspect:")
                for idx, poi in enumerate(unvisited, start=1):
                    self._write(f"{idx}) {self._poi_display_line(poi)}")
                return
            result = visit_scene(self.truth, self.presentation, self.state, self.location_id)
            self._apply_action_result(result)
            return
        if value == "2":
            result = self._interview_witness()
            if result:
                self._apply_action_result(result)
            return
        if value == "3":
            result = request_cctv(self.truth, self.presentation, self.state, self.location_id)
            self._apply_action_result(result)
            return
        if value == "4":
            result = submit_forensics(
                self.truth,
                self.presentation,
                self.state,
                self.location_id,
                item_id=self.item_id,
            )
            self._apply_action_result(result)
            return
        if value == "5":
            self._start_hypothesis_prompt()
            return
        if value == "6":
            context_lines = self.world.context_lines(self.district, self.location_name)
            summary = build_profiling_summary(
                self.presentation,
                self.state,
                self.board.hypothesis,
                context_lines=context_lines,
            )
            self.profile_lines = format_profiling_summary(
                summary, include_title=False
            )
            for line in self.profile_lines:
                self._write(line)
            self._refresh_detail(None)
            return
        if value == "7":
            if self.board.hypothesis is None:
                self._write("Set a hypothesis before arrest.")
                return
            result = arrest(
                self.truth,
                self.presentation,
                self.state,
                self.board.hypothesis.suspect_id,
                self.location_id,
                has_hypothesis=True,
            )
            self._apply_action_result(result)
            if result.action == ActionType.ARREST:
                self._finalize_arrest()
            return
        self._write("Unknown action.")

    def _apply_action_result(self, result) -> None:
        autonomy_notes = apply_autonomy(self.state, self.world, self.district)
        if autonomy_notes:
            result.notes.extend(autonomy_notes)
        if result.action == ActionType.SET_HYPOTHESIS and result.outcome == ActionOutcome.SUCCESS:
            self._write(
                f"{result.summary} (+{result.time_cost} time, +{result.pressure_cost} pressure)"
            )
        else:
            self._write(f"[{result.action}] {result.summary}")
        for item in result.revealed:
            if isinstance(item, WitnessStatement):
                self._write("- New evidence: Witness statement")
                lines = format_witness_lines(
                    self._format_time_phrase(item.reported_time_window),
                    item.statement,
                    self._witness_note(item),
                    self._format_confidence(item.confidence),
                    list(item.uncertainty_hooks),
                    self.gaze_mode,
                )
                for line in lines:
                    self._write(f"  {line}")
            elif isinstance(item, ForensicObservation):
                self._write(f"- New evidence: {item.summary}")
                poi_label = self._poi_label_for(item.poi_id)
                if poi_label:
                    self._write(f"  Location: {poi_label}")
                tod_phrase = self._format_time_phrase(item.tod_window) if item.tod_window else None
                lines = format_forensic_lines(
                    item.observation,
                    self._format_confidence(item.confidence),
                    tod_phrase,
                    item.stage_hint,
                    self.gaze_mode,
                )
                for line in lines:
                    self._write(f"  {line}")
            elif isinstance(item, CCTVReport):
                self._write(f"- New evidence: {item.summary}")
                lines = format_cctv_lines(
                    item.summary,
                    self._format_time_phrase(item.time_window),
                    self._cctv_note(item),
                    self._format_confidence(item.confidence),
                    self.gaze_mode,
                )
                for line in lines:
                    self._write(f"  {line}")
            elif isinstance(item, ForensicsResult):
                self._write(f"- New evidence: {item.summary}")
                lines = format_forensics_result_lines(
                    item.finding,
                    item.method_category,
                    self._format_confidence(item.confidence),
                    self.gaze_mode,
                )
                for line in lines:
                    self._write(f"  {line}")
            else:
                self._write(f"- New evidence: {item.summary} ({item.evidence_type}, {item.confidence})")
        for note in result.notes:
            self._write(f"- {note}")
        if result.revealed:
            self.selected_evidence_id = result.revealed[0].id
        elif self.selected_evidence_id is None and self.state.knowledge.known_evidence:
            self.selected_evidence_id = self.state.knowledge.known_evidence[0]
        self.last_result = result
        self._refresh_header()
        self._refresh_detail(result)

    def _finalize_arrest(self) -> None:
        self.board.sync_from_state(self.state)
        validation = validate_hypothesis(self.truth, self.board, self.presentation, self.state)
        self._write(validation.summary)
        if validation.supports:
            self._write("Supports:")
            for line in validation.supports:
                self._write(f"- {line}")
        if validation.missing:
            self._write("Missing:")
            for line in validation.missing:
                self._write(f"- {line}")
        if validation.notes:
            self._write("Notes:")
            for line in validation.notes:
                self._write(f"- {line}")
        outcome = resolve_case_outcome(validation)
        self._write(f"Case outcome: {outcome.arrest_result}.")
        for note in outcome.notes:
            self._write(f"- {note}")
        case_end_tick = self.case_start_tick + self.state.time
        world_notes = self.world.apply_case_outcome(
            outcome,
            self.truth.case_id,
            self.seed,
            self.district,
            self.location_name,
            self.case_start_tick,
            case_end_tick,
        )
        if self.world_store:
            self.world_store.save_world_state(self.world)
            self.world_store.record_case(self.world.case_history[-1])
        for note in world_notes:
            self._write(f"- {note}")
        end_rng = self.base_rng.fork(f"end-{self.case_index}")
        for line in build_end_tag(end_rng, outcome.arrest_result.value):
            self._write(line)
        self.case_index += 1
        self.case_start_tick = self.world.tick
        self._start_case(self.case_index)
        self._write(f"New case {self.truth.case_id} started.")
        self._refresh_header()
        self._refresh_detail(None)

    def _start_case(self, case_index: int, case_id_override: str | None = None) -> None:
        case_rng = self.base_rng.fork(f"case-{case_index}")
        case_id = case_id_override or f"case_{self.seed}_{case_index}"
        self.truth, self.case_facts = generate_case(
            case_rng,
            case_id=case_id,
            world=self.world,
            case_archetype=self.case_archetype,
        )
        self.presentation = project_case(self.truth, case_rng.fork("projection"))
        self.case_start_tick = self.world.tick
        location = self.truth.locations.get(self.case_facts["crime_scene_id"])
        self.district = location.district if location else "unknown"
        self.location_name = location.name if location else "unknown"
        intro_lines: list[str] = []
        if case_index == 1:
            intro_lines.extend(build_previously_on(self.world))
        episode_rng = self.base_rng.fork(f"episode-{case_index}")
        episode_title = build_episode_title(episode_rng, self.location_name, self.district)
        intro_lines.append(f"Episode: {episode_title}")
        intro_lines.extend(build_cold_open(episode_rng, self.location_name))
        intro_lines.extend(build_partner_line(episode_rng))
        if intro_lines:
            if self._has_mounted:
                for line in intro_lines:
                    self._write(line)
            else:
                self._pending_intro = list(intro_lines)
        self.case_modifiers = self.world.case_start_modifiers(
            self.district, self.location_name
        )
        has_returning = self.world.has_returning_person(
            self.truth.people, self.truth.case_id
        )
        self.state = InvestigationState(
            pressure=self.world.pressure,
            trust=self.world.trust,
            cooperation=self.case_modifiers.cooperation,
        )
        self.state.leads = build_leads(
            self.presentation,
            start_time=self.state.time,
            deadline_delta=self.case_modifiers.lead_deadline_delta,
        )
        scene_layout = self.case_facts.get("scene_layout") or {}
        poi_rows = scene_layout.get("pois", []) or []
        self.state.scene_pois = [ScenePOI(**row) for row in poi_rows if isinstance(row, dict)]
        body_poi_id = self.case_facts.get("body_poi_id") or self.case_facts.get("primary_poi_id")
        self.state.body_poi_id = body_poi_id or None
        self.state.neighbor_leads = build_neighbor_leads(scene_layout)
        self.board = DeductionBoard()
        self.prompt_state = None
        self.selected_evidence_id = None
        self.last_result = None
        self.profile_lines = []
        self.location_id = self.case_facts["crime_scene_id"]
        self.item_id = self.case_facts["weapon_id"]
        self._sync_people(self.truth.case_id)
        if has_returning:
            self.case_modifiers = CaseStartModifiers(
                cooperation=self.case_modifiers.cooperation,
                lead_deadline_delta=self.case_modifiers.lead_deadline_delta,
                briefing_lines=self.case_modifiers.briefing_lines
                + ["A familiar name is attached to the file."],
            )
        if self.case_modifiers:
            if self._has_mounted:
                for line in self.case_modifiers.briefing_lines:
                    self._write(line)
            else:
                self._pending_briefing = list(self.case_modifiers.briefing_lines)

    def _interview_witness(self):
        witnesses = [p for p in self.truth.people.values() if RoleTag.WITNESS in p.role_tags]
        if not witnesses:
            self._write("No witness available.")
            return None
        if len(witnesses) == 1:
            self.prompt_state = PromptState(
                step="interview_approach",
                data={"witness_id": witnesses[0].id},
                options=list(InterviewApproach),
            )
            self._write("Choose interview approach:")
            for idx, approach in enumerate(self.prompt_state.options, start=1):
                self._write(f"{idx}) {self._interview_approach_label(approach)}")
            return None
        self.prompt_state = PromptState(step="interview_witness", options=witnesses)
        self._write("Choose a witness:")
        for idx, person in enumerate(witnesses, start=1):
            self._write(f"{idx}) {person.name}")
        return None

    def _start_hypothesis_prompt(self) -> None:
        self.board.sync_from_state(self.state)
        suspects = [p for p in self.truth.people.values() if RoleTag.OFFENDER in p.role_tags]
        if not suspects:
            self._write("No suspect available.")
            return
        self.prompt_state = PromptState(step="hyp_suspect", options=suspects)
        self._write("Set hypothesis. Choose suspect:")
        for idx, person in enumerate(suspects, start=1):
            self._write(f"{idx}) {person.name}")

    def _handle_prompt_input(self, value: str) -> None:
        if self.prompt_state is None:
            return
        if value.lower() == "q":
            self._write("Prompt cancelled.")
            self.prompt_state = None
            return
        step = self.prompt_state.step
        if step == "interview_witness":
            selection = self._parse_choice(value, len(self.prompt_state.options))
            if selection is None:
                self._write("Invalid choice.")
                return
            person = self.prompt_state.options[selection]
            self.prompt_state = PromptState(
                step="interview_approach",
                data={"witness_id": person.id},
                options=list(InterviewApproach),
            )
            self._write("Choose interview approach:")
            for idx, approach in enumerate(self.prompt_state.options, start=1):
                self._write(f"{idx}) {self._interview_approach_label(approach)}")
            return
        if step == "interview_approach":
            selection = self._parse_choice(value, len(self.prompt_state.options))
            if selection is None:
                self._write("Invalid choice.")
                return
            approach = self.prompt_state.options[selection]
            self.prompt_state.data["approach"] = approach
            if approach == InterviewApproach.THEME:
                self.prompt_state.step = "interview_theme"
                self.prompt_state.options = list(InterviewTheme)
                self._write("Choose framing theme:")
                for idx, theme in enumerate(self.prompt_state.options, start=1):
                    self._write(f"{idx}) {self._interview_theme_label(theme)}")
                return
            witness_id = self.prompt_state.data["witness_id"]
            self.prompt_state = None
            result = interview(
                self.truth,
                self.presentation,
                self.state,
                witness_id,
                self.location_id,
                approach=approach,
            )
            self._apply_action_result(result)
            return
        if step == "interview_theme":
            selection = self._parse_choice(value, len(self.prompt_state.options))
            if selection is None:
                self._write("Invalid choice.")
                return
            theme = self.prompt_state.options[selection]
            witness_id = self.prompt_state.data["witness_id"]
            approach = self.prompt_state.data.get("approach", InterviewApproach.THEME)
            self.prompt_state = None
            result = interview(
                self.truth,
                self.presentation,
                self.state,
                witness_id,
                self.location_id,
                approach=approach,
                theme=theme,
            )
            self._apply_action_result(result)
            return
        if step == "visit_poi":
            selection = self._parse_choice(value, len(self.prompt_state.options))
            if selection is None:
                self._write("Invalid choice.")
                return
            poi = self.prompt_state.options[selection]
            self.prompt_state = None
            result = visit_scene(
                self.truth,
                self.presentation,
                self.state,
                self.location_id,
                poi_id=poi.poi_id,
                poi_label=self._poi_display_label(poi),
                poi_description=poi.description,
            )
            self._apply_action_result(result)
            return
        if step == "hyp_suspect":
            selection = self._parse_choice(value, len(self.prompt_state.options))
            if selection is None:
                self._write("Invalid choice.")
                return
            self.prompt_state.data["suspect_id"] = self.prompt_state.options[selection].id
            self.prompt_state.step = "hyp_claims"
            self.prompt_state.options = list(ClaimType)
            self._write("Choose 1 to 3 claims (comma-separated):")
            for idx, claim in enumerate(self.prompt_state.options, start=1):
                self._write(f"{idx}) {self._format_claim(claim)}")
            return
        if step == "hyp_claims":
            indices = self._parse_multi_choice(value, len(self.prompt_state.options))
            if not indices or len(indices) > 3:
                self._write("Select 1 to 3 claims.")
                return
            claims = [self.prompt_state.options[idx] for idx in indices]
            self.prompt_state.data["claims"] = list(dict.fromkeys(claims))
            self.prompt_state.step = "hyp_evidence"
            evidence_items = [
                item for item in self.presentation.evidence if item.id in set(self.board.known_evidence_ids)
            ]
            self.prompt_state.options = evidence_items
            if not evidence_items:
                self._write("No evidence collected yet.")
                self.prompt_state = None
                return
            self._write("Choose 1 to 3 evidence items (comma-separated):")
            for idx, item in enumerate(evidence_items, start=1):
                if isinstance(item, WitnessStatement):
                    self._write(f"{idx}) Witness statement")
                    lines = format_witness_lines(
                        self._format_time_phrase(item.reported_time_window),
                        item.statement,
                        self._witness_note(item),
                        self._format_confidence(item.confidence),
                        list(item.uncertainty_hooks),
                        self.gaze_mode,
                    )
                    for line in lines:
                        self._write(f"   {line}")
                elif isinstance(item, ForensicObservation):
                    self._write(f"{idx}) {item.summary}")
                    poi_label = self._poi_label_for(item.poi_id)
                    if poi_label:
                        self._write(f"   Location: {poi_label}")
                    tod_phrase = (
                        self._format_time_phrase(item.tod_window) if item.tod_window else None
                    )
                    lines = format_forensic_lines(
                        item.observation,
                        self._format_confidence(item.confidence),
                        tod_phrase,
                        item.stage_hint,
                        self.gaze_mode,
                    )
                    for line in lines:
                        self._write(f"   {line}")
                elif isinstance(item, CCTVReport):
                    self._write(f"{idx}) {item.summary}")
                    lines = format_cctv_lines(
                        item.summary,
                        self._format_time_phrase(item.time_window),
                        self._cctv_note(item),
                        self._format_confidence(item.confidence),
                        self.gaze_mode,
                    )
                    for line in lines:
                        self._write(f"   {line}")
                elif isinstance(item, ForensicsResult):
                    self._write(f"{idx}) {item.summary}")
                    lines = format_forensics_result_lines(
                        item.finding,
                        item.method_category,
                        self._format_confidence(item.confidence),
                        self.gaze_mode,
                    )
                    for line in lines:
                        self._write(f"   {line}")
                else:
                    self._write(f"{idx}) {item.summary} ({item.evidence_type}, {item.confidence})")
            return
        if step == "hyp_evidence":
            evidence_ids = self._parse_indices(value, self.prompt_state.options)
            data = self.prompt_state.data
            self.prompt_state = None
            result = set_hypothesis(
                self.state,
                self.board,
                data["suspect_id"],
                data["claims"],
                evidence_ids,
            )
            self._apply_action_result(result)
            return

    def _parse_choice(self, value: str, count: int) -> int | None:
        if not value.isdigit():
            return None
        index = int(value) - 1
        if index < 0 or index >= count:
            return None
        return index

    def _parse_indices(self, value: str, items: list) -> list:
        indices: list[int] = []
        for part in value.split(","):
            part = part.strip()
            if not part.isdigit():
                continue
            indices.append(int(part) - 1)
        selected: list = []
        for idx in indices:
            if 0 <= idx < len(items):
                selected.append(items[idx].id)
        return selected

    def _parse_multi_choice(self, value: str, count: int) -> list[int]:
        indices: list[int] = []
        for part in value.split(","):
            part = part.strip()
            if not part.isdigit():
                continue
            index = int(part) - 1
            if 0 <= index < count:
                indices.append(index)
        return list(dict.fromkeys(indices))
