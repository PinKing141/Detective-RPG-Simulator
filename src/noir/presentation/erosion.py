"""Noise functions for Truth -> Presentation projection."""

from __future__ import annotations

from noir.domain.enums import ConfidenceBand
from noir.util.rng import Rng


def fuzz_time(time_value: int, sigma: float, rng: Rng) -> tuple[int, int]:
    spread = int(abs(rng.gauss(0, sigma)))
    start = max(0, time_value - spread)
    end = time_value + spread
    return start, end


def maybe_omit(probability: float, rng: Rng) -> bool:
    return rng.random() < probability


def maybe_lie(probability: float, rng: Rng) -> bool:
    return rng.random() < probability


def confidence_from_window(window: tuple[int, int]) -> ConfidenceBand:
    spread = window[1] - window[0]
    if spread <= 1:
        return ConfidenceBand.STRONG
    if spread <= 3:
        return ConfidenceBand.MEDIUM
    return ConfidenceBand.WEAK
