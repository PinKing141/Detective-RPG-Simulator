from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from textual.app import App, ComposeResult
from textual.containers import Vertical, VerticalScroll
from textual.widgets import Input, RichLog, Static

from noir import config
from noir.cases.truth_generator import generate_case
from noir.deduction.board import DeductionBoard, MethodType, TimeBucket
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
from noir.investigation.results import ActionOutcome, InvestigationState
from noir.presentation.evidence import CCTVReport, ForensicsResult, WitnessStatement
from noir.presentation.projector import project_case
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
        self.rng = Rng(self.seed)
        self.truth, self.case_facts = generate_case(self.rng, case_id=self.case_id)
        self.presentation = project_case(self.truth, self.rng.fork("projection"))
        self.state = InvestigationState()
        self.board = DeductionBoard()
        self.prompt_state: PromptState | None = None
        self.selected_evidence_id = None
        self.last_result = None

        self.location_id = self.case_facts["crime_scene_id"]
        self.item_id = self.case_facts["weapon_id"]

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static("", id="header")
            yield RichLog(id="log", wrap=True)
            yield VerticalScroll(Static("", id="detail_view", expand=True), id="detail")
            yield Static(self._menu_text(), id="menu")
            yield Input(placeholder="Enter command (1-6 or q)...", id="command")

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
            "6) Arrest"
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
            f"Pressure {self.state.pressure}/{PRESSURE_LIMIT}"
        )
        hypothesis_line = self._hypothesis_line()
        supports_line = self._supports_line()
        lines = [time_line, hypothesis_line]
        if supports_line:
            lines.append(supports_line)
        header.update("\n".join(lines))

    def _refresh_detail(self, result) -> None:
        detail = self.query_one("#detail_view", Static)
        lines: list[str] = []
        lines.append("Detail")
        lines.append(f"Evidence known: {len(self.state.knowledge.known_evidence)}/{len(self.presentation.evidence)}")
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
        base = f"{index}) {item.summary} ({item.evidence_type}, {item.confidence})"
        if isinstance(item, ForensicsResult):
            return f"{base} - suggests {item.method_category}"
        return base

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
        return lines

    def _selected_evidence(self):
        if self.selected_evidence_id is None:
            return None
        for item in self.presentation.evidence:
            if item.id == self.selected_evidence_id:
                return item
        return None

    def _format_method(self, method: MethodType) -> str:
        mapping = {
            MethodType.SHARP: "Sharp force",
            MethodType.BLUNT: "Blunt force",
            MethodType.POISON: "Poison",
            MethodType.UNKNOWN: "Unknown",
        }
        return mapping.get(method, method.value)

    def _format_time_bucket(self, bucket: TimeBucket) -> str:
        return bucket.value.capitalize()

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

    def _witness_note(self, item: WitnessStatement) -> str | None:
        if item.observed_person_ids:
            person_id = item.observed_person_ids[0]
            person = self.truth.people.get(person_id)
            name = person.name if person else "someone"
            return f"Detective note: Supports presence near the scene ({name})."
        return "Detective note: Supports the timeline near the scene."

    def _cctv_note(self, item: CCTVReport) -> str | None:
        if item.observed_person_ids:
            person_id = item.observed_person_ids[0]
            person = self.truth.people.get(person_id)
            name = person.name if person else "someone"
            return f"Detective note: Footage supports presence near the scene ({name})."
        return "Detective note: Footage supports movement near the scene."

    def _hypothesis_line(self) -> str:
        if self.board.hypothesis is None:
            return "Hypothesis: (none)"
        suspect = self.truth.people.get(self.board.hypothesis.suspect_id)
        suspect_name = suspect.name if suspect else "Unknown"
        method = self._format_method(self.board.hypothesis.method)
        time_bucket = self._format_time_bucket(self.board.hypothesis.time_bucket)
        evd_count = len(self.board.hypothesis.evidence_ids)
        return f"Hypothesis: {suspect_name} | {method} | {time_bucket} | Evd: {evd_count}"

    def _supports_line(self) -> str | None:
        if self.board.hypothesis is None:
            return None
        evidence_ids = set(self.board.hypothesis.evidence_ids)
        counts = {"strong": 0, "med": 0, "weak": 0}
        for item in self.presentation.evidence:
            if item.id not in evidence_ids:
                continue
            confidence = getattr(item, "confidence", None)
            if confidence is None:
                continue
            value = confidence.value if hasattr(confidence, "value") else str(confidence)
            if value == "strong":
                counts["strong"] += 1
            elif value == "medium":
                counts["med"] += 1
            elif value == "weak":
                counts["weak"] += 1
        if sum(counts.values()) == 0:
            return None
        return f"Supports: strong {counts['strong']} / med {counts['med']} / weak {counts['weak']}"

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
        self._refresh_detail(None)
        if validation.is_correct_suspect and validation.probable_cause:
            self._write("Case concluded.")

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
            self.prompt_state.step = "hyp_method"
            self.prompt_state.options = list(MethodType)
            self._write("Choose method:")
            for idx, method in enumerate(self.prompt_state.options, start=1):
                self._write(f"{idx}) {self._format_method(method)}")
            return
        if step == "hyp_method":
            selection = self._parse_choice(value, len(self.prompt_state.options))
            if selection is None:
                self._write("Invalid choice.")
                return
            self.prompt_state.data["method"] = self.prompt_state.options[selection]
            self.prompt_state.step = "hyp_time"
            self.prompt_state.options = list(TimeBucket)
            self._write("Choose time of day:")
            for idx, bucket in enumerate(self.prompt_state.options, start=1):
                self._write(f"{idx}) {self._format_time_bucket(bucket)}")
            return
        if step == "hyp_time":
            selection = self._parse_choice(value, len(self.prompt_state.options))
            if selection is None:
                self._write("Invalid choice.")
                return
            self.prompt_state.data["time_bucket"] = self.prompt_state.options[selection]
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
                data["method"],
                data["time_bucket"],
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
