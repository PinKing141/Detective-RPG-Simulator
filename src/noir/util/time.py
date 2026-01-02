"""Time helpers using integer ticks for Phase 0."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TimeWindow:
    start: int
    end: int

    def normalized(self) -> "TimeWindow":
        if self.start <= self.end:
            return self
        return TimeWindow(start=self.end, end=self.start)

    def contains(self, t: int) -> bool:
        window = self.normalized()
        return window.start <= t <= window.end

    def overlaps(self, other: "TimeWindow") -> bool:
        left = self.normalized()
        right = other.normalized()
        return left.start <= right.end and right.start <= left.end


def overlaps(start: int, end: int, other_start: int, other_end: int) -> bool:
    return TimeWindow(start=start, end=end).overlaps(TimeWindow(start=other_start, end=other_end))
