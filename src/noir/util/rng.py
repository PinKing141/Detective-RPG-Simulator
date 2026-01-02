"""Deterministic RNG wrapper for reproducible cases."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import random
from typing import Iterable, Sequence, TypeVar

T = TypeVar("T")


@dataclass
class Rng:
    seed: int

    def __post_init__(self) -> None:
        self._random = random.Random(self.seed)

    def fork(self, salt: str) -> "Rng":
        digest = hashlib.sha256(f"{self.seed}:{salt}".encode("ascii")).hexdigest()
        new_seed = int(digest[:16], 16)
        return Rng(new_seed)

    def random(self) -> float:
        return self._random.random()

    def randint(self, a: int, b: int) -> int:
        return self._random.randint(a, b)

    def choice(self, seq: Sequence[T]) -> T:
        return self._random.choice(seq)

    def sample(self, seq: Sequence[T], k: int) -> list[T]:
        return self._random.sample(list(seq), k)

    def shuffle(self, seq: list[T]) -> None:
        self._random.shuffle(seq)

    def gauss(self, mu: float, sigma: float) -> float:
        return self._random.gauss(mu, sigma)

    def weighted_choice(self, items: Iterable[tuple[T, float]]) -> T:
        items_list = list(items)
        total = sum(weight for _, weight in items_list)
        if total <= 0:
            raise ValueError("weighted_choice requires positive total weight")
        pick = self._random.random() * total
        cumulative = 0.0
        for value, weight in items_list:
            cumulative += weight
            if pick <= cumulative:
                return value
        return items_list[-1][0]
