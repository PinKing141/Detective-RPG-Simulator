"""Phase 3E nemesis persistence (lightweight, no endgame ops)."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from noir.util.rng import Rng


class NemesisTypology(StrEnum):
    VISIONARY = "visionary"
    MISSION = "mission_oriented"
    HEDONISTIC = "hedonistic"
    POWER_CONTROL = "power_control"


class NemesisComponentType(StrEnum):
    APPROACH = "approach"
    CONTROL = "control"
    METHOD = "method"
    CLEANUP = "cleanup"
    EXIT = "exit"


@dataclass
class NemesisComponent:
    component_type: NemesisComponentType
    value: str
    weight: float
    competence: float
    compromised: bool = False
    avoid_cooldown: int = 0


@dataclass
class NemesisProfile:
    typology: NemesisTypology
    signature_token: str
    signature_staging: str
    signature_message: str
    victimology_bias: str
    comfort_zones: list[str]
    escalation_trait: str
    failure_echo: str | None = None
    counterplay_traits: list[str] = field(default_factory=list)


@dataclass
class NemesisCasePlan:
    is_nemesis_case: bool
    method_category: str | None = None
    visibility: int = 1
    degraded_execution: bool = False
    taunt_style: str | None = None


@dataclass
class NemesisState:
    profile: NemesisProfile
    mo_components: list[NemesisComponent]
    exposure: int = 0
    exposure_baseline: int = 0
    cases_until_next: int = 2
    escalation_cap: int = 3

    def to_dict(self) -> dict:
        return {
            "profile": {
                "typology": self.profile.typology.value,
                "signature_token": self.profile.signature_token,
                "signature_staging": self.profile.signature_staging,
                "signature_message": self.profile.signature_message,
                "victimology_bias": self.profile.victimology_bias,
                "comfort_zones": list(self.profile.comfort_zones),
                "escalation_trait": self.profile.escalation_trait,
                "failure_echo": self.profile.failure_echo,
                "counterplay_traits": list(self.profile.counterplay_traits),
            },
            "mo_components": [
                {
                    "component_type": comp.component_type.value,
                    "value": comp.value,
                    "weight": comp.weight,
                    "competence": comp.competence,
                    "compromised": comp.compromised,
                    "avoid_cooldown": comp.avoid_cooldown,
                }
                for comp in self.mo_components
            ],
            "exposure": self.exposure,
            "exposure_baseline": self.exposure_baseline,
            "cases_until_next": self.cases_until_next,
            "escalation_cap": self.escalation_cap,
        }

    @classmethod
    def from_dict(cls, payload: dict) -> NemesisState:
        profile_data = payload.get("profile", {})
        profile = NemesisProfile(
            typology=NemesisTypology(profile_data.get("typology", NemesisTypology.VISIONARY)),
            signature_token=profile_data.get("signature_token", "token"),
            signature_staging=profile_data.get("signature_staging", "staging"),
            signature_message=profile_data.get("signature_message", "message"),
            victimology_bias=profile_data.get("victimology_bias", "mixed"),
            comfort_zones=list(profile_data.get("comfort_zones", [])),
            escalation_trait=profile_data.get("escalation_trait", "escalate_visibility"),
            failure_echo=profile_data.get("failure_echo"),
            counterplay_traits=list(profile_data.get("counterplay_traits", []) or []),
        )
        components: list[NemesisComponent] = []
        for entry in payload.get("mo_components", []):
            component_type = NemesisComponentType(entry.get("component_type", "method"))
            components.append(
                NemesisComponent(
                    component_type=component_type,
                    value=entry.get("value", ""),
                    weight=float(entry.get("weight", 1.0)),
                    competence=float(entry.get("competence", 0.5)),
                    compromised=bool(entry.get("compromised", False)),
                    avoid_cooldown=int(entry.get("avoid_cooldown", 0)),
                )
            )
        return cls(
            profile=profile,
            mo_components=components,
            exposure=int(payload.get("exposure", 0)),
            exposure_baseline=int(payload.get("exposure_baseline", 0)),
            cases_until_next=int(payload.get("cases_until_next", 2)),
            escalation_cap=int(payload.get("escalation_cap", 3)),
        )


_SIGNATURE_TOKENS = [
    "tarot card",
    "matchbook spine",
    "pressed flower",
    "thread knot",
    "stopped clock",
]
_SIGNATURE_STAGING = [
    "posed",
    "covered",
    "displayed",
    "hidden",
]
_SIGNATURE_MESSAGES = [
    "taunting note",
    "symbolic mark",
    "silent",
]
_VICTIMOLOGY = [
    "low-risk",
    "high-risk",
    "occupational",
    "mixed",
]
_ESCALATION_TRAITS = [
    "taunting",
    "trophy-taking",
    "body movement",
    "public escalation",
]

_APPROACHES = ["lure", "break_in", "ambush"]
_CONTROLS = ["restraints", "surprise", "intimidation"]
_METHODS = ["sharp", "blunt", "poison"]
_CLEANUP = ["none", "wipe", "staging", "arson"]
_EXITS = ["walkaway", "vehicle", "misdirection"]

_ADAPT_COOLDOWN = 2


def create_nemesis_state(rng: Rng, comfort_zones: list[str] | None = None) -> NemesisState:
    typology = rng.choice(list(NemesisTypology))
    profile = NemesisProfile(
        typology=typology,
        signature_token=rng.choice(_SIGNATURE_TOKENS),
        signature_staging=rng.choice(_SIGNATURE_STAGING),
        signature_message=rng.choice(_SIGNATURE_MESSAGES),
        victimology_bias=rng.choice(_VICTIMOLOGY),
        comfort_zones=comfort_zones or [],
        escalation_trait=rng.choice(_ESCALATION_TRAITS),
    )
    mo_components = []
    mo_components.extend(_build_components(rng, NemesisComponentType.APPROACH, _APPROACHES))
    mo_components.extend(_build_components(rng, NemesisComponentType.CONTROL, _CONTROLS))
    mo_components.extend(_build_components(rng, NemesisComponentType.METHOD, _METHODS))
    mo_components.extend(_build_components(rng, NemesisComponentType.CLEANUP, _CLEANUP))
    mo_components.extend(_build_components(rng, NemesisComponentType.EXIT, _EXITS))
    _seed_weaknesses(rng, mo_components, count=2)
    return NemesisState(
        profile=profile,
        mo_components=mo_components,
        exposure=0,
        exposure_baseline=0,
        cases_until_next=rng.randint(2, 4),
        escalation_cap=3,
    )


def plan_nemesis_case(state: NemesisState, rng: Rng) -> NemesisCasePlan:
    if state.cases_until_next > 0:
        state.cases_until_next -= 1
        return NemesisCasePlan(is_nemesis_case=False)
    state.cases_until_next = rng.randint(2, 4)
    _decay_cooldowns(state)
    method, degraded = _select_method_component(state, rng)
    visibility = min(state.escalation_cap, 1 + state.exposure // 2)
    return NemesisCasePlan(
        is_nemesis_case=True,
        method_category=method.value if method else None,
        visibility=visibility,
        degraded_execution=degraded,
        taunt_style=state.profile.failure_echo,
    )


def apply_nemesis_case_outcome(
    state: NemesisState,
    was_nemesis_case: bool,
    visibility: int,
    arrest_result: str,
    method_category: str | None,
    method_compromised: bool,
    rng: Rng,
) -> list[str]:
    notes: list[str] = []
    if not was_nemesis_case:
        return notes
    delta = max(0, visibility - 1)
    if arrest_result in {"success", "partial"}:
        delta += 1
    if arrest_result == "failed" and visibility <= 1:
        delta -= 1
    state.exposure = max(state.exposure_baseline, state.exposure + delta)
    if delta > 0 and state.exposure > state.exposure_baseline:
        state.exposure_baseline = max(state.exposure_baseline, state.exposure - 1)
    if method_compromised:
        _mark_method_compromised(state, method_category)
        notes.append("Pattern file notes a compromised method.")
    if arrest_result == "failed":
        state.profile.failure_echo = rng.choice(
            ["irritated", "defensive", "taunting", "quiet"]
        )
    return notes


def _build_components(
    rng: Rng, component_type: NemesisComponentType, values: list[str]
) -> list[NemesisComponent]:
    components: list[NemesisComponent] = []
    for value in values:
        weight = 0.6 + rng.random() * 1.0
        competence = 0.35 + rng.random() * 0.55
        components.append(
            NemesisComponent(
                component_type=component_type,
                value=value,
                weight=round(weight, 2),
                competence=round(competence, 2),
            )
        )
    return components


def _seed_weaknesses(rng: Rng, components: list[NemesisComponent], count: int = 2) -> None:
    candidates = [comp for comp in components if comp.component_type == NemesisComponentType.METHOD]
    rng.shuffle(candidates)
    for comp in candidates[:count]:
        comp.competence = round(0.2 + rng.random() * 0.2, 2)


def _decay_cooldowns(state: NemesisState) -> None:
    for comp in state.mo_components:
        if comp.avoid_cooldown > 0:
            comp.avoid_cooldown -= 1


def _select_method_component(
    state: NemesisState, rng: Rng
) -> tuple[NemesisComponent | None, bool]:
    methods = [
        comp for comp in state.mo_components if comp.component_type == NemesisComponentType.METHOD
    ]
    if not methods:
        return None, False
    weights: list[float] = []
    for comp in methods:
        weight = comp.weight
        if comp.compromised and comp.avoid_cooldown == 0:
            weight *= 0.4
        weights.append(weight)
    chosen = _weighted_pick(rng, methods, weights)
    degraded = bool(chosen.compromised and chosen.avoid_cooldown > 0)
    for comp in methods:
        if comp is chosen:
            continue
        if comp.compromised and comp.avoid_cooldown == 0:
            comp.avoid_cooldown = _ADAPT_COOLDOWN
    return chosen, degraded


def _mark_method_compromised(state: NemesisState, method_category: str | None) -> None:
    methods = [
        comp for comp in state.mo_components if comp.component_type == NemesisComponentType.METHOD
    ]
    if not methods:
        return
    if method_category:
        for comp in methods:
            if comp.value == method_category:
                comp.compromised = True
                return
    methods.sort(key=lambda comp: comp.weight, reverse=True)
    methods[0].compromised = True


def _weighted_pick(rng: Rng, items: list[NemesisComponent], weights: list[float]) -> NemesisComponent:
    total = sum(weights)
    if total <= 0:
        return items[0]
    pick = rng.random() * total
    cumulative = 0.0
    for item, weight in zip(items, weights):
        cumulative += weight
        if pick <= cumulative:
            return item
    return items[-1]
