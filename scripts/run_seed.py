from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from noir import config
from noir.cases.truth_generator import generate_case
from noir.presentation.projector import project_case
from noir.util.rng import Rng


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a seeded Phase 0 case.")
    parser.add_argument("--seed", type=int, default=config.SEED)
    parser.add_argument("--case-id", type=str, default=None)
    args = parser.parse_args()

    rng = Rng(args.seed)
    truth, _ = generate_case(rng, case_id=args.case_id)
    presentation = project_case(truth, rng.fork("projection"))

    print(f"Case: {presentation.case_id} (seed {presentation.seed})")
    print(f"Evidence count: {len(presentation.evidence)}")
    for item in presentation.evidence:
        print(f"- {item.evidence_type} | {item.summary} | {item.confidence}")


if __name__ == "__main__":
    main()
