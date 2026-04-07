"""Nemesis helpers (Phase 3D/3E)."""

from noir.nemesis.patterns import PatternAddendum, PatternTracker
from noir.nemesis.signature import apply_signature_to_truth, build_signature_meta
from noir.nemesis.state import (
    NemesisCasePlan,
    NemesisComponent,
    NemesisComponentType,
    NemesisProfile,
    NemesisState,
    NemesisTypology,
    apply_nemesis_case_outcome,
    create_nemesis_state,
    plan_nemesis_case,
)

__all__ = [
    "PatternAddendum",
    "PatternTracker",
    "apply_signature_to_truth",
    "build_signature_meta",
    "NemesisCasePlan",
    "NemesisComponent",
    "NemesisComponentType",
    "NemesisProfile",
    "NemesisState",
    "NemesisTypology",
    "apply_nemesis_case_outcome",
    "create_nemesis_state",
    "plan_nemesis_case",
]
