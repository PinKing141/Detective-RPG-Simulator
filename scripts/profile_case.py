from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from noir import config
from noir.cases.truth_generator import generate_case
from noir.domain.enums import RoleTag
from noir.util.rng import Rng


def main() -> None:
    parser = argparse.ArgumentParser(description="Profile a seeded Phase 0 case.")
    parser.add_argument("--seed", type=int, default=config.SEED)
    parser.add_argument("--case-id", type=str, default=None)
    args = parser.parse_args()

    rng = Rng(args.seed)
    truth, _ = generate_case(rng, case_id=args.case_id)

    offender = next(
        (person for person in truth.people.values() if RoleTag.OFFENDER in person.role_tags),
        None,
    )

    print(f"Case: {truth.case_id} (seed {truth.seed})")
    if truth.case_meta:
        print("Case meta:")
        for key, value in truth.case_meta.items():
            print(f"- {key}: {value}")
    if offender:
        print("Offender traits:")
        for key, value in offender.traits.items():
            print(f"- {key}: {value}")


if __name__ == "__main__":
    main()
