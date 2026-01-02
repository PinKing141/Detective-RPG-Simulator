from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from textual.app import App, ComposeResult
from textual.containers import Vertical, VerticalScroll
from textual.widgets import Input, RichLog, Static

from noir import config
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
from noir.investigation.leads import LeadStatus, build_leads
from noir.investigation.outcomes import TRUST_LIMIT, apply_case_outcome, resolve_case_outcome
from noir.investigation.results import ActionOutcome, InvestigationState
from noir.presentation.evidence import CCTVReport, ForensicsResult, WitnessStatement
from noir.presentation.projector import project_case
from noir.profiling.summary import build_profiling_summary, format_profiling_summary
from noir.util.rng import Rng


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

    def __init__(self, seed: int | None = None, case_id: str | None = None) -> None:
        super().__init__()
        self.seed = seed if seed is not None else config.SEED
        self.case_id = case_id
        self.base_rng = Rng(self.seed)
        self.case_index = 1
        self.case_history = []
        self.state: InvestigationState | None = None
        self.board = DeductionBoard()
        self.prompt_state: PromptState | None = None
        self.selected_evidence_id = None
        self.last_result = None
        self.profile_lines: list[str] = []

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
        self._write(f"Case {self.truth.case_id} started.")
        self._write("Type a number to choose an action. Type 'q' to quit.")
        self._write("Focus: F6 log, F7 detail, F8 input (Tab cycles focus).")
        self.query_one("#command", Input).focus()

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
            f"Trust {self.state.trust}/{TRUST_LIMIT}"
        )
        lines = [time_line]
        lines.extend(self._hypothesis_lines())
        header.update("\n".join(lines))

    def _refresh_detail(self, result) -> None:
        detail = self.query_one("#detail_view", Static)
        lines: list[str] = []
        lines.append("Detail")
        lines.append(f"Evidence known: {len(self.state.knowledge.known_evidence)}/{len(self.presentation.evidence)}")
        lines.append("Leads:")
        lines.extend(self._lead_lines())
        lines.append("")
        lines.append("Profiling summary:")
        if self.profile_lines:
            lines.extend(self.profile_lines)
        else:
            lines.append("(none)")
        last_result = result or self.last_result
        if last_result is not None:
            lines.append("")
            lines.append(f"Last action: {last_result.action}")
            lines.append(last_result.summary)
            for note in last_result.notes:
                lines.append(f"- {note}")
        lines.append("")
        lines.append("Evidence details:")
        known_ids = list(self.state.knowledge.known_evidence)
        if not known_ids:
            lines.append("(none)")
        else:
            for idx, evidence_id in enumerate(known_ids, start=1):
                item = next(
                    (e for e in self.presentation.evidence if e.id == evidence_id),
                    None,
                )
                if item is None:
                    continue
                if idx > 1:
                    lines.append("")
                lines.extend(self._format_evidence_detail(idx, item))
        detail.update("\n".join(lines))

    def _format_evidence(self, index: int, item) -> str:
        return f"{index}) {item.summary} ({item.evidence_type}, {item.confidence})"

    def _format_evidence_detail(self, index: int, item) -> list[str]:
        if isinstance(item, WitnessStatement):
            lines = [
                f"{index}) Witness statement",
                f"Source: {item.source}",
                f"Time: {self._format_time_phrase(item.reported_time_window)} (estimate)",
                f"Statement: {item.statement}",
            ]
            note = self._witness_note(item)
            if note:
                lines.append(note)
            lines.append(f"Confidence: {self._format_confidence(item.confidence)}")
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
            summary = build_profiling_summary(
                self.presentation, self.state, self.board.hypothesis
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
        if result.action == ActionType.SET_HYPOTHESIS and result.outcome == ActionOutcome.SUCCESS:
            self._write(
                f"{result.summary} (+{result.time_cost} time, +{result.pressure_cost} pressure)"
            )
        else:
            self._write(f"[{result.action}] {result.summary}")
        for item in result.revealed:
            if isinstance(item, WitnessStatement):
                self._write("- New evidence: Witness statement")
                self._write(f"  Time: {self._format_time_phrase(item.reported_time_window)} (estimate)")
                self._write(f"  Statement: {item.statement}")
                note = self._witness_note(item)
                if note:
                    self._write(f"  {note}")
                self._write(f"  Confidence: {self._format_confidence(item.confidence)}")
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
        self.case_history.append(outcome)
        self.state = apply_case_outcome(self.state, outcome)
        self.case_index += 1
        self._start_case(self.case_index)
        self._write(f"New case {self.truth.case_id} started.")
        self._refresh_header()
        self._refresh_detail(None)

    def _start_case(self, case_index: int, case_id_override: str | None = None) -> None:
        case_rng = self.base_rng.fork(f"case-{case_index}")
        case_id = case_id_override or f"case_{self.seed}_{case_index}"
        self.truth, self.case_facts = generate_case(case_rng, case_id=case_id)
        self.presentation = project_case(self.truth, case_rng.fork("projection"))
        current_state = self.state or InvestigationState()
        self.state = InvestigationState(
            pressure=current_state.pressure,
            trust=current_state.trust,
        )
        self.state.leads = build_leads(self.presentation, start_time=self.state.time)
        self.board = DeductionBoard()
        self.prompt_state = None
        self.selected_evidence_id = None
        self.last_result = None
        self.profile_lines = []
        self.location_id = self.case_facts["crime_scene_id"]
        self.item_id = self.case_facts["weapon_id"]

    def _interview_witness(self):
        witnesses = [p for p in self.truth.people.values() if RoleTag.WITNESS in p.role_tags]
        if not witnesses:
            self._write("No witness available.")
            return None
        if len(witnesses) == 1:
            return interview(self.truth, self.presentation, self.state, witnesses[0].id, self.location_id)
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
            self.prompt_state = None
            result = interview(self.truth, self.presentation, self.state, person.id, self.location_id)
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
                    self._write(f"   Time: {self._format_time_phrase(item.reported_time_window)} (estimate)")
                    self._write(f"   Statement: {item.statement}")
                    note = self._witness_note(item)
                    if note:
                        self._write(f"   {note}")
                    self._write(f"   Confidence: {self._format_confidence(item.confidence)}")
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
