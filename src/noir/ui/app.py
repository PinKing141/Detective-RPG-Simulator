from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import time
from typing import Any

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import Input, ListItem, ListView, RichLog, Static

from noir import config
from noir.cases.archetypes import CaseArchetype
from noir.cases.truth_generator import generate_case
from noir.deduction.board import ClaimType, DeductionBoard
from noir.deduction.scoring import support_for_claims
from noir.deduction.validation import validate_hypothesis
from noir.domain.enums import RoleTag
from noir.investigation.actions import (
    arrest,
    follow_neighbor_lead,
    interview,
    rossmo_lite,
    request_cctv,
    set_profile,
    set_hypothesis,
    submit_forensics,
    tech_sweep,
    visit_scene,
)
from noir.investigation.costs import ActionType, PRESSURE_LIMIT, TIME_LIMIT
from noir.investigation.dialog_graph import load_default_interview_graph
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
from noir.narrative.debriefs import build_post_arrest_statement
from noir.nemesis import PatternTracker
from noir.presentation.evidence import (
    CCTVReport,
    ForensicObservation,
    ForensicsResult,
    WitnessStatement,
)
from noir.presentation.projector import project_case
from noir.profiling.profile import (
    ProfileDrive,
    ProfileMobility,
    ProfileOrganization,
    format_profile_lines,
)
from noir.profiling.summary import build_profiling_summary, format_profiling_summary
from noir.util.rng import Rng
from noir.util.grammar import normalize_line
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
        ("a", "focus_actions", "Focus actions"),
        ("l", "focus_list", "Focus list"),
        ("d", "focus_detail", "Focus detail"),
        ("w", "focus_log", "Focus wire"),
        ("i", "focus_input", "Focus input"),
        ("b", "show_briefing", "Briefing"),
        ("c", "show_case_file", "Case file"),
        ("g", "toggle_gaze", "Toggle gaze"),
        ("escape", "exit_app", "Exit"),
        ("f6", "focus_log", "Focus log"),
        ("f7", "focus_detail", "Focus detail"),
        ("f8", "focus_input", "Focus input"),
        ("left", "prev_tab", "Previous tab"),
        ("right", "next_tab", "Next tab"),
        ("[", "prev_tab", "Previous tab"),
        ("]", "next_tab", "Next tab"),
    ]
    CSS = """
    Screen {
        layout: vertical;
    }
    #header {
        height: auto;
        padding: 1 1;
    }
    #tabs {
        height: auto;
        padding: 0 1;
        color: $text-muted;
    }
    #body {
        height: 1fr;
    }
    #briefing {
        height: 1fr;
    }
    #briefing_banner {
        height: auto;
        padding: 1 1 0 1;
        text-style: bold;
        text-align: center;
    }
    #briefing_title {
        height: auto;
        padding: 0 1 0 1;
    }
    #briefing_meta {
        height: auto;
        padding: 0 1;
    }
    #briefing_snapshot, #briefing_leads {
        width: 1fr;
        border: solid $secondary;
        padding: 0 1;
    }
    #briefing_scroll {
        height: 1fr;
        border: solid $secondary;
        padding: 0 1;
    }
    #briefing_hint {
        height: auto;
        padding: 0 1 1 1;
        color: $text-muted;
    }
    #case_file {
        height: 1fr;
    }
    #case_list {
        width: 40%;
        border: solid $secondary;
        padding: 0 0;
    }
    #detail_view {
        width: 100%;
    }
    #detail {
        width: 60%;
        border: solid $secondary;
        padding: 0 1;
    }
    #wire {
        height: 4;
        border: solid $secondary;
        padding: 0 1;
    }
    #actions {
        height: 9;
        border: solid $secondary;
        padding: 0 0;
    }
    ListItem.disabled {
        color: $text-muted;
    }
    #command {
        height: 3;
        padding: 0 1;
        display: none;
    }
    """

    def __init__(
        self,
        seed: int | None = None,
        case_id: str | None = None,
        world_db: Path | None = None,
        case_archetype: CaseArchetype | None = None,
        gaze_mode: GazeMode | None = None,
        reset_world: bool = False,
    ) -> None:
        super().__init__()
        self.seed = seed if seed is not None else config.SEED
        self.case_id = case_id
        self.base_rng = Rng(self.seed)
        self.case_index = 1
        self.world_store = WorldStore(world_db) if world_db else None
        if self.world_store and reset_world:
            self.world_store.reset_world_state()
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
        self.prompt_title: str | None = None
        self.prompt_lines: list[str] = []
        self.selected_evidence_id = None
        self.last_result = None
        self.profile_lines: list[str] = []
        self._pending_briefing: list[str] = []
        self._pending_intro: list[str] = []
        self._has_mounted = False
        self._exit_armed_until = 0.0
        self._tab_order = [
            ("evidence", "Case File"),
            ("leads", "Leads"),
            ("pois", "Scene"),
            ("profile", "Profile"),
            ("pattern", "Pattern"),
            ("summary", "Debrief"),
        ]
        self.active_tab = "evidence"
        self.view_mode = "briefing"
        self.season = 1
        self.episode_code = ""
        self.episode_title = ""
        self.briefing_title = "Briefing"
        self.briefing_lines: list[str] = []
        self._briefing_action_payloads: list[dict[str, Any]] = []
        self._case_payloads: list[dict[str, Any]] = []
        self._action_payloads: list[dict[str, Any]] = []
        self._selected_case_index = 0
        self._suppress_list_events = False
        self.pattern_tracker = PatternTracker.from_library(self.base_rng.fork("pattern"))
        self.last_pattern_addendum = None
        self.last_post_arrest_statement: list[str] = []
        self.last_post_arrest_case_id: str | None = None

        self._start_case(self.case_index, case_id_override=self.case_id)

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static("", id="header")
            yield Static("", id="tabs")
            with Vertical(id="briefing"):
                yield Static("", id="briefing_banner")
                yield Static("", id="briefing_title")
                with Horizontal(id="briefing_meta"):
                    yield Static("", id="briefing_leads")
                    yield Static("", id="briefing_snapshot")
                yield VerticalScroll(Static("", id="briefing_body", expand=True), id="briefing_scroll")
                yield Static(
                    "Press any key to begin. Debrief available after case close.",
                    id="briefing_hint",
                )
            with Vertical(id="case_file"):
                with Horizontal(id="body"):
                    yield ListView(id="case_list")
                    yield VerticalScroll(Static("", id="detail_view", expand=True), id="detail")
                yield RichLog(id="wire", wrap=True)
                yield ListView(id="actions")
                yield Input(placeholder="Enter command (1-11 or q)...", id="command")

    def on_mount(self) -> None:
        self._has_mounted = True
        self._refresh_header()
        self._refresh_tabs()
        self._refresh_lists()
        self._set_view_mode(self.view_mode)
        if self._pending_intro:
            for line in self._pending_intro:
                self._write(line)
            self._pending_intro = []
        self._write(f"Case {self.truth.case_id} started.")
        if self._pending_briefing:
            for line in self._pending_briefing:
                self._write(line)
            self._pending_briefing = []
        self._write("Use the Actions list (Enter) or press I/F8 to type a number. Type 'q' to quit.")
        self._write("Focus: A actions, L list, D detail, W wire, I input (Tab cycles). G toggles gaze.")
        if self.view_mode == "case_file":
            self.query_one("#actions", ListView).focus()

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

    def on_key(self, event) -> None:
        if self.view_mode != "briefing" or self.prompt_state is not None:
            return
        if event.key == "q":
            self.exit()
            return
        if event.key == "escape":
            self.action_exit_app()
            return
        if event.key in {"tab", "shift+tab"}:
            return
        if event.key.startswith("f"):
            return
        self._set_view_mode("case_file")

    def action_exit_app(self) -> None:
        now = time.monotonic()
        if now <= self._exit_armed_until:
            self.exit()
            return
        self._exit_armed_until = now + 2.0
        message = "Press ESC again to quit."
        if self.view_mode == "briefing":
            if message not in self.briefing_lines:
                self.briefing_lines.append(message)
                if self._has_mounted:
                    self._refresh_briefing()
        self._write(message)

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        if self._suppress_list_events:
            return
        list_view = getattr(event, "list_view", event.control)
        if list_view.id == "actions":
            index = list_view.index
            if index is None or index >= len(self._action_payloads):
                return
            payload = self._action_payloads[index]
            if not payload.get("enabled", True):
                self._write("Action unavailable.")
                return
            self._handle_command(payload["cmd"])
            return
        if list_view.id == "case_list":
            index = list_view.index
            if index is None or index >= len(self._case_payloads):
                return
            self._selected_case_index = index
            payload = self._case_payloads[index]
            if payload.get("type") == "evidence":
                self.selected_evidence_id = payload.get("id")
            self._refresh_detail(None)

    def _write(self, message: str) -> None:
        log = self.query_one("#wire", RichLog)
        log.write(message)

    def action_focus_log(self) -> None:
        self.query_one("#wire", RichLog).focus()

    def action_focus_detail(self) -> None:
        self.query_one("#detail", VerticalScroll).focus()

    def action_focus_actions(self) -> None:
        self.query_one("#actions", ListView).focus()

    def action_focus_list(self) -> None:
        self.query_one("#case_list", ListView).focus()

    def action_focus_input(self) -> None:
        self.query_one("#command", Input).focus()

    def action_show_briefing(self) -> None:
        self._set_view_mode("briefing")

    def action_show_case_file(self) -> None:
        self._set_view_mode("case_file")

    def action_toggle_gaze(self) -> None:
        if self.gaze_mode == GazeMode.FORENSIC:
            self.gaze_mode = GazeMode.BEHAVIORAL
        else:
            self.gaze_mode = GazeMode.FORENSIC
        self._write(f"Gaze set to {gaze_label(self.gaze_mode)}.")
        self._refresh_header()
        self._refresh_detail(None)

    def action_prev_tab(self) -> None:
        index = self._tab_index(self.active_tab)
        self.active_tab = self._tab_order[index - 1][0]
        self._refresh_tabs()
        self._refresh_lists()

    def action_next_tab(self) -> None:
        index = self._tab_index(self.active_tab)
        self.active_tab = self._tab_order[(index + 1) % len(self._tab_order)][0]
        self._refresh_tabs()
        self._refresh_lists()

    def _tab_index(self, key: str) -> int:
        for idx, (tab_key, _) in enumerate(self._tab_order):
            if tab_key == key:
                return idx
        return 0

    def _refresh_tabs(self) -> None:
        tabs = self.query_one("#tabs", Static)
        labels = []
        for key, label in self._tab_order:
            if key == self.active_tab:
                labels.append(f"[bold reverse]{label}[/]")
            else:
                labels.append(label)
        tabs.update("Tabs: " + "  ".join(labels))

    def _refresh_lists(self) -> None:
        self._refresh_briefing()
        self._refresh_case_list()
        self._refresh_actions()
        self._refresh_detail(None)

    def _set_view_mode(self, mode: str) -> None:
        if mode not in {"briefing", "case_file"}:
            mode = "case_file"
        self.view_mode = mode
        if not self._has_mounted:
            return
        briefing = self.query_one("#briefing", Vertical)
        case_file = self.query_one("#case_file", Vertical)
        tabs = self.query_one("#tabs", Static)
        briefing.display = mode == "briefing"
        case_file.display = mode == "case_file"
        tabs.display = mode == "case_file"
        if mode == "briefing":
            self._refresh_briefing()
            self.query_one("#briefing_scroll", VerticalScroll).focus()
        else:
            self.query_one("#actions", ListView).focus()

    def _refresh_briefing(self) -> None:
        if not self._has_mounted:
            return
        banner = self.query_one("#briefing_banner", Static)
        title = self.query_one("#briefing_title", Static)
        body = self.query_one("#briefing_body", Static)
        title.update(self.briefing_title or "Briefing")
        banner_text = "EPISODE"
        if self.episode_code and self.episode_title:
            banner_text = f"EPISODE: {self.episode_code} — {self.episode_title}"
        elif self.episode_title:
            banner_text = f"EPISODE: {self.episode_title}"
        rule_len = max(28, len(banner_text) + 8)
        rule = "-" * rule_len
        banner.update(f"{rule}\n{banner_text}\n{rule}")
        snapshot = self.query_one("#briefing_snapshot", Static)
        leads_box = self.query_one("#briefing_leads", Static)
        snapshot_lines = [
            "Case snapshot",
            f"District: {self.district}",
            f"Location: {self.location_name}",
            f"Pressure: {self.state.pressure}/{PRESSURE_LIMIT}",
            f"Trust: {self.state.trust}/{TRUST_LIMIT}",
        ]
        snapshot.update("\n".join(snapshot_lines))
        lead_lines = ["Key leads"]
        lead_count = 0
        for lead in self.state.leads:
            if lead_count >= 2:
                break
            lead_lines.append(f"- {lead.label} (t{lead.deadline})")
            lead_count += 1
        if lead_count == 0:
            lead_lines.append("(none)")
        leads_box.update("\n".join(lead_lines))
        if self.briefing_lines:
            body.update("\n".join(self.briefing_lines))
        else:
            body.update("(no briefing available)")

    def _set_prompt_active(self, active: bool) -> None:
        command = self.query_one("#command", Input)
        log = self.query_one("#wire", RichLog)
        command.display = active
        log.display = not active
        if active:
            command.focus()
        else:
            command.value = ""
            self._clear_prompt_view()
            self.query_one("#actions", ListView).focus()

    def _set_prompt(self, title: str, lines: list[str]) -> None:
        self.prompt_title = title
        self.prompt_lines = lines
        self._refresh_detail(None)

    def _clear_prompt_view(self) -> None:
        self.prompt_title = None
        self.prompt_lines = []
        self._refresh_detail(None)

    def _refresh_header(self) -> None:
        header = self.query_one("#header", Static)
        time_line = (
            f"Case: {self.truth.case_id}  Investigation Time {self.state.time}/{TIME_LIMIT}  "
            f"Pressure {self.state.pressure}/{PRESSURE_LIMIT}  "
            f"Trust {self.state.trust}/{TRUST_LIMIT}  "
            f"Gaze {gaze_label(self.gaze_mode)} (G: toggle)"
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
        if self.prompt_state is not None:
            lines.append(self.prompt_title or "Prompt")
            if self.prompt_lines:
                lines.extend(self.prompt_lines)
            else:
                lines.append("Awaiting selection...")
            lines.append("")
            lines.append("Enter selection in input (I/F8).")
            detail.update("\n".join(lines))
            return
        payload = None
        if self._case_payloads:
            index = min(self._selected_case_index, len(self._case_payloads) - 1)
            payload = self._case_payloads[index]
        if self.active_tab == "evidence":
            lines.append("Evidence detail")
            if payload and payload.get("type") == "evidence":
                evidence_id = payload.get("id")
                item = next(
                    (e for e in self.presentation.evidence if e.id == evidence_id),
                    None,
                )
                if item is not None:
                    detail_lines = self._format_evidence_detail(1, item)
                    if detail_lines and detail_lines[0].startswith("1) "):
                        detail_lines[0] = detail_lines[0][3:]
                    lines.extend(detail_lines)
                else:
                    lines.append("No evidence selected.")
            else:
                lines.append("No evidence selected.")
        elif self.active_tab == "leads":
            lines.append("Lead detail")
            if payload and payload.get("type") == "lead":
                lead = payload.get("lead")
                status = lead.status.value if lead else "unknown"
                lines.append(f"{lead.label} ({status})")
                lines.append(f"Action: {lead.action_hint}")
                lines.append(f"Deadline: t{lead.deadline}")
            elif payload and payload.get("type") == "neighbor_lead":
                lead = payload.get("lead")
                lines.append(payload.get("label", "Neighbor lead"))
                if lead:
                    lines.append(f"Hearing bias: {lead.hearing_bias:.2f}")
            else:
                lines.append("No lead selected.")
        elif self.active_tab == "pois":
            lines.append("Scene detail")
            if payload and payload.get("type") == "poi":
                poi = payload.get("poi")
                status = "visited" if poi.poi_id in self.state.visited_poi_ids else "unvisited"
                lines.append(f"{self._poi_display_label(poi)} ({status})")
                if poi.description:
                    lines.append(normalize_line(poi.description))
                if poi.tags:
                    lines.append(f"Tags: {', '.join(poi.tags[:4])}")
            else:
                lines.append("No scene area selected.")
        elif self.active_tab == "profile":
            lines.extend(self._build_profile_tab_lines())
        elif self.active_tab == "pattern":
            lines.append("Pattern addendum")
            if payload and payload.get("type") == "pattern":
                addendum = payload.get("addendum")
                if addendum:
                    lines.extend(addendum.render())
                else:
                    lines.append("(none)")
            else:
                lines.append("(none)")
        elif self.active_tab == "summary":
            lines.append("Debrief")
            if payload and payload.get("key") == "case":
                lines.append(f"Case: {self.truth.case_id}")
                lines.append(f"District: {self.district}")
                lines.append(f"Location: {self.location_name}")
                scene_layout = self.case_facts.get("scene_layout")
                if isinstance(scene_layout, dict):
                    mode = scene_layout.get("mode")
                    if mode:
                        lines.append(f"Scene mode: {mode}")
                if self.last_pattern_addendum:
                    lines.append(f"Pattern: {self.last_pattern_addendum.label}")
            elif payload and payload.get("key") == "last_action":
                last_result = result or self.last_result
                if last_result is None:
                    lines.append("(no actions yet)")
                else:
                    lines.append(f"Last action: {last_result.action}")
                    lines.append(last_result.summary)
                    for note in last_result.notes:
                        lines.append(f"- {note}")
            elif payload and payload.get("key") == "pattern":
                lines.append("Pattern addendum")
                if self.last_pattern_addendum:
                    lines.extend(self.last_pattern_addendum.render())
                else:
                    lines.append("(none)")
            elif payload and payload.get("key") == "world":
                context_lines = self.world.context_lines(self.district, self.location_name)
                if context_lines:
                    lines.extend(context_lines)
                else:
                    lines.append("(no world notes)")
            elif payload and payload.get("key") == "post_arrest":
                if self.last_post_arrest_statement:
                    lines.append(f"Post-arrest statement ({self.last_post_arrest_case_id})")
                    lines.extend(self.last_post_arrest_statement)
                else:
                    lines.append("(none)")
            else:
                lines.append("(select a summary item)")
        detail.update("\n".join(lines))

    def _format_evidence_summary(self, item) -> str:
        summary = normalize_line(item.summary)
        return f"{summary} ({self._format_confidence(item.confidence)})"

    def _refresh_case_list(self) -> None:
        list_view = self.query_one("#case_list", ListView)
        payloads: list[dict[str, Any]] = []

        if self.active_tab == "evidence":
            known_ids = list(self.state.knowledge.known_evidence)
            for evidence_id in known_ids:
                item = next(
                    (e for e in self.presentation.evidence if e.id == evidence_id),
                    None,
                )
                if item is None:
                    continue
                payloads.append(
                    {
                        "type": "evidence",
                        "id": evidence_id,
                        "label": self._format_evidence_summary(item),
                    }
                )
        elif self.active_tab == "leads":
            for lead in self.state.leads:
                status = lead.status.value
                payloads.append(
                    {
                        "type": "lead",
                        "lead": lead,
                        "label": f"{lead.label} ({status})",
                    }
                )
            for lead in self.state.neighbor_leads:
                payloads.append(
                    {
                        "type": "neighbor_lead",
                        "lead": lead,
                        "label": f"Neighbor: {format_neighbor_lead(lead)}",
                    }
                )
        elif self.active_tab == "pois":
            for poi in self.state.scene_pois:
                status = "visited" if poi.poi_id in self.state.visited_poi_ids else "unvisited"
                payloads.append(
                    {
                        "type": "poi",
                        "poi": poi,
                        "label": f"{self._poi_display_label(poi)} ({status})",
                    }
                )
        elif self.active_tab == "profile":
            profile_lines = self._build_profile_tab_lines()
            for idx, line in enumerate(profile_lines):
                payloads.append(
                    {
                        "type": "profile",
                        "index": idx,
                        "label": line,
                    }
                )
        elif self.active_tab == "pattern":
            if self.last_pattern_addendum:
                payloads = [
                    {
                        "type": "pattern",
                        "label": f"Case {self.last_pattern_addendum.case_id}",
                        "addendum": self.last_pattern_addendum,
                    }
                ]
            else:
                payloads = [{"type": "empty", "label": "(none)"}]
        elif self.active_tab == "summary":
            payloads = [
                {"type": "summary", "key": "case", "label": "Case status"},
                {"type": "summary", "key": "last_action", "label": "Last action"},
                {"type": "summary", "key": "pattern", "label": "Pattern addendum"},
                {"type": "summary", "key": "world", "label": "World context"},
            ]
            if self.last_post_arrest_statement:
                payloads.append(
                    {
                        "type": "summary",
                        "key": "post_arrest",
                        "label": "Post-arrest statement",
                    }
                )

        if not payloads:
            payloads = [{"type": "empty", "label": "(none)"}]

        self._suppress_list_events = True
        list_view.clear()
        self._case_payloads = payloads
        for payload in payloads:
            item = ListItem(Static(payload["label"]))
            if payload.get("type") == "empty":
                item.add_class("disabled")
            list_view.append(item)
        if payloads:
            index = min(self._selected_case_index, len(payloads) - 1)
            self._selected_case_index = index
            list_view.index = index
        self._suppress_list_events = False

    def _build_action_items(self) -> list[dict[str, Any]]:
        has_witness = any(
            RoleTag.WITNESS in person.role_tags for person in self.truth.people.values()
        )
        has_evidence = bool(self.state.knowledge.known_evidence)
        has_hypothesis = self.board.hypothesis is not None
        has_neighbor = bool(self.state.neighbor_leads)
        return [
            {"cmd": "1", "label": "Visit scene", "enabled": True},
            {"cmd": "2", "label": "Interview witness", "enabled": has_witness},
            {"cmd": "3", "label": "Request CCTV", "enabled": True},
            {"cmd": "4", "label": "Submit forensics", "enabled": True},
            {"cmd": "5", "label": "Set hypothesis", "enabled": has_evidence},
            {"cmd": "6", "label": "Profiling summary", "enabled": True},
            {"cmd": "7", "label": "Arrest suspect", "enabled": has_hypothesis},
            {"cmd": "8", "label": "Follow neighbor lead", "enabled": has_neighbor},
            {"cmd": "9", "label": "Set profile", "enabled": has_evidence},
            {"cmd": "10", "label": "Analyst: Rossmo-lite", "enabled": True},
            {"cmd": "11", "label": "Analyst: Tech sweep", "enabled": True},
        ]

    def _refresh_actions(self) -> None:
        list_view = self.query_one("#actions", ListView)
        self._action_payloads = self._build_action_items()
        self._suppress_list_events = True
        list_view.clear()
        for payload in self._action_payloads:
            item = ListItem(Static(payload["label"]))
            if not payload["enabled"]:
                item.add_class("disabled")
            list_view.append(item)
        if self._action_payloads:
            list_view.index = 0
        self._suppress_list_events = False

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
            InterviewApproach.THEME: "Motive framing",
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

    def _profile_org_label(self, organization: ProfileOrganization) -> str:
        mapping = {
            ProfileOrganization.ORGANIZED: "Organized",
            ProfileOrganization.DISORGANIZED: "Disorganized",
            ProfileOrganization.MIXED: "Mixed",
            ProfileOrganization.UNKNOWN: "Unknown",
        }
        return mapping.get(organization, organization.value)

    def _profile_drive_label(self, drive: ProfileDrive) -> str:
        mapping = {
            ProfileDrive.VISIONARY: "Visionary",
            ProfileDrive.MISSION: "Mission-oriented",
            ProfileDrive.HEDONISTIC: "Hedonistic",
            ProfileDrive.POWER_CONTROL: "Power/Control",
            ProfileDrive.UNKNOWN: "Unknown",
        }
        return mapping.get(drive, drive.value)

    def _profile_mobility_label(self, mobility: ProfileMobility) -> str:
        mapping = {
            ProfileMobility.MARAUDER: "Marauder (local)",
            ProfileMobility.COMMUTER: "Commuter",
            ProfileMobility.UNKNOWN: "Unknown",
        }
        return mapping.get(mobility, mobility.value)

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

    def _wire_evidence_line(self, item) -> str:
        confidence = self._format_confidence(item.confidence)
        label = normalize_line(item.summary)
        extra = ""
        if isinstance(item, WitnessStatement):
            if item.observed_person_ids:
                person = self.truth.people.get(item.observed_person_ids[0])
                if person:
                    extra = person.name
        elif isinstance(item, CCTVReport):
            if item.observed_person_ids:
                person = self.truth.people.get(item.observed_person_ids[0])
                if person:
                    extra = person.name
        elif isinstance(item, ForensicObservation):
            poi_label = self._poi_label_for(item.poi_id)
            if poi_label:
                extra = poi_label
        if extra:
            return f"- New evidence: {label} ({confidence}) - {extra}"
        return f"- New evidence: {label} ({confidence})"

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
            description = normalize_line(poi.description)
            return f"{label}: {description}"
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

    def _build_profile_tab_lines(self) -> list[str]:
        lines = ["Working profile"]
        lines.extend(format_profile_lines(self.state.profile, self.presentation.evidence))
        lines.append("")
        lines.append("Profiling summary")
        if self.profile_lines:
            lines.extend(self.profile_lines)
        else:
            lines.append("(none)")
        lines.append("")
        lines.append("Analyst notes")
        if self.state.analyst_notes:
            lines.extend(self.state.analyst_notes)
        else:
            lines.append("(none)")
        return lines

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
                lines = ["Choose a scene area to inspect:"]
                for idx, poi in enumerate(unvisited, start=1):
                    lines.append(f"{idx}) {self._poi_display_line(poi)}")
                self._set_prompt("Scene inspection", lines)
                self._set_prompt_active(True)
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
        if value == "8":
            if not self.state.neighbor_leads:
                self._write("No neighbor leads available.")
                return
            if len(self.state.neighbor_leads) == 1:
                lead = self.state.neighbor_leads[0]
                result = follow_neighbor_lead(
                    self.truth,
                    self.presentation,
                    self.state,
                    self.location_id,
                    lead,
                )
                self._apply_action_result(result)
                return
            self.prompt_state = PromptState(
                step="neighbor_lead", options=list(self.state.neighbor_leads)
            )
            lines = ["Choose a neighbor lead:"]
            for idx, lead in enumerate(self.prompt_state.options, start=1):
                lines.append(f"{idx}) {format_neighbor_lead(lead)}")
            self._set_prompt("Neighbor lead", lines)
            self._set_prompt_active(True)
            return
        if value == "9":
            self._start_profile_prompt()
            return
        if value == "10":
            mobility = (
                self.state.profile.mobility
                if self.state.profile is not None
                else ProfileMobility.UNKNOWN
            )
            if mobility == ProfileMobility.UNKNOWN:
                self.prompt_state = PromptState(
                    step="rossmo_assumption",
                    options=list(ProfileMobility),
                )
                lines = ["Assume mobility model:"]
                for idx, option in enumerate(self.prompt_state.options, start=1):
                    lines.append(f"{idx}) {self._profile_mobility_label(option)}")
                self._set_prompt("Rossmo-lite assumption", lines)
                self._set_prompt_active(True)
                return
            result = rossmo_lite(self.truth, self.state, mobility)
            self._apply_action_result(result)
            return
        if value == "11":
            result = tech_sweep(
                self.truth,
                self.presentation,
                self.state,
                self.location_id,
            )
            self._apply_action_result(result)
            return
        self._write("Unknown action.")

    def _apply_action_result(self, result) -> None:
        autonomy_notes = apply_autonomy(self.state, self.world, self.district)
        if autonomy_notes:
            result.notes.extend(autonomy_notes)
        if result.action in {ActionType.SET_HYPOTHESIS, ActionType.SET_PROFILE} and result.outcome == ActionOutcome.SUCCESS:
            self._write(
                f"{result.summary} (+{result.time_cost} time, +{result.pressure_cost} pressure)"
            )
        else:
            self._write(f"[{result.action}] {result.summary}")
        for item in result.revealed:
            self._write(self._wire_evidence_line(item))
        for note in result.notes:
            self._write(f"- {note}")
        if result.revealed:
            self.selected_evidence_id = result.revealed[0].id
        elif self.selected_evidence_id is None and self.state.knowledge.known_evidence:
            self.selected_evidence_id = self.state.knowledge.known_evidence[0]
        self.last_result = result
        self._refresh_header()
        self._refresh_lists()

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
        debrief_rng = self.base_rng.fork(f"debrief-{self.case_index}")
        debrief_lines = build_post_arrest_statement(
            debrief_rng, self.truth, self.board, validation, outcome.arrest_result
        )
        debrief_notes = []
        if debrief_lines:
            debrief_notes = [f"Post-arrest: {debrief_lines[0]}"]
        case_end_tick = self.case_start_tick + self.state.time
        world_notes = self.world.apply_case_outcome(
            outcome,
            self.truth.case_id,
            self.seed,
            self.district,
            self.location_name,
            self.case_start_tick,
            case_end_tick,
            extra_notes=debrief_notes,
        )
        if self.world_store:
            self.world_store.save_world_state(self.world)
            self.world_store.record_case(self.world.case_history[-1])
        for note in world_notes:
            self._write(f"- {note}")
        end_rng = self.base_rng.fork(f"end-{self.case_index}")
        for line in build_end_tag(end_rng, outcome.arrest_result.value):
            self._write(line)
        self.last_post_arrest_statement = debrief_lines
        self.last_post_arrest_case_id = self.truth.case_id
        if self.last_post_arrest_statement:
            self._write("Post-arrest statement filed.")
        pattern_addendum = self.pattern_tracker.record_case(
            self.truth.case_id, self.case_index
        )
        if pattern_addendum:
            self.last_pattern_addendum = pattern_addendum
            self._write("Pattern addendum filed.")
        else:
            self.last_pattern_addendum = None
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
        pattern_plan = self.pattern_tracker.plan_case(case_id, case_index)
        self.truth.case_meta["pattern_plan"] = pattern_plan.to_case_meta()
        self.presentation = project_case(self.truth, case_rng.fork("projection"))
        self.case_start_tick = self.world.tick
        location = self.truth.locations.get(self.case_facts["crime_scene_id"])
        self.district = location.district if location else "unknown"
        self.location_name = location.name if location else "unknown"
        intro_lines: list[str] = []
        if case_index == 1:
            intro_lines.extend(build_previously_on(self.world))
        episode_rng = self.base_rng.fork(f"episode-{case_index}")
        case_archetype = self.case_facts.get("case_archetype") if isinstance(self.case_facts, dict) else None
        episode_kind = "copycat" if case_archetype == CaseArchetype.PATTERN.value else "normal"
        tag_map = {
            CaseArchetype.PRESSURE.value: ["pressure", "escalation"],
            CaseArchetype.PATTERN.value: ["recurrence", "copycat"],
            CaseArchetype.CHARACTER.value: ["identity", "personal"],
            CaseArchetype.FORESHADOWING.value: ["recurrence", "escalation"],
        }
        case_tags = tag_map.get(case_archetype, [])
        episode_title = build_episode_title(
            episode_rng,
            self.location_name,
            self.district,
            episode_kind=episode_kind,
            case_tags=case_tags,
            title_state=self.world.episode_titles,
        )
        self.episode_code = f"S{self.season}E{case_index}"
        self.episode_title = episode_title
        intro_lines.append(f"Episode: {self.episode_code} — {episode_title}")
        intro_lines.extend(build_cold_open(episode_rng, self.location_name))
        intro_lines.extend(build_partner_line(episode_rng))
        briefing_lines = [line for line in intro_lines if not line.startswith("Episode:")]
        if intro_lines:
            if self._has_mounted:
                for line in intro_lines:
                    self._write(line)
            else:
                self._pending_intro = list(intro_lines)
        self.case_modifiers = self.world.case_start_modifiers(
            self.district, self.location_name
        )
        briefing_lines.extend(self.case_modifiers.briefing_lines)
        if self.last_pattern_addendum:
            briefing_lines.append(
                f"Pattern file updated: {self.last_pattern_addendum.label}."
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
        self.briefing_title = "CASE BRIEFING"
        self.briefing_lines = briefing_lines
        self.view_mode = "briefing"
        if self._has_mounted:
            self._refresh_tabs()
            self._refresh_lists()
            self._set_view_mode(self.view_mode)

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
            lines = ["Choose interview approach:"]
            for idx, approach in enumerate(self.prompt_state.options, start=1):
                lines.append(f"{idx}) {self._interview_approach_label(approach)}")
            self._set_prompt("Interview approach", lines)
            self._set_prompt_active(True)
            return None
        self.prompt_state = PromptState(step="interview_witness", options=witnesses)
        lines = ["Choose a witness:"]
        for idx, person in enumerate(witnesses, start=1):
            lines.append(f"{idx}) {person.name}")
        self._set_prompt("Select witness", lines)
        self._set_prompt_active(True)
        return None

    def _set_interview_dialog_prompt(
        self,
        witness_id,
        approach: InterviewApproach,
        theme: InterviewTheme | None,
    ) -> bool:
        graph = load_default_interview_graph()
        if graph is None:
            return False
        interview_state = self.state.interviews.get(str(witness_id)) if self.state else None
        node_id = graph.root_node_id
        if interview_state and interview_state.dialog_node_id:
            node_id = interview_state.dialog_node_id
        if not graph.has_node(node_id):
            node_id = graph.root_node_id
        node = graph.node(node_id)
        if not node.choices:
            node = graph.node(graph.root_node_id)
        if not node.choices:
            return False
        self.prompt_state = PromptState(
            step="interview_dialog",
            data={"witness_id": witness_id, "approach": approach, "theme": theme},
            options=list(node.choices),
        )
        lines = ["Choose a prompt:"]
        for idx, choice in enumerate(self.prompt_state.options, start=1):
            lines.append(f"{idx}) {choice.text}")
        self._set_prompt("Interview prompt", lines)
        self._set_prompt_active(True)
        return True

    def _start_hypothesis_prompt(self) -> None:
        self.board.sync_from_state(self.state)
        suspects = [p for p in self.truth.people.values() if RoleTag.OFFENDER in p.role_tags]
        if not suspects:
            self._write("No suspect available.")
            return
        self.prompt_state = PromptState(step="hyp_suspect", options=suspects)
        lines = ["Choose a suspect:"]
        for idx, person in enumerate(suspects, start=1):
            lines.append(f"{idx}) {person.name}")
        self._set_prompt("Hypothesis suspect", lines)
        self._set_prompt_active(True)

    def _start_profile_prompt(self) -> None:
        options = list(ProfileOrganization)
        self.prompt_state = PromptState(step="profile_org", options=options)
        lines = ["Choose organization style:"]
        for idx, org in enumerate(options, start=1):
            lines.append(f"{idx}) {self._profile_org_label(org)}")
        self._set_prompt("Working profile", lines)
        self._set_prompt_active(True)

    def _handle_prompt_input(self, value: str) -> None:
        if self.prompt_state is None:
            return
        if value.lower() == "q":
            self._write("Prompt cancelled.")
            self.prompt_state = None
            self._set_prompt_active(False)
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
            lines = ["Choose interview approach:"]
            for idx, approach in enumerate(self.prompt_state.options, start=1):
                lines.append(f"{idx}) {self._interview_approach_label(approach)}")
            self._set_prompt("Interview approach", lines)
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
                lines = ["Choose motive framing:"]
                for idx, theme in enumerate(self.prompt_state.options, start=1):
                    lines.append(f"{idx}) {self._interview_theme_label(theme)}")
                self._set_prompt("Motive framing", lines)
                return
            witness_id = self.prompt_state.data["witness_id"]
            if self._set_interview_dialog_prompt(witness_id, approach, None):
                return
            self.prompt_state = None
            self._set_prompt_active(False)
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
            if self._set_interview_dialog_prompt(witness_id, approach, theme):
                return
            self.prompt_state = None
            self._set_prompt_active(False)
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
        if step == "interview_dialog":
            selection = self._parse_choice(value, len(self.prompt_state.options))
            if selection is None:
                self._write("Invalid choice.")
                return
            witness_id = self.prompt_state.data["witness_id"]
            approach = self.prompt_state.data.get("approach", InterviewApproach.BASELINE)
            theme = self.prompt_state.data.get("theme")
            self.prompt_state = None
            self._set_prompt_active(False)
            result = interview(
                self.truth,
                self.presentation,
                self.state,
                witness_id,
                self.location_id,
                approach=approach,
                theme=theme,
                dialog_choice_index=selection,
            )
            self._apply_action_result(result)
            return
        if step == "neighbor_lead":
            selection = self._parse_choice(value, len(self.prompt_state.options))
            if selection is None:
                self._write("Invalid choice.")
                return
            lead = self.prompt_state.options[selection]
            self.prompt_state = None
            self._set_prompt_active(False)
            result = follow_neighbor_lead(
                self.truth,
                self.presentation,
                self.state,
                self.location_id,
                lead,
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
            self._set_prompt_active(False)
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
        if step == "rossmo_assumption":
            selection = self._parse_choice(value, len(self.prompt_state.options))
            if selection is None:
                self._write("Invalid choice.")
                return
            assumption = self.prompt_state.options[selection]
            self.prompt_state = None
            self._set_prompt_active(False)
            result = rossmo_lite(self.truth, self.state, assumption)
            self._apply_action_result(result)
            return
        if step == "profile_org":
            selection = self._parse_choice(value, len(self.prompt_state.options))
            if selection is None:
                self._write("Invalid choice.")
                return
            self.prompt_state.data["organization"] = self.prompt_state.options[selection]
            self.prompt_state.step = "profile_drive"
            self.prompt_state.options = list(ProfileDrive)
            lines = ["Choose primary drive:"]
            for idx, drive in enumerate(self.prompt_state.options, start=1):
                lines.append(f"{idx}) {self._profile_drive_label(drive)}")
            self._set_prompt("Working profile", lines)
            return
        if step == "profile_drive":
            selection = self._parse_choice(value, len(self.prompt_state.options))
            if selection is None:
                self._write("Invalid choice.")
                return
            self.prompt_state.data["drive"] = self.prompt_state.options[selection]
            self.prompt_state.step = "profile_mobility"
            self.prompt_state.options = list(ProfileMobility)
            lines = ["Choose mobility model:"]
            for idx, mobility in enumerate(self.prompt_state.options, start=1):
                lines.append(f"{idx}) {self._profile_mobility_label(mobility)}")
            self._set_prompt("Working profile", lines)
            return
        if step == "profile_mobility":
            selection = self._parse_choice(value, len(self.prompt_state.options))
            if selection is None:
                self._write("Invalid choice.")
                return
            self.prompt_state.data["mobility"] = self.prompt_state.options[selection]
            evidence_items = [
                item
                for item in self.presentation.evidence
                if item.id in set(self.state.knowledge.known_evidence)
            ]
            self.prompt_state.step = "profile_evidence"
            self.prompt_state.options = evidence_items
            if not evidence_items:
                self._write("No evidence collected yet.")
                self.prompt_state = None
                self._set_prompt_active(False)
                return
            lines = ["Choose 1 to 3 evidence items (comma-separated):"]
            for idx, item in enumerate(evidence_items, start=1):
                detail_lines = self._format_evidence_detail(idx, item)
                lines.extend(detail_lines)
                lines.append("")
            if lines and lines[-1] == "":
                lines.pop()
            self._set_prompt("Profile evidence", lines)
            return
        if step == "profile_evidence":
            evidence_ids = self._parse_indices(value, self.prompt_state.options)
            data = self.prompt_state.data
            self.prompt_state = None
            self._set_prompt_active(False)
            result = set_profile(
                self.state,
                data["organization"],
                data["drive"],
                data["mobility"],
                evidence_ids,
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
            lines = ["Choose 1 to 3 claims (comma-separated):"]
            for idx, claim in enumerate(self.prompt_state.options, start=1):
                lines.append(f"{idx}) {self._format_claim(claim)}")
            self._set_prompt("Hypothesis claims", lines)
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
                self._set_prompt_active(False)
                return
            lines = ["Choose 1 to 3 evidence items (comma-separated):"]
            for idx, item in enumerate(evidence_items, start=1):
                detail_lines = self._format_evidence_detail(idx, item)
                lines.extend(detail_lines)
                lines.append("")
            if lines and lines[-1] == "":
                lines.pop()
            self._set_prompt("Hypothesis evidence", lines)
            return
        if step == "hyp_evidence":
            evidence_ids = self._parse_indices(value, self.prompt_state.options)
            data = self.prompt_state.data
            self.prompt_state = None
            self._set_prompt_active(False)
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
